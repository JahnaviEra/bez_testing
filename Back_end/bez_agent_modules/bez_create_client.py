import json, logging

# import from bez resources
from bez_utility.bez_metadata_clients import _get_client_id, _check_client_name_exists, _create_client_table_record, _create_client_privileges
from bez_utility.bez_validation import PayloadValidator
# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _create_client(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        event_body = json.loads(event.get("body", {}))
        validation_rules = {
            "client_name": ["required", "not_blank", "alpha_num"]
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
      
        logger.info(f"Event body: {event_body}")
        client_name = event_body.get("client_name").strip()
        client_name_exists = _check_client_name_exists(client_name)
        logger.info(f"Client name exists here: {client_name_exists}")
        if client_name_exists:
            return {"statusCode": 400,
                    "body": json.dumps({"error": "This client already exists. If you need access to this client's data, please contact client admin or Bez admin. Else, please proceed by creating another client."})
                    }
        else:
            client_id = _get_client_id()
            _create_client_table_record(client_id, client_name, user_id)
            _create_client_privileges(client_id, user_id)
            result = {"client_id": client_id, "client_name": client_name}
            return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error creating client: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"{str(e)}"})
            }