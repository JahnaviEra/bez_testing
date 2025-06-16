import json, time, logging
import boto3
from botocore.exceptions import ClientError

#import from bez functions
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _get_record_from_table

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
users_table = dynamodb.Table("users")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_user_id():
    try:
        user_id = _generate_uid({"n": "8"})
        print('User id is:', user_id)
        user_id_exists = _check_record_exists({"table_name": "users",
                                                "keys": {"user_id": user_id},
                                                "gsi_name": ""})
        # print('User Exists:', user_id_exists)
        if user_id_exists:
            _get_user_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique User id is:{user_id}')
    return user_id

def _create_user(data):
    try:
        user_id = _get_user_id()
        item = {
            "user_id": user_id,
            "auth0_id": data.get("auth0_id", ""),
            "created_at": str(int(time.time())),
            "email": data.get("email", "").lower(),
            "email_verified": False,
            "first_name": data.get("first_name", ""),
            "is_deleted": False,
            "is_super_admin": False,
            "last_name": data.get("last_name", "")
        }
        logger.info(f'Item inserted to User table: {item}')
        response = users_table.put_item(Item=item)
        logger.info('User created in Users table')
        return user_id
    except ClientError as e:
        logger.error(f"Error storing user: {e.response['Error']['Message']}")
        return {"error": e.response['Error']['Message']}

def _get_user_by_email(data):
    try:
        print(data)
        logger.info(f'User data type: {type(data)}')
        email = data.get("email", "").lower()
        logger.info(f'User email: {email}')
        item = _get_record_from_table({"table_name": "users",
                                    "keys": {"email": email.lower()},
                                    "gsi_name": "email-index"})
        if item:
            logger.info(f'User found: {item}')
            return item
        else:
            raise Exception("Function Error: User not found")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_user_by_id(data):
    try:
        print(data)
        user_id = data.get("user_id")
        item = _get_record_from_table({"table_name": "users",
                                    "keys": {"user_id": user_id},
                                    "gsi_name": ""})
        if item:
            return item
        else:
            raise Exception("Function Error: User not found")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
