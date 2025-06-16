import json, logging, boto3, time, os
import http.client
import urllib.parse
from botocore.exceptions import ClientError

# import from bez resources
from bez_utility.bez_utils_aws import _get_record_from_table, _get_secret_value, _update_data_in_table, _write_s3

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
qb_integration_tokens_table = dynamodb.Table("qb_integration_tokens")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_secret_from_intid(integration_id):
    try:
        integration = _get_record_from_table({"table_name": "integrations", "keys": {"integration_id": integration_id}, "gsi_name": ""})
        if "secret_name" in integration:
            secret_name = integration.get('secret_name', "")
            logger.info(f"Secret_name: {secret_name}")
            return secret_name
        else:
            raise Exception("Function Error: Integration not found")
    except ClientError as e:
        raise Exception(f"Failed to get integration details: {e.response['Error']['Message']}")
    except Exception as e:
        raise Exception(f"Unexpected error getting integration details: {str(e)}")

def _get_qbo_creds_from_secret(secret_name):
    try:
        secret = _get_secret_value({"secret_name":secret_name})
        logger.info(f"Secret: {secret}")
        if "error" in secret:
            return {"error": secret["error"]}
        else:
            client_id = secret.get("client_id")
            client_secret = secret.get("client_secret")
            realm_id = secret.get("realm_id")
            sandbox = secret.get("sandbox", "false") 
            if not all([client_id, client_secret, realm_id]):
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing necessary credentials from secret value"})
                }
            logger.info(f"Client ID: {client_id}, Client Secret: {client_secret}, Realm ID: {realm_id}")
            return client_id, client_secret, realm_id, sandbox
    except ClientError as e:
        raise Exception(f"Failed to get secret: {e.response['Error']['Message']}")
    except Exception as e:
        raise Exception(f"Unexpected error getting secret: {str(e)}")

def _get_refresh_token_from_intid(integration_id):
    try:
        token_details = _get_record_from_table({"table_name": "qb_integration_tokens", "keys": {"integration_id": integration_id}, "gsi_name": ""})
        refresh_token = token_details.get("refresh_token")
        if not refresh_token:
            return {"error": "Refresh token not found in qb_integration_tokens"}
        logger.info(f"Refresh token: {refresh_token}")
        return refresh_token
    except ClientError as e:
        raise Exception(f"Failed to get refresh token: {e.response['Error']['Message']}")
    except Exception as e:
        raise Exception(f"Unexpected error getting refresh token: {str(e)}")

def _get_new_refresh_token(client_id, client_secret, refresh_token):
    try:
        base_url = "oauth.platform.intuit.com"
        path = "/oauth2/v1/tokens/bearer"
        conn = http.client.HTTPSConnection(base_url)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        params = {
            "grant_type": "refresh_token",   # Use "refresh_token" grant type
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
        body = urllib.parse.urlencode(params)
        logger.info(f"Request: {body}")
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        if "error" in data:
            raise Exception(f"Function Error: Failed to get new refresh token: {data}")
        else:
            logger.info(f"Response: {data}")
            new_refresh_token = json.loads(data).get("refresh_token")
            logger.info(f"New refresh token: {new_refresh_token}")
            access_token = json.loads(data).get("access_token")
            return new_refresh_token, access_token
    except Exception as e:
        raise e

def _save_updated_refresh_token(refresh_token, new_refresh_token, integration_id):
    try:
        if refresh_token != new_refresh_token:
            response = _update_data_in_table({"table_name": "qb_integration_tokens", 
                                            "key": "integration_id",
                                            "key_value": integration_id,
                                            "update_data": {"refresh_token": new_refresh_token, "old_refresh_token": refresh_token},
                                            "gsi_key": "",
                                            "gsi_value": ""})
            logger.info(f"Response: {response}")
        else:
            response = {"Refresh token not updated"}
            logger.info(f"Response: {response}")
        return response
    except ClientError as e:
        raise Exception(f"Failed to update refresh token: {e.response['Error']['Message']}")
    except Exception as e:
        raise Exception(f"Unexpected error updating refresh token: {str(e)}")

def _connect_to_qbo(client_id, client_secret, realm_id, sandbox, access_token):
    try:
        environment = "sandbox" if sandbox.lower() == "true" else "production"
        base_url = "sandbox-quickbooks.api.intuit.com" if environment == "sandbox" else "quickbooks.api.intuit.com"
        path = f"/v3/company/{realm_id}/companyinfo/{realm_id}"
        conn = http.client.HTTPSConnection(base_url)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        conn.request("GET", path, headers=headers)
        connection_response = conn.getresponse()
        logger.info(f"Connection response: {connection_response}")
        return connection_response
    except Exception as e:
        logger.error(f"Error connecting to QBO: {str(e)}")
        raise Exception(f"Unexpected error connecting to QBO: {str(e)}")

def _create_qbo_refresh_token_record(integration_id, user_id, session_id, refresh_token):
    try:
        item = {
            "user_id": user_id,
            "session_id": session_id,
            "integration_id": integration_id,
            "refresh_token": refresh_token,
            "created_at": str(int(time.time())),
            "updated_at": str(int(time.time()))
        }
        qb_integration_tokens_table.put_item(Item=item)
        logger.info(f"Refresh token updated in qbo_integration_tokens table.")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _qbo_create_connection(event):
    try:
        logger.info(f"Creating QBO Connection with: {event}")
        integration_id = event.get("integration_id")
        user_id = event.get("user_id")
        session_id = event.get("session_id")
        secret_name = _get_secret_from_intid(integration_id)
        client_id, client_secret, realm_id, sandbox = _get_qbo_creds_from_secret(secret_name)
        refresh_token = _get_refresh_token_from_intid(integration_id)
        new_refresh_token, access_token = _get_new_refresh_token(client_id, client_secret, refresh_token)
        _save_updated_refresh_token(refresh_token, new_refresh_token, integration_id)
        return {"realm_id": realm_id,
                "access_token": access_token,
                "sandbox": sandbox}
    except Exception as e:
        raise Exception(str(e))

def _get_qbo_query_data_with_filter(event):
    try:
        logger.info(event)
        entity = event.get("query_object")
        names = event.get("names")
        qbo_creds = event.get("qbo_creds")
        realm_id = qbo_creds.get("realm_id")
        access_token = qbo_creds.get("access_token")
        sandbox = qbo_creds.get("sandbox")
        start_position = 1
        max_results = 1000
        query_objects = {}
        st = time.time()
        base_url = "sandbox-quickbooks.api.intuit.com" if sandbox == "true" else "quickbooks.api.intuit.com"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        for name in names:
            name_dict = {}
            query = f"SELECT * FROM {entity} WHERE DisplayName LIKE '%{name}%'"
            logger.info(query)
            paginated_query = f"{query} STARTPOSITION {start_position} MAXRESULTS {max_results}"                
            params = urllib.parse.urlencode({"query": paginated_query})
            path = f"/v3/company/{realm_id}/query?{params}"
            # Make the API call
            conn = http.client.HTTPSConnection(base_url)
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            data = response.read().decode("utf-8")
            if response.status != 200:
                print(f"Error fetching {name}: {data}")
            else:
                # Parse and handle the response
                data = json.loads(data)
                entity_response = data.get("QueryResponse", {}).get(entity, [])
                logger.info(f"Entity_response for '{name}': {entity_response}")

                if len(entity_response) > 0:
                    if entity not in query_objects:
                        query_objects[entity] = []
                    for item in entity_response:
                        name_dict = {
                            "name": item.get("DisplayName"),
                            "id": item.get("Id")
                        }
                        query_objects[entity].append(name_dict)

        total_time = time.time() - st
        # Return the matched entities and time taken
        if query_objects:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "matched_entities": query_objects,
                    "time_taken_seconds": total_time
                })
            }
        else:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "time_taken_seconds": total_time
                })
            }
    except Exception as e:
        print(f"Error processing the request: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal server error str({e})"})
        }

def _get_qbo_report_data(event):
    try:
        logger.info(event)
        agent_int_uid = event.get("agent_int_uid")
        integration_id = (agent_int_uid.split('-'))[:3][1]
        execution_id = event.get("execution_id")
        params_output = event.get("params_output")
        logger.info(params_output)
        qbo_creds = event.get("qbo_creds")
        realm_id = qbo_creds.get("realm_id")
        logger.info(qbo_creds)
        access_token = qbo_creds.get("access_token")
        sandbox = qbo_creds.get("sandbox")
        logger.info(f"{realm_id}, {access_token}, {sandbox}")
        # logger.info(f"report_name {report_name}")
        start_position = 1
        max_results = 1000
        base_url = "sandbox-quickbooks.api.intuit.com" if sandbox.lower() == "true" else "quickbooks.api.intuit.com"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        logger.info(params_output)
        report_name = params_output.get("qbo_object")
        params_json = params_output.get("query_params")
        logger.info(report_name, params_json)
        if not report_name or not params_json:
            logger.warning(f"Function Error: Missing report name.")
        params = urllib.parse.urlencode(params_json) if params_json else ""
        # Construct the request path
        path = f"/v3/company/{realm_id}/reports/{report_name}"
        if params:
            path += f"?{params}"
        # Debugging output
        print(f"Request URL: https://{base_url}{path}")
        print(f"Headers: {headers}")
        # Send GET request
        conn = http.client.HTTPSConnection(base_url)
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        write_data = json.loads(data.decode("utf-8"))
        print(f"Response: {res.status} {res.reason}")
        map_index = event.get("map_index", 0)
        suffix = f"{map_index}"
        s3_key = f"{integration_id}/{execution_id}_{report_name}_{suffix}"
        s3_bucket = 'bez-dev'
        _write_s3(s3_bucket, s3_key, json.dumps(write_data))
        params_output["s3_key"] = s3_key
        params_output["map_index"]=map_index
        return params_output
    except Exception as e:
            return {"status": "Error retrieving data", "message": str(e)}