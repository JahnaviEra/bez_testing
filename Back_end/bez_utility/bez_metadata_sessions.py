import  logging, time
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# import from bez functions
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _get_record_from_table

# Initialize resources
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Calling resources
sessions_table = dynamodb.Table("sessions")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_session_id():
    try:
        session_id = _generate_uid({"n": "16"})
        print(session_id)
        session_exists = _check_record_exists({"table_name": "sessions", "keys": {"session_id": session_id}, "gsi_name": ""})
        print(session_exists)
        if session_exists:
            session_id = _get_session_id()
    except Exception as error:
        raise error
    return session_id

def _create_session(data):
    user_id = data.get("user_id", "")
    try:
        session_id = _get_session_id()
        item =  {
            "session_id": session_id,
            "user_id": user_id,
            "validated_at": str(int(time.time())),
            "expires_at": str(int(time.time()) + 30 * 60),
            "login_at": str(int(time.time())),
            }
        response = sessions_table.put_item(Item=item, ConditionExpression="attribute_not_exists(session_id)")
        logger.info('Session created in Sessions table')
        return session_id
    except ClientError as e:
        logger.error(f"Error storing session: {e.response['Error']['Message']}")
        return {"error": e.response['Error']['Message']}

def _get_session_details_by_id(data):
    session_id = data.get("session_id", "")
    try:
        item = _get_record_from_table({"table_name": "sessions", "keys": {"session_id": session_id}, "gsi_name": ""})
        if item:
            return item
        else:
            return None
    except Exception as error:
        print(f"Unexpected error: {error}")
        raise error
