"""
Module to parse event from event bridge and trigger respective glue-job
Set environment variables with gluejobs as defined in dict below.
"""

import os
import boto3

GLUE_JOB_EVENT_MAPPING = {
    "data_quality_event": os.environ['data_quality_glue_job'],
    "feature_store_event": os.environ['feature_store_glue_job'],
    "model_monitoring_event": os.environ['model_monitoring_glue_job']
}


def lambda_handler(event, context):
    """Main Function For lambda."""

    print(event)
    glue_client = boto3.client('glue')

    if event["detail-type"] in GLUE_JOB_EVENT_MAPPING:
        response = glue_client.start_job_run(
            JobName=GLUE_JOB_EVENT_MAPPING[event["detail-type"]
                                           ], Arguments=event["detail"]
        )
    print(response)
