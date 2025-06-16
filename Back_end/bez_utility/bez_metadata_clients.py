import json, logging, boto3, re, string
from botocore.exceptions import ClientError
import time
# import from bez resources
from bez_utility.bez_utils_common import _generate_uid
from bez_utility.bez_utils_aws import _check_record_exists, _scan_table_with_filter
from boto3.dynamodb.conditions import Attr

# Initialize resources
dynamodb = boto3.resource('dynamodb')

# Calling resources
clients_table = dynamodb.Table("clients")
clients_privileges_table = dynamodb.Table("client_privileges")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _get_client_id():
    try:
        client_id = _generate_uid({"n": "8"})
        print('Client id is:', client_id)
        client_id_exists = _check_record_exists({"table_name": "clients", "keys": {"client_id": client_id}, "gsi_name": ""})
        # print('User Exists:', user_id_exists)
        if client_id_exists:
            _get_client_id()
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise Exception(error)
    logger.info(f'Unique Client id is:{client_id}')
    return client_id

def _make_short_name(client_name):
        common_terms = r'\b(The|Inc|LLC|Incorporated|Enterprises?|Services?|Ltd|Limited|Group|Management|' \
                    r'Capital|Partners|Associates|Company|Co|Ltd|Corp|Corporation|First|New|Of|And|Or|' \
                    r'Solutions|Investments?|Construction|Consulting|House|Properties|International|' \
                    r'Trading|Design|Media|Systems|Engineering|Road|Energy|Financial|Holdings?|Health|' \
                    r'Insurance|Foods|General|Resources?|American?|United|Communications|Stores?|Automotive|' \
                    r'Data|Industry|Industries|Intl)\b'
        single_char_words = r'\bS\b'
        if not re.match(r'^[a-z0-9]+$', client_name, flags=re.IGNORECASE):
            short_name = re.sub(common_terms, '', client_name, flags=re.IGNORECASE)
        else:
            short_name = client_name
        short_name = re.sub(single_char_words, '', short_name, flags=re.IGNORECASE)
        short_name = short_name.lower().split()[:2]
        short_name = ''.join(short_name)
        if len(short_name) < 2:
            short_name = client_name.lower()
        short_name = re.sub(r'[^a-z0-9]', '', short_name)
        return short_name
 

def _check_client_name_short_exists(short_name):
    try:
        short_name_exists = _check_record_exists({"table_name": "clients", "keys": {"client_short_name": short_name}, "gsi_name": "client_short_name-index"})
        if short_name_exists:
            system = short_name.rstrip(string.digits)
            sequence = short_name[len(system):]
            if not sequence:
                sequence = '1'
            else:
                sequence = int(sequence) + 1
            short_name = f'{system}{sequence}'
            short_name = _check_client_name_short_exists(short_name)
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise Exception(error)
    return short_name
    

def _create_client_table_record(client_id, client_name, user_id):
    try:
        client_short_name = _check_client_name_short_exists(_make_short_name(client_name))
        item = {
            "client_id": client_id,
            "client_name": client_name,
            "client_name_lower": client_name.lower(),
            "client_short_name": client_short_name,
            "is_active": True,
            "is_authorized": False,
            "is_deleted": False,
            "created_at": str(int(time.time())),
            "created_by": str(user_id),
        }
        clients_table.put_item(Item=item)
        logger.info(f"Client table record created: {item}")
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _create_client_privileges(client_id, user_id):
    try:
        logger.info(f"Creating client privileges: {client_id}, {user_id}")
        item = {"client_privilege_id": str(client_id) + "-" + str(user_id),
            "add_int": True,
            "allowed_actions": "",
            "client_id": client_id,
            "is_active": True,
            "is_deleted": False,
            "is_owner": True,
            "manage_users": True,
            "modify_client": True,
            "user_id": user_id,
            "view_client": True,
            "created_at": str(int(time.time())),
            "created_by": str(user_id),
        }
        clients_privileges_table.put_item(Item=item)
    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise error

def _check_client_name_exists(client_name):
    try:
        logger.info(f"Checking client name exists: {client_name}")
        client_name_exists = _check_record_exists({"table_name": "clients", "keys": {"client_name_lower": client_name.lower()}, "gsi_name": "client_name_lower-index"})
        logger.info(f"Client name exists: {client_name_exists}")
        return client_name_exists            
    except Exception as e:
        raise e

def _check_client_id_exists(client_id):
    try:
        logger.info(f"Checking client id exists: {client_id}")
        client_id_exists = _check_record_exists({"table_name": "clients", "keys": {"client_id": client_id}})
        logger.info(f"Client id exists: {client_id_exists}")
        return client_id_exists            
    except Exception as e:
        raise e

def _get_all_client():
    try:
        filters = Attr('is_active').eq(True) & Attr('is_deleted').eq(False)
        return _scan_table_with_filter({"table_name": "clients", "filters": filters})            
    except Exception as e:
        raise e


def _check_user_client_access(user_id,client_id):
    try:
        client_access=clients_privileges_table.query(
            IndexName="user_id-index",
            KeyConditionExpression="user_id=:uid",
            FilterExpression="client_id=:cid AND is_active=:true AND is_deleted =:false",
            ExpressionAttributeValues={
                ":uid":user_id,
                ":cid":client_id,
                ":true":True,
                ":false":False,
            }
        )
        return client_access.get("Count", 0) > 0
    except Exception as e:
        return e

def _active_clients_by_userid(user_id):
    try:
        active_clients = clients_privileges_table.query(
            IndexName = "user_id-index",
            KeyConditionExpression="user_id = :uid",
            FilterExpression="is_active = :true AND is_deleted = :false",
            ExpressionAttributeValues={
                ":uid": user_id,
                ":true": True,
                ":false": False,
            }
        )
        return active_clients
    except Exception as e:
        raise e

def _get_client_by_clientid(client_id):
    try:
        client = clients_table.get_item(
            Key={
                "client_id": client_id
            }
        )
        logger.info(f"client: {client}")
        if client.get("Item") is None:
            raise Exception(f"Function Error: Client not found.")
        return client["Item"]
    except Exception as e:
        raise e