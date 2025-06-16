import logging

# import from bez resources
from bez_utility.bez_utils_aws import _read_s3
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _wf_qbo_identify(event):
    try:
        logger.info(f"Received event: {event}")
        s3_bucket = event["s3_bucket"]
        s3_key = event["s3_key"]
        logger.info(s3_key)
        bez_training_prompt = _read_s3(s3_bucket, s3_key)
        system_prompt = bez_training_prompt
        # full_prompt = "Answer the following questions:" + " " + event["user_prompt"].strip() + "/n using: /n" + system_prompt
        full_prompt = f"""
        These are the Guideline that you need to follow to provide response to the User's question :
            {system_prompt}
        Here is the User's Question:
            {event["user_prompt"].strip()}"""
        ai_response = _get_ai_response({"prompt": full_prompt})
        logger.info(ai_response)
        return ai_response
    except Exception as e:
        logger.error(f"Error in _wf_qbo_identify: {e}")
        raise Exception(str(e))
