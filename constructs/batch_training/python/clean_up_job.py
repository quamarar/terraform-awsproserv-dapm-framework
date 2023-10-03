
from dynamodb_util import TrainStateDataModel, TrainInputDataModel, TrainingMetaDataModel
from awsglue.utils import getResolvedOptions
from ddb_helper_functions import delete_ddb_table, fetch_all_records, delete_table_record, update_ssm_store, read_ssm_store, email_sns
from datetime import datetime
import logging
import boto3
import sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns_client = boto3.client('sns')
ssm_client = boto3.client('ssm')
cleanup_job_status = "SUCCEEDED"

def delete_ddb_table_entries(ddb_model):
    """
    :param ddb_model: Object of table
    :return: bool 
    """
    if not ddb_model.exists():
        print("DDB Table doesnt exist hence returning")
        return

    try:
        all_jobs = ddb_model.scan()
        for job in all_jobs:
            job.delete(add_version_condition=False)
    except Exception as error:
        logger.error("Error while deleting records from table- {}".format(error))
        raise Exception(
            "Error while deleting records from table- {}".format(error))
    return True


def clean_up_framework(args):
    """
    @:param args: parameters sent from environment
    :return: bool
    """
    global cleanup_job_status
    try:
        # dynamically set the table names for input, state and meta dynamoDB tables
        TrainInputDataModel.setup_model(
            TrainInputDataModel, args['train_inputtable_name'], args['region'])
        TrainStateDataModel.setup_model(
            TrainStateDataModel, args['train_statetable_name'], args['region'])
        TrainingMetaDataModel.setup_model(
            TrainingMetaDataModel, args['train_metatable_name'], args['region'])
        if TrainInputDataModel.exists():
            metaitemtemp = TrainingMetaDataModel.get("fixedlookupkey")
            email_topic_arn = metaitemtemp.email_topic_arn
            usecase_name = metaitemtemp.usecase_name
        else:
            raise Exception("TrainingMetaDataModel doesn't exist or it does not have any record")   

        
        delete_ddb_table_entries(TrainInputDataModel)
    
        all_jobs = TrainStateDataModel.scan()
        batch_client = boto3.client('batch')
        for job in all_jobs:
            if job.awsbatch_job_status_overall != "SUCCEEDED" and job.awsbatch_job_status_overall != "FAILED":
                try:
                    logger.info("Terminating AWS Btach JOBID- {}".format(job.cur_awsbatchjob_id))
                    response = batch_client.terminate_job(
                        jobId=job.cur_awsbatchjob_id,
                        reason='cleanup'
                    )
                    # ddb_helper_functions.delete_table_record(TrainStateDataModel, TrainStateDataModel.batchjob_id,
                    #                                          job.batchjob_id)
                except Exception as error:
                    logger.error(
                        f"Error to terminate job {job.cur_awsbatchjob_id} - {error}")
        delete_ddb_table_entries(TrainStateDataModel)
        delete_ddb_table_entries(TrainingMetaDataModel)
        # state_records = ddb_helper_functions.fetch_all_records(TrainStateDataModel)
        response = ssm_client.put_parameter(
            Name=args['ssm_training_complete_status'],
            Description='status complete',
            Value='False',
            Overwrite=True,
        )
        # assert (0 == len(list(input_records))), "Error in deleting records from StateTable"
        # assert (0 == len(list(all_jobs.total_count))), "Error in deleting records from InputTable"
        logger.info("Training CleanUp job Completed")
    except Exception as error:
            cleanup_job_status = "FAILED"
            logger.error("Error in training cleaning up-> {}".format(error))
        
    finally:
        today = datetime.now()
        email_subject = f"{usecase_name} Traning Status:"
        email_message = f"""Model Training  {cleanup_job_status} for {usecase_name}

         \n Year:{today.year} \n Month:{today.month} \n Day:{today.day} """

        email_sns(sns_client, email_topic_arn, email_message, email_subject)
        
        

if __name__ == '__main__':
    args = getResolvedOptions(sys.argv,
                              [
                                  'train_inputtable_name',
                                  'train_statetable_name',
                                  'train_metatable_name',
                                  'ssm_training_complete_status',
                                  'region'])
    clean_up_framework(args)
