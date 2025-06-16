import boto3,logging,json

# Import from bez resources
from bez_utility.bez_utils_aws import _scan_table_with_filter, _get_presigned_url, _get_record_from_table, _update_data_in_table
from bez_utility.bez_metadata_agents import _check_user_agent_access
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
BUCKET_NAME = "bez"

def _list_of_llms(event):
    try:
        logger.info(f"Received event: {event}")
        env = event.get("headers", {}).get("env", "dev")
        bucket_name = f"{BUCKET_NAME}-{env}"
        items = _scan_table_with_filter({"table_name":"list_of_llm"})
        result = []
        for item in items:
            llm_name = item.get("llm_name", "")
            logo_path = item.get("llm_logo", "")
            llm_id = item.get("llm_id", "")
            provider = item.get("provider", "")
            finance_use_case = item.get("finance_use_case", "")
            tech_use_case = item.get("tech_use_case", "")
            if not logo_path:
                logger.warning(f"Skipping {llm_name}, invalid logo path")
                continue
            presigned_url = _get_presigned_url(bucket_name, logo_path, 3600)
            result.append({
                "llm_id": llm_id,
                "llm_name": llm_name,
                "llm_logo": presigned_url,
                "finance_use_case": finance_use_case,
                "tech_use_case": tech_use_case,
                "provider": provider
            })
        return {"statusCode": 200, "body": json.dumps({"result": result})}
    except Exception as e:
        logger.error(f"Error fetching LLMs: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"message": f"Error fetching LLMs: {str(e)}", "error": str(e)})}


def _update_llm(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event.get("queryStringParameters", {}).get("agent_int_uid", None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        event_body = json.loads(event.get("body", "{}"))
        validation_rules = {
            "llm_id": ["required", "not_blank"]
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {"statusCode": 400, "body": json.dumps({"validation_errors": validator.errors})}
        llm_id = event_body.get("llm_id")
        if not llm_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select a valid LLM Model and try again."})}
        items = _get_record_from_table({
            "table_name": "agent_privileges",
            "keys": {"agent_int_uid": agent_int_uid, "user_id": user_id},
            "gsi_name": "agent_int_uid-user_id-index"
        })
        if not items:
            return {"statusCode": 404, "body": json.dumps({"error": "No matching privilege found for this user and agent."})}
        item = items[0]
        agent_privilege_id = item.get("agent_privilege_id")
        if not agent_privilege_id:
            return {"statusCode": 500, "body": json.dumps({"error": "Privilege id is missing from Agent list."})
            }
        _update_data_in_table({"table_name": "agent_privileges",
                               "key": "agent_privilege_id",
                               "key_value": agent_privilege_id,
                               "update_data": {"llm_id": llm_id}})
        return {"statusCode": 200, "body": json.dumps({"message": "LLM ID updated successfully."})}
    except Exception as e:
        logger.error(f"Error updating LLM ID: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}