import json, logging, os

# import from bez resources
from bez_utility.bez_metadata_agents import _get_agent_details, _create_agent_ai_name, _get_agent_int_uid, _create_record_agent_by_int, _get_agent_privilege_id, _create_agent_privilege_record, _save_mda_default_sections, _save_agent_pic
from bez_utility.bez_metadata_clients import _check_user_client_access
from bez_utility.bez_metadata_int import _get_int_by_intid, _check_user_access
from bez_utility.bez_utils_bedrock import _generate_avatar_prompt
from bez_utility.bez_utils_aws import _get_presigned_url

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("BUCKET_NAME", "bez")

def _get_base_agent_profile(event):
    try:
        logger.info(f"Received event: {event}")
        agent_id = event['queryStringParameters']["agent_id"]
        if not agent_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required parameter: agent_id"})}
        base_agent = _get_agent_details(agent_id)
        logger.info(f"Base agent: {base_agent}")
        return {"statusCode": 200, "body": json.dumps(base_agent)}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}")
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}

def _create_agent_profile(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        env = event.get("headers", {}).get("env", None)
        event_body = json.loads(event.get("body", {}))
        logger.info(f"Event body: {event_body}")
        agent_id = event_body.get("agent_id")
        int_id = event_body.get("int_id")
        integration = _get_int_by_intid(int_id)
        client_id = integration['client_id']
        client_access = _check_user_client_access(user_id, client_id)
        if not client_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this client. Please select a different client and try again."})}
        logger.info(f"Client ID: {client_id}")
        int_access = _check_user_access(user_id, int_id)
        if not int_access:
            return {"statusCode": 400, "body": json.dumps({"error": "You do not have permissions to access this integration. Please select a different client and try again."})}
        agent_name = _create_agent_ai_name(agent_id, user_id)
        agent_data = _get_agent_details(agent_id)
        agent_int_uid = _get_agent_int_uid(agent_id, int_id)
        agent_pic = _generate_avatar_prompt(agent_name)
        s3_path = _save_agent_pic(agent_pic, agent_name, agent_int_uid, env, agent_data["agent_type"])
        bucket_name = f"{BUCKET_NAME}-{env}"
        presigned_url = None
        if s3_path:
            presigned_url = _get_presigned_url(bucket_name, s3_path, 3600)
        _create_record_agent_by_int(int_id, agent_int_uid, agent_name, agent_data["agent_type"], agent_data["skillset"], agent_data["welcome_prompt"], s3_path)
        agent_privilege_id = _get_agent_privilege_id()
        _create_agent_privilege_record(agent_privilege_id, agent_int_uid, agent_data["agent_persona"], user_id, '')
        if agent_id == "001":
             _save_mda_default_sections(agent_int_uid)
        return {"statusCode": 200,
                "body": json.dumps({"message": "Agent details saved successfully.",
                                "agent_int_uid": agent_int_uid,
                                "agent_name": agent_name,
                                "profile_pic_url": presigned_url})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }