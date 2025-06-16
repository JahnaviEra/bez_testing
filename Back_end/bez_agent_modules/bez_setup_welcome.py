import json, logging

# import from bez resources
from bez_utility.bez_metadata_users import _get_user_by_id
from bez_utility.bez_utils_aws import _get_record_from_table
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _setup_welcome(event):
    try:
        logger.info(f"Received event: {event}")
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        body = json.loads(event.get("body", {}))
        logger.info(f"Session ID: {body}")
        agent_id = body.get("agent_id", None)
        logger.info(f"Agent: {agent_id}")
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        elif not agent_id:
            return {"statusCode": 400, "body": "Please select an agent to sign up."}
        user = _get_user_by_id({"user_id": user_id})
        first_name = user.get("first_name", "User")
        logger.info(f"First name: {first_name}") 
        admin_agent = _get_record_from_table({"table_name": "agent_list", "keys": {"agent_id": "admin"}, "gsi_name": ""})
        admin_welcome_prompt = admin_agent.get("welcome_prompt", "").replace("{first_name}", first_name)
        agent = _get_record_from_table({"table_name": "agent_list", "keys": {"agent_id": agent_id}, "gsi_name": ""})
        system_prompt = admin_welcome_prompt + "/n Don't leave additional spaces in the response."
        ai_response = _get_ai_response({"prompt": system_prompt})
        logger.info(f"Admin prompt: {ai_response}")
        result = {"setup_message": ai_response}
        return {
            'statusCode': 200,
            'body': json.dumps(result)
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