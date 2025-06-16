import boto3, logging
# import pandas as pd
import csv
from io import BytesIO
from io import StringIO

# Initialize DynamoDB resource
s3 = boto3.client('s3')

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# def _read_xl_s3(bucket_name, object_key, sheet_name=None):
#     try:
#         response = s3.get_object(Bucket=bucket_name, Key=object_key)
#         with BytesIO(response['Body'].read()) as file_stream:
#             df = pd.read_excel(file_stream, sheet_name=sheet_name)
#         return df.to_dict(orient='records')
    
#     except s3.exceptions.NoSuchKey:
#         logger.error(f"S3 object '{object_key}' not found in bucket '{bucket_name}'.")
#         raise
#     except Exception as e:
#         logger.error(f"Failed to read Excel file from S3: {e}")
#         raise Exception(f"Function Error: An error occured while reading Excel file {e}")

def _read_csv_s3(bucket_name, object_key):
    try:
        # response = s3.get_object(Bucket=bucket_name, Key=object_key)
        # with BytesIO(response['Body'].read()) as file_stream:
        #     df = pd.read_csv(file_stream, encoding='utf-8')
        # return df.to_dict(orient='records')
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(content))
        return list(csv_reader)
    except s3.exceptions.NoSuchKey:
        logger.error(f"S3 object '{object_key}' not found in bucket '{bucket_name}'.")
        raise
    except Exception as e:
        logger.error(f"Failed to read CSV file from S3: {e}")
        raise Exception(f"Function Error: An error occured while reading CSV file {e}")