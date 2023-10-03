import json
import boto3
import os
import logging
from datetime import datetime
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)


def lambda_handler(event, context):

    print(event)
    region = event["region"]

    ssm_client = boto3.client('ssm', region_name=region)
    custom_meta_data = event['detail']['CustomerMetadataProperties']

    # updating model prefix path and winning algo in SSM parameter
    update_ssm_params(ssm_client, approved_model_prefix_path=custom_meta_data["winningalgos3uri"],
                      winner_algorithm=custom_meta_data["winning_algo"])

    print("Done!!")


def update_ssm_params(ssm_client, **ssm_meta_data):
    try:
        for param, value in ssm_meta_data.items():
            ssm_path = os.environ[param]
            ssm_client.put_parameter(
                Name=ssm_path,
                Description='updated from lambda function',
                Value=value,
                Overwrite=True
            )
    except Exception as error:
        logging.error("Error->".format(error))
        return False
    return True


def read_ssm_param(ssm_parameter_name, ssm_client) -> dict:
    logging.info("fetch ssm parameter value- {}".format(ssm_parameter_name))

    response = ssm_client.get_parameter(
        Name=ssm_parameter_name,

    )
    return json.loads(response['Parameter']['Value'])
