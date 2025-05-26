import boto3

client_session = boto3.Session()
boto3_lambda_client = client_session.client('lambda', region_name='ap-northeast-1')

res_payload = boto3_lambda_client.invoke(
    FunctionName='boto3_version_check',
    InvocationType='RequestResponse'
)['Payload']

print(res_payload.read())
