import json, logging

# import from bez resources
from bez_utility.bez_metadata_int import _get_int_list_by_clientid, _get_int_id, _create_int_table_record, _create_int_privileges
from bez_utility.bez_validation import PayloadValidator
from bez_utility.bez_metadata_clients import _check_user_client_access, _check_client_id_exists

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _create_int(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        event_body = json.loads(event.get("body", {}))
        logger.info(f"Event body: {event_body}")

        validation_rules = {
            "client_id": ["required", "not_blank"],
            "integration_name": ["required", "not_blank", "alpha_num_length"],
            "erp_name": ["required", "choices:quickbooks"]
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        client_id = event_body.get("client_id")
        integration_name = event_body.get("integration_name").strip()
        erp_name = event_body.get("erp_name")

        client_exists = _check_client_id_exists(client_id)
        if not client_exists:
            return {"statusCode": 400, "body": json.dumps({"error":"The selected client does not exist. Please select a different client and try again."})}
        has_access = _check_user_client_access(user_id, client_id)
        if not has_access:
            return {"statusCode": 400, "body": json.dumps({"error":"You do not have permissions to access this client. Please select a different client and try again."})}
        integrations_list = _get_int_list_by_clientid(client_id)
        logger.info(f"Integrations list: {integrations_list}")
        int_name_exists = any(item.get("integration_name").lower() == integration_name.lower() for item in integrations_list)
        if int_name_exists:
            return {"statusCode": 400, "body": json.dumps({"error":"The selected integration name already exists. Please try with a unique name."})}
        int_id = _get_int_id()
        _create_int_table_record(int_id, client_id, erp_name, integration_name, user_id)
        _create_int_privileges(int_id, client_id, user_id)
        result = {"integration_id": int_id, "integration_name": integration_name}
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error creating integrations info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }