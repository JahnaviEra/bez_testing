import json, logging
from botocore.exceptions import ClientError

# import from bez resources
from bez_utility.bez_utils_qbo import _get_secret_from_intid, _get_qbo_creds_from_secret, _get_refresh_token_from_intid, _get_new_refresh_token, _save_updated_refresh_token, _connect_to_qbo, _create_qbo_refresh_token_record
from bez_utility.bez_metadata_int import _get_int_by_intid, _check_user_access
from bez_utility.bez_utils_aws import _update_secret, _get_secret_value, _create_secret, _update_data_in_table
from bez_utility.bez_validation import PayloadValidator

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _existing_qbo_credentials(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body":  json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        integration_id = event['queryStringParameters'].get("integration_id")
        logger.info(f"Integration ID: {integration_id}")
        if not integration_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Integration Id is a required. Please select an integration and try again."})}
        # check if integration id is valid before checking user access
        integration = _get_int_by_intid(integration_id)

        # raise exception if user does not have access to the integration
        user_access = _check_user_access(user_id, integration_id)
        secret_name = _get_secret_from_intid(integration_id)
        logger.info(f"Secret Name: {secret_name}")
        # Get the credentials from the secret manager
        client_id, client_secret, realm_id, sandbox = _get_qbo_creds_from_secret(secret_name)
        logger.info("Fetched client credentials successfully.")
        # Get the refresh token from the integration ID
        refresh_token = _get_refresh_token_from_intid(integration_id)
        logger.info("Fetched refresh token successfully.")
        result = {"qbo": {"client_id": client_id,
            "client_secret": client_secret,
            "realm_id": realm_id,
            "sandbox": sandbox,
            "refresh_token": refresh_token}}
        # Return all values
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    except Exception as e:
        logger.error(f"Unexpected error while fetching QBO credentials: {e}")
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)}),}

def _existing_connect_to_qbo(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body":  json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        integration_id = event['queryStringParameters']["integration_id"]
        logger.info(f"Integration ID: {integration_id}")
        if not integration_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Integration Id is a required. Please select an integration and try again."})}
        integration = _get_int_by_intid(integration_id)
        user_access = _check_user_access(user_id, integration_id)
        secret_name = _get_secret_from_intid(integration_id)
        client_id, client_secret, realm_id, sandbox = _get_qbo_creds_from_secret(secret_name)
        refresh_token = _get_refresh_token_from_intid(integration_id)
        new_refresh_token, access_token = _get_new_refresh_token(client_id, client_secret, refresh_token)
        update_status = _save_updated_refresh_token(refresh_token, new_refresh_token, integration_id)
        connection_response = _connect_to_qbo(client_id, client_secret, realm_id, sandbox, access_token)
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Successfully connected to QuickBooks.",
                                "refresh_token": new_refresh_token})
        }
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)}),}

def _new_connect_to_qbo(event):
    try:
        logger.info(f"Received event: {event}")
        event_body = json.loads(event.get("body", {}))
        logger.info(f"Event body: {event_body}")
        validation_rules = {
            "client_id": ["required", "not_blank"],
            "client_secret": ["required", "not_blank"],
            "realm_id": ["required", "not_blank"],
            "refresh_token": ["required", "not_blank"]
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        client_id = event_body.get("client_id")
        client_secret = event_body.get("client_secret")
        realm_id = event_body.get("realm_id")
        refresh_token = event_body.get("refresh_token")
        sandbox = event_body.get("sandbox", "false")
        logger.info(f"Client ID: {client_id}, Client Secret: {client_secret}, Realm ID: {realm_id}, Refresh Token: {refresh_token}")

        # Attempt to get a new refresh token and connect to QuickBooks
        try:
            new_refresh_token, access_token = _get_new_refresh_token(client_id, client_secret, refresh_token)
            connection_response = _connect_to_qbo(client_id, client_secret, realm_id, sandbox, access_token)

            if connection_response.status == 200:
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "Successfully connected to QuickBooks.",
                                        "refresh_token": new_refresh_token})
                }
            else:
                raise Exception("Function Error: Invalid QuickBooks credentials")
        except Exception as e:
            logger.error(f"Error during QuickBooks connection: {str(e)}")
            raise Exception("Function Error: Provided QuickBooks credentials are invalid. Please check and try again.")

    except ClientError as e:
        logger.error(f"AWS ClientError: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "AWS ClientError occurred", "details": str(e)})}
    except Exception as e:
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)}),}

def _update_qbo_credentials(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        if not user_id:
            return {"statusCode": 400, "body":  json.dumps({"error": "User Id is a required field. Please re-login to try again."})}
        event_body = json.loads(event.get("body", {}))
        validation_rules = {
            "client_id": ["required", "not_blank"],
            "client_secret": ["required", "not_blank"],
            "realm_id": ["required", "not_blank"],
            "refresh_token": ["required", "not_blank"],
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        integration_id = event['queryStringParameters'].get("integration_id")
        if not integration_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Integration Id is a required. Please select an integration and try again."})}
        logger.info(f"Integration ID: {integration_id}")
        integration_record = _get_int_by_intid(integration_id)
        user_access = _check_user_access(user_id, integration_id)
        client_id = event_body.get("client_id")
        client_secret = event_body.get("client_secret")
        refresh_token = event_body.get("refresh_token")
        realm_id = event_body.get("realm_id")
        sandbox = event_body.get("sandbox", "false")
        env = event.get("headers").get("env", "dev")
        logger.info(f"Integration ID: {integration_id}, Client ID: {client_id}, Client Secret: {client_secret}, Refresh Token: {refresh_token}, Realm ID: {realm_id}, Sandbox: {sandbox}, Environment: {env}")
        try:
            new_refresh_token, access_token = _get_new_refresh_token(client_id, client_secret, refresh_token)
            update_status = _save_updated_refresh_token(refresh_token, new_refresh_token, integration_id)
            logger.info("Refresh token and access token updated successfully.")
            response = _connect_to_qbo(client_id, client_secret, realm_id, sandbox, access_token)
            if response.status != 200:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Failed to connect to QBO with provided credentials. Please check the credentials and try again."})
                }
        except Exception as e:
            raise e
        logger.info("QBO credentials verified successfully.")
        # Fetch client_id from integrations table
        # integration_record fetched  before checking user access
        logger.info(f'Fetching client ID from integrations table: {"client_id" not in integration_record}')
        if not integration_record or "client_id" not in integration_record:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "The selected integration is not associated with any client. Please recheck and try again."})
            }
        client_id_from_db = integration_record["client_id"]
        logger.info(f"Client ID from DB: {client_id_from_db}")
        secret_name = f"bez_{env}/{client_id_from_db}/{integration_id}"
        secret_value = {
            "client_id": client_id,
            "client_secret": client_secret,
            "realm_id": realm_id,
            "sandbox": sandbox,
        }
        # Check if secret already exists
        try:
            existing_secret = _get_secret_value({"secret_name": secret_name})
        except Exception as e:
            existing_secret = {"error": str(e)}
        if "error" in existing_secret:
            # Create the secret
            logger.info(f"Secret not found, creating new secret: {secret_name}")
            _create_secret({"secret_name": secret_name, "secret_value": secret_value})
            logger.info("Secret successfully created.")
        else:
            # Update the existing secret
            logger.info(f"Secret found, updating secret: {secret_name}")
            _update_secret({"secret_name": secret_name, "secret_value": secret_value})
            logger.info("Secret successfully updated.")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "QBO credentials verified and updated successfully."})
        }
    except ClientError as e:
        logger.error(f"AWS ClientError: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "AWS ClientError", "details": str(e)})
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)}),}


def _save_qbo_creds(event):
    try:
        logger.info(f"Received event: {event}")
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("user_id", None)
        session_id = event.get("requestContext", {}).get("authorizer", {}).get("session_id", None)
        event_body = json.loads(event.get("body", {}))
        logger.info(f"Event body: {event_body}")
        integration_id = event['queryStringParameters'].get("integration_id")
        if not integration_id:
            return {"statusCode": 400, "body": json.dumps({"error": "Integration Id is a required. Please select an integration and try again."})}

        validation_rules = {
            "client_id": ["required", "not_blank"],
            "client_secret": ["required", "not_blank"],
            "realm_id": ["required", "not_blank"],
            "refresh_token": ["required", "not_blank"],
        }
        validator = PayloadValidator(event_body, validation_rules)
        if not validator.is_valid():
            return {
                "statusCode": 400,
                "body": json.dumps({"validation_errors": validator.errors})
            }
        qbo_client_id = event_body.get('client_id')
        client_secret = event_body.get('client_secret')
        refresh_token = event_body.get('refresh_token')
        realm_id = event_body.get('realm_id')
        sandbox = event_body.get("sandbox", "false")
        env = event.get("headers", {}).get("env", "dev")
        integration = _get_int_by_intid(integration_id)
        user_access = _check_user_access(user_id, integration_id)
        try:
            new_refresh_token, access_token = _get_new_refresh_token(qbo_client_id, client_secret, refresh_token)
            response = _connect_to_qbo(qbo_client_id, client_secret, realm_id, sandbox, access_token)
            if response.status != 200:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Quickbooks credentials are invalid. Please check the credentials and try again."})
                }             
        except Exception as e:
            raise e
        logger.info("QBO credentials verified successfully.")
        client_id = integration['client_id']
        logger.info(f"Client ID: {client_id}")
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
        logger.error(f"Unexpected error: {str(e)}")
        if "Function Error:" in str(e):
            return {"statusCode": 400, "body": json.dumps({"error": str(e)[len("Function Error: "):]})}
        else:
            logger.error(f"Error fetching agent info: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"message": f"Error fetching agent info: {str(e)}", "error": str(e)})}