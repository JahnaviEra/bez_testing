import json, boto3, logging, time
import http.client
from botocore.exceptions import BotoCoreError, ClientError
from urllib.parse import urlencode

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value
from bez_utility.bez_utils_auth0 import _add_mfa, _verify_mfa, _create_jwt_token
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _mfa_verify(event):
    try:
        logger.info(f'Received event: {event}')
        start_time = ((time.time()))
        body = json.loads(event.get("body", "{}"))
        mfa_token = body.get('mfa_token')
        otp = body.get('otp')
        validation_rules = {
            "mfa_token": ["required"],
            "otp": ["required", "otp"]
        }

        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        
        logger.info(f'MFA Token: {mfa_token}')
        logger.info(f'OTP: {otp}')
        duration = str(time.time() - (start_time))
        logger.info(f'Reading variables: {duration}')
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        duration = str((time.time()) - (start_time))
        logger.info(f'Got config: {duration}')
        logger.info(f'Secret value for env variables: {config}')
        response = _verify_mfa(mfa_token, otp, config)
        duration = str((time.time()) - (start_time))
        logger.info(f'Got config: {duration}')
        logger.info(f'Response from verify MFA: {response}')
        if response['status'] == 200:
            try:
                token = _create_jwt_token({"token": response['data']['id_token'], "config": config})
                duration = str((time.time()) - (start_time))
                logger.info(f'Created jwt: {duration}')
                logger.info(f'Token: {token}')
                result = {"data": token}
                lambda_response = {
                    'statusCode': 200,
                    'body': json.dumps(result)
                }
                logger.info(f'Lambda response: {lambda_response}')
                return lambda_response
            except Exception as e:
                result =  {"error": {"code": "SOMETHING_WENT_WRONG", "message": str(e)}}
                lambda_response= {
                    'statusCode': 500,
                    'body': json.dumps(result)
                }
                return lambda_response
        else:
            error_data = response.get('data', '')
            result =   {"error": error_data.get('error', ''), "error_description": error_data.get('error_description', '')}
            lambda_response = {
                    'statusCode': 400,
                    'body': json.dumps(result)
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
            logger.error(f"Error verify Mfa info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }