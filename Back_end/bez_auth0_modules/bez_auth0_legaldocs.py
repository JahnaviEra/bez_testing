import json, logging, boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def _get_doc(event):
    try:
        logger.info('Received event: {event}')
        # body = json.loads(event.get("body", "{}"))
        BUCKET_NAME = "bez-dev"
        if not event['queryStringParameters'].get("file_name"):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': "file_name is required."})
            }

        file_name = event['queryStringParameters']["file_name"]
        if file_name == "privacy_policy":
            file = "Bez Privacy Policy.pdf"
        elif file_name == "terms_and_conditions":
            file = "Bez Terms and Conditions.pdf"
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': "Invalid file_name"})
            }
        # data = {}
        presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': f"common/documents/{file}"},
                ExpiresIn=3600  # URL valid for 1 hour
            )
        logger.info(presigned_url)
        data = presigned_url
        result = {"data":data}
        return {'statusCode': 200,
                'body': json.dumps(result)
                }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error get Document info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }