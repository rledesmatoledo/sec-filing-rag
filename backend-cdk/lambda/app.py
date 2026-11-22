import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request

import boto3

from text_extractor import extract_text

USER_AGENT = os.environ.get("SEC_USER_AGENT", "Roberto Ledesma robertoledesma015@gmail.com")
MODEL_ID = os.environ["MODEL_ID"]
MODEL_CONTEXT_WINDOW = int(os.environ.get("MODEL_CONTEXT_WINDOW", "200000"))
CONTEXT_BUDGET_RATIO = float(os.environ.get("CONTEXT_BUDGET_RATIO", "0.8"))
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "1024"))

FILING_TOKEN_BUDGET = int(MODEL_CONTEXT_WINDOW * CONTEXT_BUDGET_RATIO)

VALID_PERIODS = ("Q1", "Q2", "Q3", "Q4", "FY")
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

SYSTEM_PROMPT = (
    "You are a financial analyst assistant. You answer strictly from the SEC filing "
    "text you are given. Quote the figures as they appear in the filing. If the filing "
    "does not contain the answer, say so explicitly instead of guessing."
)

_bedrock = boto3.client("bedrock-runtime")


def _error(code, message, field=None):
    body = {"error": code, "message": message}
    if field:
        body["field"] = field
    return body

def _api_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }

class EdgarError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.payload = _error(code, message)


def validate(event):
    if not isinstance(event, dict):
        return _error("ValidationError", "Request body must be a JSON object.")

    for field in ("question", "ticker", "year", "period"):
        if field not in event:
            return _error("ValidationError", f"Missing required field: '{field}'.", field)

    question = event["question"]
    if not isinstance(question, str) or not question.strip():
        return _error("ValidationError", "'question' must be a non-empty string.", "question")

    ticker = event["ticker"]
    if not isinstance(ticker, str):
        return _error("ValidationError", "'ticker' must be a string.", "ticker")
    if not TICKER_PATTERN.match(ticker):
        return _error(
            "ValidationError",
            f"Invalid ticker '{ticker}'. Must be uppercase, 1-10 characters "
            "(letters, digits, '.' or '-').",
            "ticker",
        )

    year = event["year"]
    if isinstance(year, bool) or not isinstance(year, int):
        return _error("ValidationError", "'year' must be an integer.", "year")
    if not 1993 <= year <= 2100:
        return _error("ValidationError", f"'year' out of range: {year}.", "year")

    period = event["period"]
    if not isinstance(period, str) or period not in VALID_PERIODS:
        return _error(
            "ValidationError",
            f"Invalid value for 'period': {period!r}. Must be one of: "
            f"{', '.join(VALID_PERIODS)}.",
            "period",
        )

    return None


def _get(url, host=None):
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    if host:
        headers["Host"] = host
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body
    except urllib.error.HTTPError as exc:
        raise EdgarError("UpstreamError", f"SEC EDGAR returned {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EdgarError("UpstreamError", f"Could not reach SEC EDGAR: {exc}") from exc


def _get_json(url, host=None):
    return json.loads(_get(url, host=host))


def lookup_cik(ticker):
    data = _get_json("https://www.sec.gov/files/company_tickers_exchange.json")
    columns = data["fields"]
    cik_index, ticker_index = columns.index("cik"), columns.index("ticker")
    for row in data["data"]:
        if row[ticker_index] == ticker:
            return int(row[cik_index])
    raise EdgarError("NotFound", f"Ticker '{ticker}' is not registered with SEC EDGAR.")


def _quarter_of(report_date):
    year, month = int(report_date[0:4]), int(report_date[5:7])
    return year, f"Q{(month - 1) // 3 + 1}"


def _iter_filings(submissions):
    recent = submissions["filings"]["recent"]
    for index in range(len(recent["accessionNumber"])):
        yield {key: recent[key][index] for key in recent}

    for page in submissions["filings"].get("files", []):
        older = _get_json(
            f"https://data.sec.gov/submissions/{page['name']}", host="data.sec.gov"
        )
        for index in range(len(older["accessionNumber"])):
            yield {key: older[key][index] for key in older}


def find_filing(cik, year, period):
    submissions = _get_json(
        f"https://data.sec.gov/submissions/CIK{cik:010d}.json", host="data.sec.gov"
    )
    form_type = "10-K" if period == "FY" else "10-Q"
    fallback = None

    for filing in _iter_filings(submissions):
        if filing["form"] != form_type:
            continue
        report_date = filing.get("reportDate") or ""
        if len(report_date) < 7:
            continue

        report_year, report_quarter = _quarter_of(report_date)
        if form_type == "10-K":
            fiscal_year = report_year - 1 if report_quarter == "Q1" else report_year
            exact = fiscal_year == year
            near = report_year == year
        else:
            exact = report_year == year and report_quarter == period
            near = False
        if not (exact or near):
            continue

        accession = filing["accessionNumber"].replace("-", "")
        match = {
            "url": (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"
                f"{filing['primaryDocument']}"
            ),
            "form": filing["form"],
            "filing_date": filing["filingDate"],
            "report_date": report_date,
            "accession_number": filing["accessionNumber"],
        }
        if exact:
            return match
        fallback = fallback or match

    if fallback:
        return fallback

    hint = ""
    if period == "Q4":
        hint = " Most filers cover Q4 in their annual report — try period 'FY'."
    raise EdgarError(
        "NotFound",
        f"No {form_type} covering {period} {year} was found for CIK {cik}.{hint}",
    )


def build_prompt(question, ticker, period, year, filing_text):
    return (
        "Using only the SEC filing text provided below, answer the following question. "
        "If the answer is not contained in the filing, say so explicitly.\n\n"
        f"Question: {question}\n\n"
        f"Filing ({ticker} {period} {year}):\n"
        f"{filing_text}"
    )


def lambda_handler(event, context):
    if "body" in event:
        try:
            event = json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON body"})
            }
    error = validate(event)
    if error:
        return _api_response(400, error)

    question = event["question"].strip()
    ticker, year, period = event["ticker"], event["year"], event["period"]

    try:
        cik = lookup_cik(ticker)
        filing = find_filing(cik, year, period)
        filing_html = _get(filing["url"]).decode("utf-8", errors="replace")
    except EdgarError as exc:
        return _api_response(400, exc.payload)

    filing_text = extract_text(filing_html, max_tokens=FILING_TOKEN_BUDGET)
    prompt = build_prompt(question, ticker, period, year, filing_text)

    try:
        started = time.perf_counter()
        response = _bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": MAX_OUTPUT_TOKENS, "temperature": 0},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
    except Exception as exc:
        return _api_response(500, _error("InferenceError", f"Bedrock Converse call failed: {exc}"))

    usage = response.get("usage", {})
    return _api_response(200, {
        "answer": response["output"]["message"]["content"][0]["text"],
        "meta": {
            "model": MODEL_ID,
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
            "latency_ms": latency_ms,
            "source": {
                "form": filing["form"],
                "url": filing["url"],
                "report_date": filing["report_date"],
                "filing_date": filing["filing_date"],
            },
        },
    })