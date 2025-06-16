import json, boto3, logging
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_utils_auth0 import _add_mfa
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _addmfa(event):
    try:
        logger.info(f'Received event: {event}')
        body = json.loads(event.get("body", "{}"))
        mfa_token = body.get('mfa_token')
        validation_rules = {
            "mfa_token": ["required"]
        }
        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info(f'Secret value for env variables: {config}')
        response = _add_mfa(config, mfa_token)
        if response.status == 200:
            associate = response.read().decode()
            logger.info(associate)
            result =  {"data": {"mfa_token": mfa_token, "associate": json.loads(associate)}}
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
        else:
            errors = response.read().decode()
            logger.error(errors)
            message = json.loads(errors).get('error_description', '')
            result =  {"error": {"code": "AUTH0_REQUEST_FAILED", "message": message}}
            return {
                'statusCode': 403,
                'body': json.dumps(result)
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
            logger.error(f"Error add MFA info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }