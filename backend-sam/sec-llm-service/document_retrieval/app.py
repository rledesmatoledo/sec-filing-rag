import json
import os
import requests

def lambda_handler(event, context):

    valid_periods = ["Q1", "Q2", "Q3", "Q4", "FY"]

    question = event.get("question", "")
    ticker = event.get("ticker", "")
    year = event.get("year", "")
    period = event.get("period", "")

    if period not in valid_periods:
        return {
            "error":"ValidationError",
            "message":f"Invalid value for 'period': '{period}'. Must be one of: Q1, Q2, Q3, Q4, FY."
        }

    headers = {
        "User-Agent": "Roberto Ledesma robertoledesma015@gmail.com"

    }

    try:
        ticker_url = "https://www.sec.gov/files/company_tickers_exchange.json"
        response = requests.get(ticker_url, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"SEC tickers request failed: {e}")
        return {
            "error": "UpstreamError",
            "message": f"Failed to fetch tickers from SEC: {e}"
        }
    
    cik = None
    for entry in data["data"]:
        if entry[2].upper() == ticker.upper():
            cik = entry[0]
            break

    if cik is None:
        return{
            "error":"NotFound",
            "message":f"Ticker '{ticker}' not found."
        }

    try:
        padded_cik = str(cik).zfill(10)
        sub_url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
        sub_headers = {
            "User-Agent": headers["User-Agent"],
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"
        }
        sub_response = requests.get(sub_url, headers=sub_headers)
        sub_response.raise_for_status()
        submissions = sub_response.json()
    except requests.exceptions.RequestException as e:
        print(f"SEC submissions request failed: {e}")
        return {
            "error": "UpstreamError",
            "message": f"Failed to fetch submissions from SEC: {e}"
        }

    form_type = "10-K" if period == "FY" else "10-Q"
    filings = submissions["filings"]["recent"]

    filing_url = None
    for i, form in enumerate(filings["form"]):
        if form == form_type and str(year) in filings["filingDate"][i]:
            accession = filings["accessionNumber"][i].replace("-", "")
            document = filings["primaryDocument"][i]
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
            break

    if filing_url is None:
        return {
            "error": "NotFound",
            "message": f"No {form_type} filing found for {ticker} in {year}."
        }
 
    return {
        "answer": f"Filing found for {ticker} ({period} {year}): {filing_url}",
        "meta": {
            "model": "none",
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0
        }
    }