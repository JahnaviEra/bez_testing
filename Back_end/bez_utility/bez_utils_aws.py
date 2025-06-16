import boto3, json, logging, base64
from botocore.exceptions import BotoCoreError, ClientError
from boto3.dynamodb.conditions import Key, Attr
from botocore.config import Config

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
secrets_manager = boto3.client('secretsmanager')
s3_config = Config(
    max_pool_connections=100,
    retries={'max_attempts': 10}
)
s3 = boto3.client('s3', config=s3_config)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# DynamoDB functions
def _check_record_exists(data):
    try:
        logger.info(data)
        table_name = data.get("table_name")
        logger.info(f"Checking if record exists in table {table_name}")
        keys = data.get("keys", {})
        gsi_name = data.get("gsi_name", None)
        if not table_name or not keys:
            raise ValueError("Table name and at least one key are required.")
        table = dynamodb.Table(table_name)
        # logger.info(f"Checking if record exists in table {table_name} with {key_name} = {key_value} and gsi_name as {gsi_name}")
        if gsi_name:  # Use GSI (query)
            key_conditions = []
            expression_values = {}
            for idx, (key, value) in enumerate(keys.items()):
                key_conditions.append(f"{key} = :val{idx}")
                expression_values[f":val{idx}"] = value
            key_condition_expression = " AND ".join(key_conditions)
            response = table.query(
                IndexName=gsi_name,
                KeyConditionExpression=key_condition_expression,
                ExpressionAttributeValues=expression_values
            )
            logger.info(f"response from dynamodb with gsi_name: {response}")
            return response.get("Count", 0) > 0
        else:  # Use Primary Key (get_item)
            response = table.get_item(Key=keys)
            logger.info(f"response from dynamodb: {response}")
            return "Item" in response
    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching item: {e}")
        raise e


def _get_record_from_table(data):
    try:
        table_name = data.get("table_name")
        keys = data.get("keys", {})
        gsi_name = data.get("gsi_name", None)
        if not table_name or not keys:
            raise ValueError("Table name and at least one key are required.")
        table = dynamodb.Table(table_name)
        if gsi_name:
            key_conditions = []
            expression_values = {}
            for idx, (key, value) in enumerate(keys.items()):
                key_conditions.append(f"{key} = :val{idx}")
                expression_values[f":val{idx}"] = value
            key_condition_expression = " AND ".join(key_conditions)
            response = table.query(
                IndexName=gsi_name,
                KeyConditionExpression=key_condition_expression,
                ExpressionAttributeValues=expression_values
            )
            items = response.get("Items", [])
            return items
        else:  # Use Primary Key (get_item)
            response = table.get_item(Key=keys)
            item = response.get("Item", {})
            return item
    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching item: {e}")
        raise e


def _update_data_in_table(data):
    table_name = data.get("table_name")
    key = data.get("key")
    key_value = data.get("key_value")
    update_data = data.get("update_data")
    gsi_key = data.get("gsi_key", None)
    gsi_value = data.get("gsi_value", None)
    table = dynamodb.Table(table_name)
    try:
        # Construct the update expression
        update_expression = "SET " + ", ".join(f"#{k} = :{k}" for k in update_data.keys())
        expression_attribute_names = {f"#{k}": k for k in update_data.keys()}
        expression_attribute_values = {f":{k}": v for k, v in update_data.items()}

        # Define key condition
        key_condition = {key: key_value}
        if gsi_key and gsi_value:
            key_condition[gsi_key] = gsi_value

        # Perform the update
        response = table.update_item(
            Key=key_condition,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        return response
    except (BotoCoreError, ClientError) as e:
        print(f"Error updating item: {e}")
        raise e


def _query_dynamodb(data):
    table_name = data.get("table_name")
    query_params = data.get("query_params")
    comparison_ops = data.get("comparison_ops", None)
    filter_params = data.get("filter_params", None)
    gsi_name = data.get("gsi_name", None)
    # Initialize DynamoDB client
    table = dynamodb.Table(table_name)
    try:
        # Construct KeyConditionExpression dynamically
        key_conditions = None
        for key, value in query_params.items():
            # Apply different conditions based on comparison_ops
            if comparison_ops and key in comparison_ops:
                op = comparison_ops[key]
                if op == "gte":
                    condition = Key(key).gte(value)
                elif op == "lte":
                    condition = Key(key).lte(value)
                elif op == "begins_with":
                    condition = Key(key).begins_with(value)
                else:  # Default to equality
                    condition = Key(key).eq(value)
            else:
                condition = Key(key).eq(value)
            key_conditions = condition if key_conditions is None else key_conditions & condition
            logger.info(f"Key Conditions: {key_conditions}")
        # Construct FilterExpression (for non-key attributes)
        filter_expression = None
        if filter_params:
            for key, value in filter_params.items():
                condition = Attr(key).eq(bool(value))
                filter_expression = condition if filter_expression is None else filter_expression & condition
        logger.info(f"Filter Expression: {filter_expression}")
        # Perform the query operation
        query_args = {"KeyConditionExpression": key_conditions}
        if filter_expression:
            query_args["FilterExpression"] = filter_expression  # Apply filter if provided
        if gsi_name:
            query_args["IndexName"] = gsi_name  # Use GSI if specified
        logger.info(f"Query Args: {query_args}")
        response = table.query(**query_args)
        return response.get("Items", [])
    except Exception as e:
        print(f"Error querying DynamoDB: {str(e)}")
        raise e


# Secrets functions
def _create_secret(data):
    secret_name = data.get('secret_name', None)
    secret_value = data.get('secret_value', None)
    kwargs = {"Name": secret_name,
              "SecretString": json.dumps(secret_value),
              }
    return secrets_manager.create_secret(**kwargs)


def _get_secret_value(data):
    try:
        secret_name = data.get('secret_name', None)
        if not secret_name:
            return {"error": "Missing secret_name in event"}
        response = secrets_manager.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret_value = response['SecretString']
            try:
                return json.loads(secret_value)  # Try to return as JSON
            except json.JSONDecodeError:
                return secret_value  # Return as plain string
        else:
            decoded_binary = base64.b64decode(response['SecretBinary'])
            return decoded_binary
    except ClientError as e:
        raise e


def _send_email(subject, body, user_email, source='bez_dev@futureviewsystems.com'):
    try:
        ssm_client = boto3.client('ssm')
        primary_account_id = ssm_client.get_parameter(Name='fvs-ses-account-id')['Parameter']['Value']
        external_id = ssm_client.get_parameter(Name='bez-dev-ses-external-id')['Parameter']['Value']
        # Assume the role for the Account
        sts_client = boto3.client('sts')
        assumed_role = sts_client.assume_role(
            RoleArn=f'arn:aws:iam::{primary_account_id}:role/SESCrossAccountSendRole-BezDev',
            RoleSessionName='BezDevAdminSESSendSession', ExternalId=external_id)
        credentials = assumed_role['Credentials']
        # Instantiate the SES client with the assumed role credentials
        ses_client = boto3.client('ses', region_name='us-east-1', aws_access_key_id=credentials['AccessKeyId'],
                                  aws_secret_access_key=credentials['SecretAccessKey'],
                                  aws_session_token=credentials['SessionToken'])
        # Send the email
        response = ses_client.send_email(
            Source=source,
            Destination={'ToAddresses': [user_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body}
                }
            }
        )
        logger.info(f"OTP sent to {user_email}.")
        return True
    except ClientError as e:
        logger.info(f"Error sending email: {e.response['Error']['Message']}")
        return False


def _update_secret(data):
    secret_name = data.get('secret_name', None)
    secret_value = data.get('secret_value', None)
    kwargs = {"SecretId": secret_name,
              "SecretString": json.dumps(secret_value),
              }
    return secrets_manager.update_secret(**kwargs)


def _scan_table_with_filter(data):
    table_name = data.get("table_name")
    filter_expression = data.get("filter_expression", None)
    table = dynamodb.Table(table_name)
    all_items = []
    exclusive_start_key = None
    while True:
        scan_kwargs = {}
        if filter_expression:
            scan_kwargs['FilterExpression'] = filter_expression
        if exclusive_start_key:
            scan_kwargs['ExclusiveStartKey'] = exclusive_start_key
        response = table.scan(**scan_kwargs)
        all_items.extend(response.get('Items', []))
        exclusive_start_key = response.get('LastEvaluatedKey')
        if not exclusive_start_key:
            break
    return all_items


def _read_s3(bucket_name, object_key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')  # decode to string
        return content
    except Exception as e:
        print(f"Error: The object key '{object_key}' does not exist in bucket '{bucket_name}'.")
        raise e

def _write_s3(bucket_name, object_key, data):
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=data
        )
        return f"Data written to {object_key} in {bucket_name}"
    except Exception as e:
        raise Exception(f"Function Error {e}")

def _get_files_s3(bucket_name, folder_path):
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_path)
        objects = []
        if 'Contents' in response:
            for obj in response['Contents']:
                objects.append(obj['Key'])
        else:
            logger.info("No files found.")
        return objects
    except Exception as e:
        raise Exception("Function Error: Error listing files in S3")

def _get_presigned_url(bucket_name, key, expiresin = 3600):
    try:
        presigned_url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=expiresin
        )
        return presigned_url
    except Exception as e:
        logger.error(f"Function Error generating presigned URL: {str(e)}", exc_info=True)
        raise Exception(f"Function Error generating presigned URL: {str(e)}")