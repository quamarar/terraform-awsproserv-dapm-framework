import logging
import boto3
from inference_dynamodb_model import (InferenceStateDataModel, InferenceMetaDataModel,
                                      InferenceInputDataModel, Timelaps)
from ddb_helper_functions import delete_ddb_table, fetch_all_records, delete_table_record, update_ssm_store, read_ssm_store, email_sns
from constants import JOB_STATUS_DICT
import sys
from awsglue.utils import getResolvedOptions
from datetime import datetime


# uncomment for local development


# from model.utils.ddb_helper_functions import delete_ddb_table, fetch_all_records, delete_table_record
# from model.utils.constants import JOB_STATUS_DICT, SSM_INFERENCING_COMPLETE_STATUS
# from model.utils_inference.inference_dynamodb_model import InferenceStateDataModel, InferenceMetaDataModel, \
#     InferenceInputDataModel, Timelaps
# from awsglue.utils import getResolvedOptions
# import logging
# import boto3
# import sys


#############################
ssm_client = boto3.client('ssm')
sns_client = boto3.client('sns')
job_name = "Inference_cleanup_job"
logger = logging.getLogger()
logger.setLevel(logging.INFO)

cleanup_job_status = "SUCCEEDED"

def delete_ddb_table_entries(ddb_model):
    """
    :param ddb_model: Object of table
    :return: bool 
    """
    if not ddb_model.exists():
        logger.error("DDB Table doesnt exist hence returning")
        raise Exception("Table doesn't exist")

    try:
        all_jobs = ddb_model.scan()
        for job in all_jobs:
            job.delete(add_version_condition=False)
    except Exception as error:
        logger.error("Error while deleting records from table-{}".format(error))
        raise Exception(
            "Error while deleting records from table- {}".format(error))

    return True


def clean_up_inference_framework(args) -> bool:
    """
    @:param args: parameters sent from environment
    :return: bool
    """
    global cleanup_job_status
    try:

        InferenceInputDataModel.setup_model(
            InferenceInputDataModel, args['inference_inputtable_name'], args['region'])
        InferenceStateDataModel.setup_model(
            InferenceStateDataModel, args['inference_statetable_name'], args['region'])
        InferenceMetaDataModel.setup_model(
            InferenceMetaDataModel, args['inference_metatable_name'], args['region'])
        if InferenceInputDataModel.exists():
            
            meta_item = InferenceMetaDataModel.get("fixedlookupkey")
            email_topic_arn = meta_item.email_topic_arn
            usecase_name = meta_item.inference_usecase_name
        else:
            raise Exception("InferenceMetaDataModel doesn't exist or it does not have any record")
        
        delete_ddb_table_entries(InferenceInputDataModel)

        all_jobs = InferenceStateDataModel.scan()
        batch_client = boto3.client('batch')
        for job in all_jobs:
            if job.awsbatch_job_status_overall != JOB_STATUS_DICT["succeeded"] and job.awsbatch_job_status_overall != \
                    JOB_STATUS_DICT["failed"]:
                try:
                    logger.info("Terminating Inference AWS Batch JOBID- {}".format(job.cur_awsbatchjob_id))
                    response = batch_client.terminate_job(
                        jobId=job.cur_awsbatchjob_id,
                        reason='cleanup'
                    )
                    # delete_table_record(InferenceStateDataModel, InferenceStateDataModel.batchjob_id,
                    #                    job.batchjob_id)
                except Exception as error:
                    logger.error(
                        f"Error to terminate inference job {job.cur_awsbatchjob_id} - {error}")
                    return False
        delete_ddb_table_entries(InferenceStateDataModel)
        delete_ddb_table_entries(InferenceMetaDataModel)
        # state_records = ddb_helper_functions.fetch_all_records(InferenceStateDataModel)

        update_ssm_store(
            ssm_parameter_name=args['ssm_inferencing_complete_status'], value='False', region=args['region'])

    except Exception as error:
        cleanup_job_status = "FAILED"
        logger.error("Error in inferencing cleaning up-> {}".format(error))
        
    finally:
        today = datetime.now()
        email_subject = f"{usecase_name} Inference Status:"
        email_message = f"""Model Inference  {cleanup_job_status} for {usecase_name}\n Year:{today.year} \n Month:{today.month} \n Day:{today.day} """

        email_sns(sns_client, email_topic_arn, email_message, email_subject)

        logger.info("Inferenc CleanUp job Completed")
        


if __name__ == '__main__':
    args = getResolvedOptions(sys.argv,
                              [
                                  'inference_inputtable_name',
                                  'inference_statetable_name',
                                  'inference_metatable_name',
                                  'ssm_inferencing_complete_status',
                                  'region'])

    clean_up_inference_framework(args=args)
