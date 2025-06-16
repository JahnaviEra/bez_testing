import logging, json
import boto3

dynamodb = boto3.resource('dynamodb')
mda_prefs_table = dynamodb.Table("agent_mda_section_report_map")

# import from bez resources
from bez_utility.bez_metadata_agents import _check_user_agent_access

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_prefs(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        preferences_result = mda_prefs_table.query(IndexName="agent_int_uid-index",
                                       KeyConditionExpression= "agent_int_uid = :ag_id",
                                       ExpressionAttributeValues = {":ag_id": agent_int_uid})
        preferences = preferences_result.get("Items", [])
        if not preferences:
            return {"statusCode": 400, "body": json.dumps({"error": "No data found for the given agent_int_uid"})}
        default_prefs = []
        for preference in preferences:
            default_prefs.append({
                "section_order": str(preference.get("section_order")),
                "mda_section": preference.get("section_title"),
                "report_data": preference.get("report_data"),
                "instruction": preference.get("instruction")})
        logger.info(default_prefs)
        return {"statusCode": 200, "body": json.dumps({"data": default_prefs})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}

def _update_prefs(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        agent_int_uid = event['queryStringParameters'].get('agent_int_uid', None)
        if not agent_int_uid:
            return {"statusCode": 400, "body": json.dumps({"error": "Agent selection is required to proceed. Please select an agent to continue."})}
        user_access = _check_user_agent_access(user_id, agent_int_uid)
        event_body = json.loads(event.get("body", "{}"))
        preferences = event_body.get("prefs", [])
        logger.info(preferences)
        if not preferences:
            return {"statusCode": 400, "body": json.dumps({"error": "No report preferences to update."})}
        prefix_to_match = agent_int_uid
        existing = mda_prefs_table.scan(FilterExpression=boto3.dynamodb.conditions.Attr('pk').begins_with(prefix_to_match),
                                        ProjectionExpression='pk')
        items_to_delete = existing['Items']
        with mda_prefs_table.batch_writer() as batch:
            for item in items_to_delete:
                batch.delete_item(Key={'pk': item['pk']})
        next_section_id = 1
        for preference in preferences:
            print(preference)
            item = {
                "agent_int_uid_secid": f"{agent_int_uid}-{next_section_id}",
                "agent_int_uid": agent_int_uid,
                "instruction": preference["instruction"],
                "report_data": preference.get("report_data"),
                "section_title":preference.get("mda_section"),
                "section_order": preference["section_order"]
            }
            mda_prefs_table.put_item(Item=item)
            next_section_id += 1
        return {"statusCode": 200, "body": json.dumps({"message": "Records inserted successfully"})}
    except Exception as e:
        if "Function Error:" in str(e):
            error_message = str(e)[str(e).find("Function Error:") + len("Function Error: "):]
            logger.warning(f"Client error when fetching agent profile: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"error": error_message})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": f"{str(e)}"})}