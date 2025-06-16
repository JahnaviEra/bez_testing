import logging, json
import boto3

dynamodb = boto3.resource('dynamodb')
agent_privileges_table = dynamodb.Table('agent_privileges')
agent_list = dynamodb.Table('agent_list')

# import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _get_persona(event):
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
        persona_results = agent_privileges_table.query(IndexName="agent_int_uid-index",
                                                       KeyConditionExpression="agent_int_uid = :ag_id",
                                                       ExpressionAttributeValues={":ag_id": agent_int_uid})
        persona = persona_results.get("Items", [])
        if not persona:
            return {"statusCode": 400, "body": json.dumps({"error": "No data found for the given agent_int_uid"})}
        agent_persona = persona[0].get("agent_persona")
        return {"statusCode": 200, "body": json.dumps({"data": agent_persona})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}


def _update_persona(event):
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
        event_body = json.loads(event.get("body", "{}"))
        new_persona = event_body.get("agent_persona")
        if not new_persona:
            return {"statusCode": 400, "body": json.dumps({"error": "No persona to update."})}
        response = agent_privileges_table.query(
            IndexName='agent_int_uid-index',
            KeyConditionExpression='agent_int_uid = :agent_int_uid',
            ExpressionAttributeValues={
                ':agent_int_uid': agent_int_uid
            }
        )
        items = response.get('Items', [])
        if not items:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent not found"})}

        primary_key = {
            'agent_privilege_id': items[0]['agent_privilege_id']
        }

        agent_privileges_table.update_item(
            Key=primary_key,
            UpdateExpression="SET agent_persona = :persona",
            ExpressionAttributeValues={":persona": new_persona}
        )
        return {"statusCode": 200, "body": json.dumps({"message": "Records updated successfully"})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}


def _reset_persona(event):
    try:
        query_params = event.get("queryStringParameters", {})
        agent_int_uid = query_params.get("agent_int_uid")
        if not agent_int_uid:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid or missing agent_int_uid."})
            }
        agent_id = agent_int_uid[:3]
        agent_result = agent_list.scan()
        agents = agent_result.get("Items", [])
        matching_agent = next((a for a in agents if a.get("agent_id") == agent_id), None)

        if not matching_agent or "agent_persona" not in matching_agent:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Agent persona not found."})
            }
        return {
            "statusCode": 200,
            "body": json.dumps({"data": matching_agent["agent_persona"]})
        }
    except Exception as e:
        logger.error("Error resetting persona", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }