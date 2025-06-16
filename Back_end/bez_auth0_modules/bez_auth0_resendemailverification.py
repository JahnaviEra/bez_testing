import json, boto3, logging
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value, _update_data_in_table
from bez_utility.bez_utils_auth0 import _get_user_by_email_auth0, _send_user_verification_email
from bez_utility.bez_metadata_users import _get_user_by_email, _create_user
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _resend_email_verification(event):
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
        email = email.lower()
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info(f'Secret value for env variables: {config}')
        auth0_user_data = _get_user_by_email_auth0({"email": email, "config": config})
        logger.info(f"User data from Auth0: {auth0_user_data}")
        auth0_user = auth0_user_data[0]
        if not isinstance(auth0_user_data, list) or len(auth0_user_data) == 0:
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": {"code": "USER_DOES_NOT_EXIST", "message": "The specified user does not exist."}})
                }
        else: 
            app_user = _get_user_by_email({"email": email})
            logger.info(f"User from Bezi-Metadata-Users: {app_user}")
            if not app_user:
                name = auth0_user['name'].split(' ')
                if len(name) == 2:
                    first_name, last_name = tuple(name)
                else:
                    first_name, last_name = name[0], ""
                create_user = _create_user({"auth0_id": auth0_user_data[0].get('identities')[0].get('user_id'), "email": email, "first_name": first_name, "last_name": last_name})
                logger.info(f"Created new user in DynamoDB table: {create_user}")
                app_user = _get_user_by_email({"email": email})
                logger.info(f"User from Bezi-Metadata-Users: {app_user}")
            if auth0_user.get("email_verified", False):
                if not app_user[0].get("email_verified", False):
                    _update_data_in_table({"table_name": "users", "key": "user_id",
                                            "key_value": str(app_user[0].get("user_id")),
                                            "update_data": {"email_verified": auth0_user.get("email_verified", False) }})
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": {"code": "EMAIL_ALREADY_VERIFIED", "message": "The selected email has already been verified. Please proceed with login."}})
                }
            elif not auth0_user.get("email_verified", False):
                _update_data_in_table({"table_name": "users", "key": "user_id",
                                        "key_value": str(app_user[0].get("user_id")),
                                        "update_data": {"email_verified": False }})
                logger.info(f"auth0 User ID: {auth0_user_data[0].get('identities')[0].get('user_id')}")
                response = _send_user_verification_email(str(f"auth0|{auth0_user_data[0].get('identities')[0].get('user_id')}"), config)
                logger.info(f"Response from Auth0: {response}")
                if "error" in response:
                    return {
                        'statusCode': 403,
                        'body': json.dumps({"error": {"code": "AUTH0_REQUEST_FAILED", "message": response["error"]}})
                    }
                else:
                    return {
                        'statusCode': 200,
                        'body': json.dumps({"data": "The verification email has been successfully sent."})
                    }  
    except KeyError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing parameter: {str(e)}'})
        }
    except Exception as e:        
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error Resend email info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }