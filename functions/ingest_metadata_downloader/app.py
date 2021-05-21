import os

import requests
import boto3
import sys
from datetime import datetime


def lambda_handler(event, context):
    print(f'Debug: event: {event}')

    cellar_id = event['cellarId']
    print(f'Downloading notice with cellar {cellar_id}')

    try:
        url = f'{get_endpoints()["notice"]}/download-notice.html?legalContentId=cellar:' \
              f'{cellar_id}&noticeType=branch&callingUrl=&lng=EN'
        print(f'Querying for notice: {url}')
        response = requests.get(url)
        if response.status_code == 200:
            print('Notice was downloaded successfully')
            upload_content(response.content, cellar_id)
            save_record(cellar_id)

        event['downloaded'] = True
    except Exception as e:
        error = sys.exc_info()[2]
        print(f'Error while downloading {error}, {e}')
        event['error'] = error
        event['downloaded'] = False

    return event


def upload_content(content: str, cellar_id: str):
    """
    This function downloads the notice from EurLex and uploads it to S3
    """
    s3_client = boto3.client('s3', endpoint_url=get_endpoints()['aws'])
    object_key = f'notice_{cellar_id}.xml'
    bucket_name = get_s3_bucket_name()
    existing_objects = s3_client.list_objects(Bucket=bucket_name, Prefix=object_key)

    if 'Contents' in existing_objects:
        print('Object with a given name already exists, to be removed')
        for item in existing_objects['Contents']:
            remove_key = item['Key']
            print(f'Removing {remove_key} from bucket {bucket_name}')
            s3_client.delete_object(Bucket=bucket_name, Key=remove_key)

    s3_client.put_object(Bucket=bucket_name, Key=object_key, Body=content)
    print(f'Object {object_key} was uploaded to bucket {bucket_name}')


def save_record(cellar_id: str):
    """
    This function creates a record in the DynamoDB about a downloaded notice
    """
    dynamo_client = boto3.client('dynamodb', endpoint_url=get_endpoints()['aws'])
    dynamo_table = get_dyname_table_name()
    current_date = datetime.now()
    dynamo_client.put_item(TableName=dynamo_table, Item={
        'cellarId': {
            'S': cellar_id
        },
        'created': {
            'S': current_date.strftime('%m/%d/%y %H:%M:%S')
        }
    })
    print(f'Item with cellar {cellar_id} created')


def get_s3_bucket_name() -> str:
    """
    Returns the name of bucket to store downloaded notices
    """
    return os.getenv('INGEST_S3_BUCKET_NAME', 'notices-bucket')


def get_dyname_table_name() -> str:
    """
    Returns the name of the DynamoDB table to store information about downloaded notices
    """
    return os.getenv('INGEST_DYNAMODB_TABLE_NAME', 'eurlex_documents')


def get_endpoints():
    """
    Returns Localstack url for CI tests else None
    """
    aws_endpoint = None if os.getenv("LOCALSTACK_HOSTNAME") is None \
        else f'http://{os.getenv("LOCALSTACK_HOSTNAME")}:4566'
    notice_download_host = "https://eur-lex.europa.eu"

    return {"aws": aws_endpoint, "notice": notice_download_host}


if __name__ == '__main__':
    event = {
        'cellarId': 'a14bb485-038c-11eb-a511-01aa75ed71a1'
    }
    lambda_handler(event, {})
