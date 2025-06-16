import json, logging

# import from bez resources
from bez_utility.bez_metadata_int import _get_int_by_intid, _check_user_access
from bez_utility.bez_utils_aws import _create_secret, _update_data_in_table
from bez_utility.bez_utils_qbo import _create_qbo_refresh_token_record
from bez_utility.bez_metadata_clients import _check_user_client_access

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _save_qbo_creds(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        event_body = json.loads(event.get("body", {}))
        logger.info(f"Event body: {event_body}")
        integration_id = event_body.get("integration_id")
        qbo_client_id = event_body.get("qbo_creds").get('client_id')
        client_secret = event_body.get("qbo_creds").get('client_secret')
        refresh_token = event_body.get("qbo_creds").get('refresh_token')
        realm_id = event_body.get("qbo_creds").get('realm_id')
        sandbox = event_body.get("qbo_creds").get("sandbox", "false")
        env = event.get("headers", {}).get("env", "dev")
        if not all([integration_id, qbo_client_id, client_secret, realm_id, refresh_token]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Some key fields are missing in the input. Please check and try again."})
            }
        integration = _get_int_by_intid(integration_id)
        client_id = integration['Item']['client_id']
        logger.info(f"Client ID: {client_id}")
        client_access = _check_user_client_access(user_id, client_id)
        if not client_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this client. Please select a different client and try again."})}
        int_access = _check_user_access(user_id, integration_id)
        if not int_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this integration. Please select a different client and try again."})}
        secret_name = f"bez_{env}/{str(client_id)}/{str(integration_id)}"
        logger.info(f"Secret name: {secret_name}")
        secret_value = {
            "client_id": qbo_client_id,
            "client_secret": client_secret,
            "realm_id": realm_id,
            "sandbox": sandbox
        }
        _create_secret({"secret_name": secret_name, "secret_value": secret_value})
        _update_data_in_table({"table_name": "integrations", "key": "integration_id",
                                "key_value": str(integration_id),
                                "update_data": {"secret_name": secret_name}})
        _create_qbo_refresh_token_record(integration_id, user_id, session_id, refresh_token)
        return {"statusCode": 200, "body": json.dumps({"message": "Credentials saved successfully"})}
    except Exception as e:
        raise e