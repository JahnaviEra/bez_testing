import json, logging

from bez_qbo_modules.bez_connect_to_qbo import _existing_connect_to_qbo, _new_connect_to_qbo, _existing_qbo_credentials, _update_qbo_credentials, _save_qbo_creds
from bez_qbo_modules.bez_qbo_expert import _qbo_expert_response
from bez_utility_qbo_expert.bez_wf_qbo_identify import _wf_qbo_identify
from bez_utility_qbo_expert.bez_wf_qbo_query_params import _wf_qbo_query_params
from bez_utility_qbo_expert.bez_wf_qbo_expert_summarize import _wf_qbo_expert_summarize,_wf_generic_response
from bez_utility.bez_utils_qbo import _qbo_create_connection, _get_qbo_query_data_with_filter, _get_qbo_report_data

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _add_headers_to_resp(data):
    data['headers'] = {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type"
                    }
    return data

def lambda_handler(event, context):
    try:
        logger.info(event)
        path = event.get("resource")
        method = event.get("httpMethod")
        function = event.get("workflow_function")
        logger.info(function)
        if path == "/connect_to_qbo" and event['queryStringParameters']["func"] == 'existing_check' and method == "GET":
            response = _existing_connect_to_qbo(event)
        elif path == "/connect_to_qbo" and event['queryStringParameters']["func"] == 'newconn_check' and method == "POST":
            response = _new_connect_to_qbo(event)
        elif path == "/save_qbo_creds"  and method == "POST":
            response = _save_qbo_creds(event)
        elif path == "/get_creds" and method == "GET":
            response = _existing_qbo_credentials(event)
        elif path == "/update_creds" and method == "POST":
            response = _update_qbo_credentials(event)
        elif path == "/qbo_expert" and method == "POST":
            response = _qbo_expert_response(event)
        elif function == "_wf_qbo_identify":
            function_response = _wf_qbo_identify(event)
        elif function == "_qbo_create_connection":
            function_response = _qbo_create_connection(event)
        elif function == "_get_qbo_query_data_with_filter":
            function_response = _get_qbo_query_data_with_filter(event)
        elif function == "_wf_qbo_query_params":
            function_response = _wf_qbo_query_params(event)
        elif function == "_wf_qbo_get_data":
            function_response = _get_qbo_report_data(event)
        elif function == "_wf_qbo_expert_summarize":
            function_response = _wf_qbo_expert_summarize(event)
        elif function == "_wf_generic_response":
            function_response = _wf_generic_response(event)
        else:
            response = {
                'statusCode': 400,
                'body': json.dumps({'error': 'This is not a valid request. Please check and try again.'})
            }
    except Exception as e:
        logger.info(e)
        response = {"error": str(e)}
    if path:
        return _add_headers_to_resp(response)
    elif function:
        return function_response