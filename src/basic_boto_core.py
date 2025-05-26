import os
import boto3
from botocore.client import Config

botocore_config = Config(
    retries={
        'max_attempts': 0
    },
    read_timeout=120,
    connect_timeout=120,
    region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
)

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda',config=botocore_config)

res_payload = boto3_lambda_client.invoke(
    FunctionName='boto3_version_check',
    InvocationType='RequestResponse'
)['Payload']

print(res_payload.read())
