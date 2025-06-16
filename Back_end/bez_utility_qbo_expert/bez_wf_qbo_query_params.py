import logging, json, time
from datetime import datetime

# import from bez resources
from bez_utility.bez_utils_pd import _read_csv_s3
from bez_utility.bez_utils_bedrock import _get_ai_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

current_date = datetime.now()
# Extract the year
current_year = current_date.year

def _wf_qbo_query_params(event):
    try:
        logger.info(f"Received event: {event}")
        st1 = time.time()
        logger.info(f"start time: {st1}")
        s3_bucket = event["s3_bucket"]
        s3_key = event["s3_key"]
        user_prompt = event["user_prompt"]
        qbo_objects = event["objects"]
        obj_names = [o['qbo_obj_name'] for o in qbo_objects]
        query_results = event["query_results"]
        qbo_creds = event.get("qbo_creds")
        sandbox = qbo_creds.get("sandbox")
        base_url = "sandbox-quickbooks.api.intuit.com" if sandbox == "true" else "quickbooks.api.intuit.com"
        if not user_prompt or not qbo_objects:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required fields: user_input or identified_objects"})
            }
        param_rows = _read_csv_s3(s3_bucket, s3_key)
        st2 = time.time()
        t1 = st2 - st1
        logger.info(f"Time to read from S3: {t1}")
        relevant_params = [row for row in param_rows if row.get("Object") in obj_names]
        if relevant_params:
            headers = relevant_params[0].keys()
            html_table = "<table border='1'><thead><tr>"
            html_table += "".join(f"<th>{h}</th>" for h in headers)
            html_table += "</tr></thead><tbody>"
            for row in relevant_params:
                html_table += "<tr>" + "".join(f"<td>{row[h]}</td>" for h in headers) + "</tr>"
            html_table += "</tbody></table>"
        else:
            html_table = "<p>No relevant parameters found.</p>"
        st3 = time.time()
        t2 = st3 - st2
        logger.info(f"Time to filter relevant info: {t2}")
        system_instruction = """
        Introduction:
        You are an expert in generating structured QuickBooks Online API definitions for financial reports and entity queries. Based on a user's natural language query, use the provided Identified Objects list,ID's Dictionary and Parameters Table to generate the required API calls.
    
        Objective:
        Generate a complete chain of API calls to fulfill the user request, including:
        - Entity lookups (e.g., Customer by DisplayName) when needed.
        - Correct parameter extraction using exact names and allowed values from the Parameters Table.
        - Structured API definitions in execution-ready JSON-style format.
    
        Output Format:
        Return a Python dictionary where each key is a QBO object name and its value is a dictionary:
        [
            {
            "qbo_object": "QBOObjectName",
            "query_params": {
                "parameter1": "value",
                ...
                }
            }
        ]
    
        Guidelines:
        - Use only the objects listed under Identified Objects. Do not create new ones.
        - Use parameter names and allowed values exactly as listed in the Parameters Table.
        - When customer names are mentioned, perform a Customer query using DisplayName, then use the resulting Customer.Id in the report query.
        - Convert year mentions (e.g., "2022") into "start_date": "2022-01-01" and "end_date": "2022-12-31".
        - Use placeholder values like <customer_id> or <realmId> where actual IDs are available in the provided ID dictionary.
        - Do not include extra text, commentary, or explanation outside of the JSON response.
        - Maintain the order of calls — lookups must precede dependent API calls (e.g., Customer before ProfitAndLoss).
        - If the same parameter (e.g., summarize_column_by, customer, vendor) has multiple values, do not combine them in a single API call.
        - Do not Use arrays like "summarize_column_by": ["Month", "ProductsAndServices"]
        - Do not Repeat the same key multiple times in the same dictionary (this will result in invalid JSON)
        - Instead Generate separate API call definitions, one for each value.
        - Always ensure each parameter value results in a separate query block.
    """
        system_instruction +=f"""
        Note:
        - Ensure the returned dictionary reflects the proper API calling sequence.
        - Validate all parameters using the allowed values in the Parameters Table.
        - If no values are present in the user question, omit optional parameters.
        - Ensure you generate Multiple API's accordingly based on provided Query and ID dictionary.
        - Ensure you always include ID's if provided.
        - If there is no year or date mentioned in the user question then consider current year as : {current_year} and current date as {current_date}
    """
    
        # Adding the context (identified objects, parameters, and examples) to the instruction
        system_instruction+=f""" Here is the dictionary Identified Objects and types: {str(obj_names)}
        Here is the Parameters Table which contains Object name, available parameters along with its description and the Allowed values {html_table}
        Consider this as a base_url: {base_url}
        """
        logger.info(query_results)
        st4 = time.time()
        t3 = st4 - st3
        logger.info(f"Time to create prompt: {t3}")
        if query_results and len(query_results) > 0:
            system_instruction += f'''Here is the ID dictionary: {query_results}
            Ensure you always include {list(query_results.keys())} along with ID in the query_params in your response.
            If there are multiple Keys in the ID dictionary, ensure you generate multiple API Calls for each Key for each Object in your response as shown in examples.
            Generate the response as an array.'''
        system_instruction += """
        Here are some examples of how you should generate final response:
            User Question: Summarize P&L for customer 2022
            Input: {'Customer': ['1']}
            Your Response: [{
                "qbo_object": "ProfitAndLoss",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "customer": '1'
                    }
                }]       
            User Question: Summarize P&L for vendor1,vendor2 in 2022
            Input: {'Vendor': ['1','2']}
            Your Response: [
                {
                "qbo_object": "ProfitAndLoss",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "vendor": '1'
                    }
                },
                {
                    "qbo_object": "ProfitAndLoss",
                    "query_params": {
                        "start_date": "2022-01-01",
                        "end_date": "2022-12-31",
                        "vendor": '2'
                    }
                }
            ]
            User Question: Show split of revenue by product in 2022, by months in columns
            Your Response: [
                {
                "qbo_object": "ProfitAndLoss",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "summarize_column_by": "Month"
                }
                },
                {
                "qbo_object": "ProfitAndLoss",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "summarize_column_by": "ProductsAndServices"
                }
                }
            ]
            User Question: Summarize liabilities for customer1, vendor1,vendor2 in 2022
            Input: {'Customer': ['1'], 'Vendor': ['1', '2']}
            Your Response: [
                {
                "qbo_object": "BalanceSheet",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "customer": "1"
                    }
                },
                {
                "qbo_object": "BalanceSheet",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "vendor": '1'
                    }
                },
                {
                "qbo_object": "BalanceSheet",
                "query_params": {
                    "start_date": "2022-01-01",
                    "end_date": "2022-12-31",
                    "vendor": '2'
                    }
                }
            ]
        """
        st5 = time.time()
        t4 = st5 - st4
        logger.info(f"Time to add params prompt: {t4}")
        full_prompt = f"User Question: {user_prompt}\nSystem Instruction: {system_instruction}"
        ai_response = _get_ai_response({"prompt": full_prompt})
        st6 = time.time()
        t5 = st6 - st5
        logger.info(f"Time to get bedrock response: {t5}")
        response_array = json.loads(ai_response)
        for i, obj in enumerate(response_array, 1):
            obj['id'] = i
        return json.dumps(response_array)
    except Exception as e:
        logger.exception("Unexpected error occurred during API definition generation.")
        raise Exception(str(e))