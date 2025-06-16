import json, logging

# import from bez resources
from bez_utility.bez_utils_aws import _write_s3
from bez_utility.bez_metadata_messages import _update_msg_output

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez-dev"

def _error_handler(event):
    logger.info(event)
    object_key = f'{event["integration_id"]}/{event["agent_int_uid"]}/chat_history/{event["message_id"]}'
    ai_response = json.dumps({"statusCode": 400, "body": json.dumps(event["error"])})
    _write_s3(BUCKET_NAME,object_key,ai_response)
    _update_msg_output(event["message_id"], ai_response)
    raise Exception(f"Error Handler: {event["error"]}")
