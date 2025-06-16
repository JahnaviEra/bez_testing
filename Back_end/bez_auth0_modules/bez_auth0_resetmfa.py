import json, boto3, logging, time
from botocore.exceptions import ClientError
import http.client
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _send_reset_email(event):
    return {}


def _verify_otp(event):
    return {}

# import from bez resources
from bez_utility.bez_utils_aws import _get_secret_value, _update_data_in_table, _send_email
from bez_utility.bez_utils_auth0 import _get_user_by_email_auth0, _get_auth0_access_token, _get_user_mfa_factors, _delete_mfa_factor
from bez_utility.bez_metadata_users import _get_user_by_email, _create_user
from bez_utility.bez_validation import PayloadValidator
from bez_utility.bez_utils_common import _generate_otp

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _send_reset_email(event):
    try:
        logger.info('Received event: {event}')
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
        source = config.get("ses_email_source", "bez_dev@futureviewsystems.com")
        logger.info(f'Secret value for env variables: {config}')
        user = _get_user_by_email({"email": email})
        logger.info(f"User: {user}")
        if not user:
            auth0_data = _get_user_by_email_auth0({"email": email, "config": config})
            if len(auth0_data) == 0:
                lambda_response = {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'The above email is not associated with any user. Please check your email and try again.'})
                }
                return lambda_response
            auth0_user = auth0_data[0]
            name = auth0_user['name'].split(' ')
            if len(name) == 2:
                first_name, last_name = tuple(name)
            else:
                first_name, last_name = name[0], ""
            user_id  = _create_user({"auth0_id": auth0_user['user_id'],
                            "email": auth0_user['email'],
                            "first_name": first_name,
                            "last_name": last_name})          
        else:
            user_id  = user[0]['user_id']
        otp = _generate_otp()
        subject = "Reset your MFA"
        body = f"You have submitted a request to reset Multi-Factor Authentication. If it was you, confirm the request using this code. Your code is: {otp}\n\nThis OTP will expire in 10 minutes. Thanks!"
        otp_expiration =  int(time.time()) + (10 * 60)  # 10 minutes from now
        update_user = _update_data_in_table({"table_name": "users",
                                            "key": "user_id",
                                            "key_value": user_id,
                                            "update_data": {"otp": otp, "otp_expiration":otp_expiration}
                                            })
        _send_email(subject, body, email, source)
        result =   {"data": "Your code to reset MFA has been successfully sent. Please check your inbox to proceed."}
        lambda_response = {
            'statusCode': 200,
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
        lambda_response = {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
        return lambda_response

def _verify_otp(event):
    try:
        logger.info(f'Received event: {event}')
        body = json.loads(event.get("body", "{}"))
        email = body.get('email')
        otp = body.get('otp')
        validation_rules = {
            "email": ["required", "email"],
            "otp": ["required", "otp"],
        }
        validator = PayloadValidator(body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        config = _get_secret_value({"secret_name": "bezi/dev/env_variables"})
        logger.info(f'Secret value for env variables: {config}')
        user = _get_user_by_email({"email": email})
        logger.info(f"User: {user}")
        if not user:
            lambda_response = {
                'statusCode': 400,
                'body': json.dumps({'error': f'The above email is not associated with any user. Please check your email and try again.'})
            }
            logger.info(f"Lambda response: {lambda_response}")
            return lambda_response
        else:
            user_data = user[0]
        current_time = int(time.time())
        if not user_data.get("otp")  or int(user_data.get("otp")) != int(otp):
            lambda_response = {
                'statusCode': 400,
                'body': json.dumps({'error': f'Looks like the code entered is incorrect. Please check and enter valid code.'})
            }
            logger.info(f"Lambda response: {lambda_response}")
            return lambda_response
        if not user_data.get("otp_expiration") or int(user_data.get("otp_expiration")) < current_time:
            lambda_response = {
                'statusCode': 400,
                'body': json.dumps({'error': f'The code sent is no longer valid and has unfortunately expired. Please click on reset MFA and try again.'})
            }
            logger.info(f"Lambda response: {lambda_response}")
            return lambda_response
        access_token = _get_auth0_access_token({"config": config})        
        logger.info(f"Access token from Auth0: {access_token}")
        auth0_id = user_data['auth0_id']
        if not auth0_id.startswith("auth0|"):
            auth0_id = "auth0|" + str(auth0_id)       
        mfa_factors = _get_user_mfa_factors(access_token, config, auth0_id)
        error_message = ''
        if mfa_factors['status'] == 200:
            for factor in mfa_factors['data']:
                mfa_factor_id = factor['id']
                response = _delete_mfa_factor(access_token, mfa_factor_id, config, auth0_id)
                if response['status'] != 204:
                    error_message = "Error resetting Multi-factor Authenticator."
        else:
            error_message = f'Error resetting Multi-factor Authenticator.'        
        if error_message:
            lambda_response = {
                'statusCode': 400,
                'body': json.dumps({'error': f'We encountered a problem resetting MFA. Please try again after some time.'})
                }
            return lambda_response
        else:
            update_user = _update_data_in_table({"table_name": "users",
                                    "key": "user_id",
                                    "key_value": user_data['user_id'],
                                    "update_data": {"otp": 0, "otp_expiration":0}
                                    })
            result = {"data": "Your MFA has been successfully reset. Please continue to log in."}
            lambda_response = {
                'statusCode': 200,
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
            logger.error(f"Error resetMFA info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }