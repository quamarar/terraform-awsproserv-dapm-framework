import logging
import sys
import time
import boto3

from constants import JOB_STATUS_DICT
from inference_dynamodb_model import (InferenceStateDataModel, InferenceMetaDataModel,
                                      InferenceInputDataModel, Timelaps)
from ddb_helper_functions import (submit_aws_batch_job, delete_table_record, get_job_logstream,
                                  delete_folder_from_s3, get_aws_job_status_and_compute_requirement,
                                  dump_data_to_s3, submit_inference_aws_batch_job,extract_hash_from_string)
from awsglue.utils import getResolvedOptions
import traceback


job_name = "Inference_aws_batchj_job_status_check"
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def reupdate_inference_job_state_table_onjobsubmission(batchjob_id, cur_batchjob_id, rerun_batchjob_id,
                                                       batch_job_status_overall, num_runs, recursive_runs=0
                                                       ) -> int:
    """
    :param cur_batchjob_id:
    :param batchjob_id: haskey for the record to update
    :param rerun_batchjob_id: on submitting job a jobid is returned and for second time re-run try
    :param batch_job_status_overall: status changes  SUBMITTED on re-run
    :param num_runs: default is 1 and auto increments by 1
    :return: exit code
    """

    try:
        item = InferenceStateDataModel.get(hash_key=batchjob_id)
        logger.info(
            "Updating JOBID- {} record on resumission of failed job-".format(batchjob_id))
        item.cur_awsbatchjob_id = cur_batchjob_id
        item.rerun_awsbatchjob_id = rerun_batchjob_id
        item.num_runs = num_runs + 1
        item.awsbatch_job_status_overall = batch_job_status_overall
        item.save()

    except Exception as error:
        logging.error("Error: {}".format(error))
        if recursive_runs == 3:
            time.sleep(2)
            return False
        logging.error(
            " Retrying in reupdate_train_job_state_table_onjobsubmission recursive_runs {}".format(recursive_runs))
        reupdate_inference_job_state_table_onjobsubmission(batchjob_id, cur_batchjob_id, rerun_batchjob_id,
                                                           batch_job_status_overall, num_runs, recursive_runs + 1)
    return True


def status_update_inference_job_state_table(batchjob_id, batch_job_status_overall, num_recursive_calls=0):
    """
    :param batchjob_id: haskey for the record to update
    :param batch_job_status_overall
    :return: exit code
    """

    try:
        item = InferenceStateDataModel.get(hash_key=batchjob_id)
        logger.info(
            "Updating JOBID- {} status in StateTable".format(batchjob_id))
        item.awsbatch_job_status_overall = batch_job_status_overall
        item.save()

    except Exception as error:
        logging.error("Error: {}".format(error))
        logging.info(
            "Retrying in status_update_train_job_state_table with num_recursive_calls: {}".format(num_recursive_calls))
        if num_recursive_calls == 3:
            raise Exception(
                "status_update_train_job_state_table dynamoDB threw an Exception")
        time.sleep(2)
        status_update_inference_job_state_table(
            batchjob_id, batch_job_status_overall, num_recursive_calls + 1)


def submit_failed_job_inference_state_table(batch_job_state, batch_client, **kwargs):
    """
    Method submit to AWS Batch job queue for RE-RUN and update TrainState DDB Table
    @:param job:
    @:param batch_client:
    :return: Returns exit code otherwise exception
    """
    logger.info(
        "submitting failed job - {}".format(batch_job_state.cur_awsbatchjob_id))
    metaitemtemp = InferenceMetaDataModel.get("fixedlookupkey")
    aws_batch_job_name = metaitemtemp.aws_batch_job_prefixname
    aws_batch_job_queue = metaitemtemp.aws_batch_job_queue
    aws_batch_job_def = metaitemtemp.aws_batch_job_definition
    logger.info(
        f"Deleting marker :{kwargs['marker']} from bucket : {kwargs['bucket']}")
    delete_folder_from_s3(boto_s3_resource=kwargs["s3_resource"],
                          bucket=kwargs["bucket"], marker=kwargs["marker"])
        
    state_machine_id = extract_hash_from_string(batch_job_state.inference_step_job_id)

    unique_batch_job_name = """{}_{}_{}_{}""".format(aws_batch_job_name, state_machine_id, batch_job_state.pk,
                                                     batch_job_state.mapping_id)
                                                     

    status, batch_job_id, _ = submit_inference_aws_batch_job(
        batch_client,
        s3_inferencing_prefix_input_path=batch_job_state.s3_pk_mappingid_data_input_path,
        s3_inferencing_prefix_output_path=batch_job_state.s3_inference_prefix_output_path,
        inference_metatable_name=metaitemtemp.inference_metatable_name,
        mapping_id=batch_job_state.mapping_id,
        s3_approved_model_prefix_path=batch_job_state.s3_pk_mapping_model_prefix_input_path,
        pk_id=batch_job_state.pk, region=args['region'],
        aws_batch_job_name=unique_batch_job_name,
        aws_batch_job_queue=aws_batch_job_queue,
        aws_batch_job_definition=aws_batch_job_def,
        aws_batch_compute_scale_factor=2,
        job_id=batch_job_state.cur_awsbatchjob_id

    )

    reupdate_inference_job_state_table_onjobsubmission(batchjob_id=batch_job_state.batchjob_id,
                                                       cur_batchjob_id=batch_job_id,
                                                       rerun_batchjob_id=batch_job_id,
                                                       batch_job_status_overall="SUBMITTED",
                                                       num_runs=batch_job_state.num_runs)


def resubmit_batch_jobs(batch_job_state, batch_client, s3_resource):
    delete_subfolder = str(
        batch_job_state.s3_inference_prefix_output_path).replace("s3://", "")
    bucket_name = delete_subfolder.split("/")[0]
    marker_path = "/".join(delete_subfolder.split('/')[1:-2])

    submit_failed_job_inference_state_table(batch_job_state=batch_job_state, batch_client=batch_client,
                                            s3_resource=s3_resource, bucket=bucket_name, marker=marker_path)


def update_batch_job_status() -> bool:
    """
    Method  fetches realtime status of AWS batch jobs and update it in State DynamoDb table
    :return: bool status
    """
    batch_client = boto3.client('batch')
    s3_resource = boto3.resource('s3')

    all_batch_jobs = InferenceStateDataModel.scan()

    total_batch_job_count = InferenceStateDataModel.count()
    logging.info(f"total_batch_job_count:{total_batch_job_count}")
    logging.info('running update_batch_job_status method')
    for batch_job_state in all_batch_jobs:

        logging.info(
            'update_batch_job_status job id->{} '.format(batch_job_state.batchjob_id))
        cur_batch_job_status, _ = get_aws_job_status_and_compute_requirement(
            batchjob_id=batch_job_state.cur_awsbatchjob_id, boto3_client=batch_client)

        if (cur_batch_job_status == "SUCCEEDED") or (cur_batch_job_status == "FAILED"):
            update_job_cw_url(batch_job=batch_job_state,
                              batch_client=batch_client)

        # Update only if the status changes - else pass
        if cur_batch_job_status != batch_job_state.awsbatch_job_status_overall:
            status_update_inference_job_state_table(batchjob_id=batch_job_state.batchjob_id,
                                                    batch_job_status_overall=cur_batch_job_status)

        if (batch_job_state.num_runs == 0) and (cur_batch_job_status == JOB_STATUS_DICT['failed']):
            resubmit_batch_jobs(
                batch_job_state, batch_client=batch_client, s3_resource=s3_resource)

    return True


def get_per_job_inference_success_count(job) -> int:
    per_job_inference_success_count = 0
    for item in job.algo_execution_status:
        if item.algorithm_execution_status == 'SUCCESS':
            per_job_inference_success_count += 1
    return per_job_inference_success_count


def check_overall_inference_batch_completion() -> tuple:
    """
    Method checks if any job is still pending to complete, if yes then returns False else True
    :return: bool status
    """
    logger.info("Checking Overall inference batch job(s) completion")
    completed = True
    inference_batch_jobs_state = InferenceStateDataModel.scan()
    overall_inference_success_count = 0

    logging.info('running check_overall_batch_completion method')
    for inference_batch_job in inference_batch_jobs_state:
        if inference_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['succeeded']:
            overall_inference_success_count = (overall_inference_success_count +
                                               get_per_job_inference_success_count(inference_batch_job))
        if ((inference_batch_job.num_runs == 0) and
                (inference_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['failed'])):
            logging.info('Not all jobs completed, wait for completion...')
            return False, None
        if ((inference_batch_job.num_runs == 1) and
                (inference_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['failed'])):
            overall_inference_success_count = (overall_inference_success_count +
                                               get_per_job_inference_success_count(inference_batch_job))
        if (inference_batch_job.awsbatch_job_status_overall != JOB_STATUS_DICT['failed']) and (
                inference_batch_job.awsbatch_job_status_overall != JOB_STATUS_DICT['succeeded']):
            logging.info('Not all jobs completed, wait for completion...')
            return False, None
    return completed, overall_inference_success_count


def update_job_cw_url(batch_job, batch_client):
    batch_job_cw_url = get_job_logstream(
        batchjob_id=batch_job.cur_awsbatchjob_id, boto3_client=batch_client)
    logger.info("batch job url ->", batch_job_cw_url)
    logging.info(f"batch_job_cw_url {batch_job_cw_url}")
    item = InferenceStateDataModel.get(hash_key=f"{batch_job.batchjob_id}")
    if item.num_runs > 1:
        item.rerun_awsbatchjob_cw_log_url = batch_job_cw_url
        item.update(actions=[
            InferenceStateDataModel.rerun_awsbatchjob_cw_log_url.set(
                batch_job_cw_url)
        ])
    else:
        item.update(actions=[
            InferenceStateDataModel.first_run_awsbatchjob_cw_log_url.set(
                batch_job_cw_url)
        ])


def check_batch_job_failure_threshold(batch_job_failure_count, total_batch_job_count):
    batch_job_failure_percent = 100 * batch_job_failure_count / total_batch_job_count
    if batch_job_failure_percent > float(BATCH_JOB_FAILURE_THRESHOLD_PERCENT):
        logger.error(f"Total batch jobs count: {total_batch_job_count} , "
                     f"Failed batch jobs count : {batch_job_failure_count}")

        raise Exception(f"Batch job failure percentage : {batch_job_failure_percent} exceeded batch job failure "
                        f"threshold percentage : {BATCH_JOB_FAILURE_THRESHOLD_PERCENT}")


def get_total_success_failure_number() -> tuple:
    item_failed = InferenceStateDataModel.scan(
        InferenceStateDataModel.awsbatch_job_status_overall == "FAILED")
    item_success = InferenceStateDataModel.scan(
        InferenceStateDataModel.awsbatch_job_status_overall == "SUCCEEDED")
    total_batch_success = len(list(item_success))
    total_batch_failures = len(list(item_failed))
    logger.info(
        f"failed job {total_batch_failures}, succeeded jobs {total_batch_success}")
    return total_batch_success, total_batch_failures


if __name__ == "__main__":
    try:
        args = getResolvedOptions(sys.argv,
                                  [
                                      'inference_inputtable_name',
                                      'inference_statetable_name',
                                      'inference_metatable_name',
                                      'region',
                                      'batch_job_failure_threshold_percent',
                                      'ssm_inferencing_complete_status'
                                  ])
        logger.info("System Arguments {}".format(args))
        # dynamically set the table names for input, state and meta dynamoDB tables
        InferenceInputDataModel.setup_model(
            InferenceInputDataModel, args['inference_inputtable_name'], args['region'])
        InferenceStateDataModel.setup_model(
            InferenceStateDataModel, args['inference_statetable_name'], args['region'])
        InferenceMetaDataModel.setup_model(
            InferenceMetaDataModel, args['inference_metatable_name'], args['region'])
        BATCH_JOB_FAILURE_THRESHOLD_PERCENT = int(
            args['batch_job_failure_threshold_percent'])
        # UPDATE STATUS OF THE JOBS In STATE TABLE
        update_batch_job_status()

        """model_s3_output_path = s3://bucketname/debug/year=execution_year
                                           /month=execution_month/day=execution_day/stepjobid=step_job_id/"""

        metaitem = InferenceMetaDataModel.get("fixedlookupkey")

        year = metaitem.inference_execution_year
        month = metaitem.inference_execution_month
        day = metaitem.inference_execution_day
        s3_bucket = metaitem.s3_bucket_name_shared
        sf_exec_id = metaitem.inference_step_job_id
        object_name = (f"debug/year={year}/month={month}/day={day}/stepjobid={sf_exec_id}/"
                       f"step_job_overall_summary.json")

        all_job_completion_flag, inference_created_count = check_overall_inference_batch_completion()
        logging.info("All inference Job completion flag {}".format(
            all_job_completion_flag))

        if all_job_completion_flag:
            logging.info("All submitted inference AWS Batch Jobs Completed")

            dump_data_to_s3(s3_ouput_bucket=s3_bucket, s3_output_object_name=object_name,
                            ddb_model=InferenceStateDataModel)

            total_batch_success, total_batch_failures = get_total_success_failure_number()

            metaitem.total_numb_batch_job_succeeded = total_batch_success
            metaitem.total_num_batch_job_failed = total_batch_failures
            metaitem.total_num_inference_executed = inference_created_count

            temp_start = metaitem.inference_timelaps.start_time
            metaitem.inference_timelaps = Timelaps(start_time=temp_start,
                                                   end_time=int(time.time()))
            metaitem.save()

            check_batch_job_failure_threshold(
                total_batch_failures, total_batch_failures + total_batch_success)

            # 'updating SSM parameter '

            ssm_client = boto3.client('ssm')

            response = ssm_client.put_parameter(
                Name=args['ssm_inferencing_complete_status'],
                Description='status inference complete',
                Value='True',
                Overwrite=True
            )
    except Exception as error:
        logger.error("Error ->{}".format(error))
        traceback.print_exc()
        sys.exit(1)
