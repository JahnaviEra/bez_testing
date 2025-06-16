import json, logging, os

# import from bez resources
from bez_utility.bez_metadata_agents import _get_agent_details, _get_agent_int_uid, _create_agent_by_int_table_record, _get_agent_privilege_id, _create_agent_privilege_record, _get_clean_folder_name, _save_agent_pic
from bez_utility.bez_metadata_clients import _check_user_client_access
from bez_utility.bez_metadata_int import _get_int_by_intid, _check_user_access
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_base_agent_profile(event):
    try:
        logger.info(f"Received event: {event}")
        agent_id = event['queryStringParameters']["agent_id"]
        base_agent = _get_agent_details(agent_id)
        logger.info(f"Base agent: {base_agent}")
        return {"statusCode": 200, "body": json.dumps(base_agent)}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }

def _save_agent_profile(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        env = event.get("headers", {}).get("env", None)
        event_body = json.loads(event.get("body", {}))
        validation_rules = {"agent_name": ["required", "not_blank", "alpha_num"],
                            "agent_id": ["required", "not_blank"],
                            "int_id": ["required", "not_blank"]}
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        logger.info(f"Event body: {event_body}")
        agent_id = event_body.get("agent_id")
        int_id = event_body.get("int_id")
        integration = _get_int_by_intid(int_id)
        client_id = integration['client_id']
        logger.info(f"Client ID: {client_id}")
        client_access = _check_user_client_access(user_id, client_id)
        if not client_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this client. Please select a different client and try again."})}
        int_access = _check_user_access(user_id, int_id)
        if not int_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this integration. Please select a different client and try again."})}
        agent_data = _get_agent_details(agent_id)
        logger.info(f"Agent data: {agent_data}")
        agent_age = event_body.get("agent_age", agent_data.get("agent_age"))
        agent_gender = event_body.get("agent_gender", agent_data.get("agent_gender"))
        agent_name = event_body.get("agent_name", agent_data.get("agent_name"))        
        agent_type = agent_data.get("agent_type", {})
        example_welcome_prompt = agent_data.get("example", {})
        skillset = agent_data.get("skillset", {})
        welcome_prompt = agent_data.get("welcome_prompt", {})
        agent_int_uid = _get_agent_int_uid(agent_id, int_id)
        cleaned_agent_type  = _get_clean_folder_name(agent_type)
        image_data  = event_body.get('agent_pic')
        profile_pic = _save_agent_pic(image_data, agent_name, agent_int_uid, env, agent_type)
        _create_agent_by_int_table_record(int_id, agent_int_uid, agent_age, agent_gender, agent_name, agent_type, example_welcome_prompt, skillset, welcome_prompt, profile_pic)
        agent_privilege_id = _get_agent_privilege_id()
        _create_agent_privilege_record(agent_privilege_id, agent_int_uid, user_id)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Agent details saved successfully.",
                "agent_int_uid": agent_int_uid
            })
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }