import json, logging

# import from bez resources
from bez_utility.bez_utils_aws import _get_record_from_table
from bez_utility.bez_metadata_int import _get_int_by_clientid, _get_int_by_userid
from bez_utility.bez_metadata_clients import _check_user_client_access,_check_client_id_exists, _active_clients_by_userid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _int_list_by_client(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        client_id = event['queryStringParameters']['client_id']
        if not client_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Please select a client and try again."})}        
        client = _get_record_from_table({"table_name": "clients", "keys": {"client_id": client_id}, "gsi_name": ""})
        logger.info(f"client: {client}")      
        erp = event['queryStringParameters']['erp']
        if erp == "qb":
            erp_name = "quickbooks"
        else:
            erp_name = erp
        client_exists = _check_client_id_exists(client_id)
        if not client_exists:
            return {"statusCode": 400, "body": json.dumps({"error":"The selected client does not exist. Please select a different client and try again."})}        
        has_access = _check_user_client_access(user_id, client_id)
        if not has_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this client. Please select a different client and try again."})}
        integrations_by_client = _get_int_by_clientid(client_id, erp_name)
        integrations = [{"integration_id": item["integration_id"], "integration_name": item["integration_name"]} for item in integrations_by_client.get("Items", [])]
        logger.info(f"integrations: {integrations}")
        #Check permissions of the user on the integrations 
        integrations_data = [] 
        if integrations: 
            for integration in integrations:
                include_integration = _get_int_by_userid(user_id, integration["integration_id"])                                                                        
                selected_integrations = include_integration.get('Items', [])
                if selected_integrations:
                    integrations_data.append({
                    "integration_id": integration["integration_id"],
                    "integration_name": integration["integration_name"]
                    })
            logger.info(f"integrations_data: {integrations_data}")        
        if integrations_data:
            response = {"data": integrations_data}
        else:
            response = {"message": "No active Integrations found for the selected client.", "data": []}
        return {
            "statusCode": 200,
            "body": json.dumps(response)
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

def _int_count_by_user(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body": json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        query_string = event.get("queryStringParameters",{})
        erp = query_string.get("erp","all")
        if erp == None:
            erp_name = 'all'
        elif erp == "qb":
            erp_name = "quickbooks"
        else:
            erp_name = erp
        client_data = _active_clients_by_userid(user_id)["Items"]
        clients = [item['client_id'] for item in client_data]
        if not clients:
            response = {'message':'No active connections for this user.'}
            return {
                "statusCode": 200,
                "body": json.dumps(response)
            }
        logger.info(f"Clients: {clients}")
        integrations_count = 0
        for client in clients:
            integrations_by_client = _get_int_by_clientid(client, erp_name)["Items"]
            logger.info(integrations_by_client)
            integrations_count += len(integrations_by_client)
        if integrations_count > 0:
            response = {'message':'The selected user has active connections'}
        else:
            response = {'message':'No active connections for this user.'}
        return {
            "statusCode": 200,
            "body": json.dumps(response)
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