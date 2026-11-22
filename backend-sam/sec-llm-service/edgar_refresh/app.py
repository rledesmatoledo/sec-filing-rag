import json
import os
import boto3
import requests

def lambda_handler(event, context):

    headers = {
        "User-Agent": "Roberto Ledesma robertoledesma015@gmail.com"
    }

    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.text
    except requests.exceptions.RequestException as e:
        print(f"SEC request failed: {e}")
        return {
            "error": "UpstreamError",
            "message": f"Failed to fetch data from SEC: {e}"
        }

    try:
        bucket = os.environ["BUCKET_NAME"]
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket=bucket,
            Key="company_tickers.json",
            Body=data
        )
    except Exception as e:
        print(f"S3 upload failed: {e}")
        return {
            "error": "StorageError",
            "message": f"Failed to upload to S3: {e}"
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "company_tickers.json uploaded"})
    }