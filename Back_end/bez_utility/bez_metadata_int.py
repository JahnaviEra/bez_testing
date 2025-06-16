import json, logging, boto3, re, time
from botocore.exceptions import ClientError

# import from bez resources
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
int_table = dynamodb.Table("integrations")
int_privileges_table = dynamodb.Table("int_privileges")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _check_user_access(user_id, integration_id):
    try:
        int_access=int_privileges_table.query(
            IndexName="integration_id-index",
            KeyConditionExpression="integration_id=:int_id",
            FilterExpression="user_id=:uid AND is_active=:true AND is_deleted =:false",
            ExpressionAttributeValues={
                ":int_id":integration_id,
                ":uid":str(user_id),
                ":true":True,
                ":false":False,
            }
        )
        if int_access.get("Count", 0) > 0:
            return int_access
        else:
            raise Exception(f"Function Error: User does not have access to the selected integration. Please select a new integration and try again.")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_int_id():
    try:
        int_id = _generate_uid({"n": "8"})
        logger.info(f'Int id is: {int_id}')
        int_id_exists = _check_record_exists({"table_name": "integrations", "keys": {"integration_id": int_id}, "gsi_name": ""})
        if int_id_exists:
            _get_int_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error
    logger.info(f'Unique Integration id is:{int_id}')
    return int_id

def _create_int_table_record(int_id, client_id, erp_name, int_name,user_id):
    try:
        item = {
            "integration_id": int_id,
            "client_id": client_id,
            "erp_name": erp_name,
            "integration_name": int_name,
            "is_active": True,
            "is_deleted": False,
            "created_at": str(int(time.time())),
            "created_by": str(user_id),
        }
        int_table.put_item(Item=item)
        logger.info(f"Int table record created: {item}")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _create_int_privileges(int_id, client_id, user_id):
    try:
        logger.info(f"Creating int privileges: {int_id}, {client_id}, {user_id}")
        item = {"int_privilege_id": str(int_id) + "-" + str(client_id) + "-" + str(user_id),
            "client_id": client_id,
            "integration_id": int_id, 
            "is_active": True,
            "is_deleted": False,
            "is_owner": True,
            "user_id": user_id,
            "view_int": True 
        }
        int_privileges_table.put_item(Item=item)
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _get_int_by_clientid(client_id, erp_name = 'all'):
    try:
        if erp_name == 'all':
            integrations_by_client = int_table.query(
                IndexName="client_id-index",
                KeyConditionExpression="client_id = :cl_id",
                FilterExpression="is_active = :true AND is_deleted = :false",
                ExpressionAttributeValues={
                    ":cl_id": client_id,
                    ":true": True,
                    ":false": False,
                }
            )
            return integrations_by_client
        else:
            integrations_by_client = int_table.query(
                IndexName = "client_id-index",
                KeyConditionExpression= "client_id = :cl_id",
                FilterExpression="erp_name = :erp AND is_active = :true AND is_deleted = :false",
                ExpressionAttributeValues={
                    ":cl_id": client_id,
                    ":erp": erp_name,
                    ":true": True,
                    ":false": False,
                }
            )
            return integrations_by_client
    except Exception as e:
        return e

def _get_int_by_userid(user_id, integration_id):
    try:
        int_list = int_privileges_table.query(
                IndexName = "integration_id-index",
                KeyConditionExpression= "integration_id = :int_id",
                FilterExpression="user_id = :u_id AND is_active=:true AND is_deleted =:false",
                ExpressionAttributeValues={
                    ":int_id": integration_id,
                    ":u_id": user_id,
                    ":true":True,
                    ":false":False
                }
            )
        return int_list
    except Exception as e:
        return e

def _get_int_by_intname(client_id, int_name):
    try:
        integrations_list = int_table.query(
            IndexName = "client_id-index",
            KeyConditionExpression= "client_id = :cl_id",
            FilterExpression="integration_name = :i_name",
            ExpressionAttributeValues={
                ":cl_id": client_id,
                ":i_name": int_name
            }
        )
        logger.info(f"Integrations list: {integrations_list}")
        return integrations_list
    except Exception as e:
        return e

def _get_int_list_by_clientid(client_id):
    try:
        integrations_list = int_table.query(
            IndexName = "client_id-index",
            KeyConditionExpression= "client_id = :cl_id",
            ExpressionAttributeValues={
                ":cl_id": client_id
            }
        )
        logger.info(f"Integrations list: {integrations_list}")
        return integrations_list["Items"]
    except Exception as e:
        return e

def _get_int_by_intid(integration_id):
    try:
        integration = int_table.get_item(
            Key={
                "integration_id": integration_id
            }
        )
        logger.info(f"Integration: {integration}")
        if integration.get("Item") is None:
            raise Exception(f"Function Error: Integration not found.")
        return integration["Item"]
    except Exception as e:
        raise e