import json, boto3, logging
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_utils_auth0 import _get_user_by_email_auth0
from bez_utility.bez_metadata_users import _get_user_by_email
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _email_available(event):
    try:
        logger.info(f'Received event: {event}')
        body = json.loads(event.get("body", "{}"))
        validation_rules = {
            "email": ["required", "email"]
        }
        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        email = body.get('email').lower()
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info(f'Secret value for env variables: {config}')
        user = _get_user_by_email({"email": email})
        logger.info(f"User: {user}")
        if user:
            lambda_response = {
                'statusCode': 401,
                'body': json.dumps({"error": {"message": "Email already exists"}})
            }  
        else:
            # Checking if user exists in Auth0
            user_data = _get_user_by_email_auth0({"email": email, "config": config})
            if len(user_data)>0:
                lambda_response = {
                    'statusCode': 402,
                    'body': json.dumps({'error': 'Email already exists'})
                }
            else:       
                lambda_response = {
                    'statusCode': 200,
                    'body': json.dumps({'data': 'Email available'})}
        return lambda_response        
    except KeyError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing parameter: {str(e)}'})
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error email available info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }