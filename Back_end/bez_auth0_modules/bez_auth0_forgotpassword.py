import json, boto3, logging
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode

# import from bez resources
from bez_utility.bez_metadata_users import _get_user_by_email
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_utils_auth0 import _get_user_by_email_auth0
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _forgot_password(event):
    try:
        logger.info('Received event:', event)
        body = json.loads(event.get("body", "{}"))
        email = body.get('email')
        validation_rules = {
            "email": ["required", "email"]
        }

        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        user = _get_user_by_email({"email": email})
        if not user:
            auth0_data = _get_user_by_email_auth0({"email": email, "config": config})
            if len(auth0_data) == 0:
                lambda_response = {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'The above email is not associated with any user. Please check your email and try again.'})
                }
                return lambda_response
        connection = http.client.HTTPSConnection(config['AUTH0_DOMAIN'])
        headers = {'content-type': "application/json"}
        data = {
            'client_id': config['AUTH0_CLIENT_ID'],
            'email': email,
            'connection': config['AUTH0_DATABASE']
        }
        body = json.dumps(data)
        connection.request("POST", "/dbconnections/change_password", body=body, headers=headers)
        response = connection.getresponse()
        if response.status == 200:
            result = {"data": "You have submitted a request to change your password. Please check your email for next steps."}
            lambda_response = {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            return lambda_response
        else:
            lambda_response = {
                'statusCode': 400,
                'body': json.dumps({'error': f'Something went wrong. Please try again later'})
            }
            return lambda_response

    except KeyError as e:
        lambda_response = {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing parameter: {str(e)}'})
        }
        return lambda_response
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error forgotpassword info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }