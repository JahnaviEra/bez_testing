import json, logging

from bez_utility.bez_metadata_agents import _get_details_for_agentintuid, _check_user_agent_access, _save_agent_pic, _get_agent_details
from bez_utility.bez_utils_aws import _get_presigned_url, _update_data_in_table
from bez_utility.bez_validation import PayloadValidator


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez"

def _agent_details(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        agent_details = _get_details_for_agentintuid(agent_int_uid)
        logger.info(f"agent_details: {agent_details}")
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        env = event.get("headers", {}).get("env", "dev")
        bucket_name = f"{BUCKET_NAME}-{env}"
        agent_name = agent_details.get("agent_name")
        agent_pic = agent_details.get("profile_pic",{})
        agent_pic_url = ""
        if agent_pic:
            agent_pic_url = _get_presigned_url(bucket_name, agent_pic, 3600)
        return {"statusCode": 200,
            "body": json.dumps({"agent_name": agent_name, "agent_pic": agent_pic, "agent_pic_url": agent_pic_url})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error fetching agent info: {str(e)}"})}


def _update_agent_details(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps(
                {"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        env = event.get("headers", {}).get("env", "dev")
        event_body = json.loads(event.get("body", "{}"))
        new_profile = event_body.get("agent_profile")
        if not new_profile:
            return {"statusCode": 400, "body": json.dumps({"error": "No profile to update."})}
        validation_rules = {
            "agent_name": ["required", "not_blank", "alpha"]
        }
        validator = PayloadValidator(new_profile, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        agent_name = new_profile.get("agent_name")
        image_data = new_profile.get("profile_pic")
        if not agent_name and not image_data:
            return {"statusCode": 400, "body": json.dumps({"error": "No valid fields to update."})}
        agent_id = agent_int_uid[:3]
        agent_data = _get_agent_details(agent_id)
        profile_pic = _save_agent_pic(image_data, agent_name, agent_int_uid, env, agent_data["agent_type"])
        _update_data_in_table({"table_name": "agent_list_by_int",
                               "key":"agent_int_uid",
                               "key_value": agent_int_uid,
                               "update_data":{"agent_name": agent_name, "profile_pic": profile_pic}})
        return {"statusCode": 200, "body": json.dumps({"message": "Agent profile updated successfully."})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}