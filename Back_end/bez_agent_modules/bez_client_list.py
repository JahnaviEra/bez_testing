import json, logging

# import from bez resources
from bez_utility.bez_metadata_clients import _active_clients_by_userid
from bez_utility.bez_utils_aws import _get_record_from_table

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _client_list(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            response = {"statusCode": 400, "body": "User Id is a required field. Please re-login to try again."}
        client_list_response = _active_clients_by_userid(user_id)
        logger.info(f"Client list response: {client_list_response}")
        client_ids = [item["client_id"] for item in client_list_response.get("Items", [])]
        if not client_ids:
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No active clients found", "clients": []})
            }
        # Fetch client names one by one from clients table
        clients_data = []
        for client_id in client_ids:
            client_response = _get_record_from_table({"table_name": "clients", "keys": {"client_id": client_id}, "gsi_name": ""})
            logger.info(f"Client response: {client_response}")
            if client_response:
                clients_data.append({
                    "client_id": client_id,
                    "clientname": client_response["client_name"]
                })
        return {
            "statusCode": 200,
            "body": json.dumps({"clients": clients_data})
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error getting client list: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }