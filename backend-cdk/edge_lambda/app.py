import json
import os
import boto3

lambda_client = boto3.client("lambda")
CORE_FUNCTION = os.environ["CORE_FUNCTION_NAME"]

REQUIRED_FIELDS = ["question", "ticker", "year", "period"]

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    missing = [f for f in REQUIRED_FIELDS if f not in body]
    if missing:
        return _response(400, {
            "error": "ValidationError",
            "message": f"Missing required fields: {', '.join(missing)}"
        })

    response = lambda_client.invoke(
        FunctionName=CORE_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(body).encode(),
    )

    if "FunctionError" in response:
        error_payload = json.loads(response["Payload"].read())
        return _response(502, {
            "error": "CoreLambdaError",
            "message": str(error_payload)
        })

    result = json.loads(response["Payload"].read())
    return _response(200, result)


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }