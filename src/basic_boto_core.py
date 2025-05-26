import os
import boto3
import json
from botocore.client import Config

botocore_config = Config(
    retries={
        'max_attempts': 0
    },
    read_timeout=60,
    connect_timeout=60,
    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
)

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda',config=botocore_config)
