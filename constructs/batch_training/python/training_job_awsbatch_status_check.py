import logging
import sys
import time
import boto3
import traceback

from awsglue.utils import getResolvedOptions
from ddb_helper_functions import (submit_aws_batch_job, get_job_logstream,
                                  delete_folder_from_s3, get_aws_job_status_and_compute_requirement, dump_data_to_s3,
                                  extract_hash_from_string)
from dynamodb_util import TrainStateDataModel, TrainingMetaDataModel, TrainInputDataModel, Timelaps

from constants import JOB_STATUS_DICT

######################## This is for local development ###################
# import log
# import sys
# import time
#
# import boto3
#
# from model.utils.constants import JOB_STATUS_DICT, ssm_training_complete_status
# from model.utils.dynamodb_util import TrainStateDataModel, TrainingMetaDataModel, TrainInputDataModel, Timelaps
# from model.utils.ddb_helper_functions import submit_aws_batch_job, delete_table_record, get_job_logstream, \
#     delete_folder_from_s3, get_aws_job_status_and_compute_requirement, dump_data_to_s3
# from awsglue.utils import getResolvedOptions

######################## This is for local development ###################

logger = logging.getLogger()
logger.setLevel(logging.INFO)

batch_client = boto3.client('batch')
s3_resource = boto3.resource('s3')


def update_job_cw_url(batch_job_state):
    batch_job_cw_url = get_job_logstream(
        batchjob_id=batch_job_state.cur_awsbatchjob_id, boto3_client=batch_client)
    train_state_item = TrainStateDataModel.get(
        hash_key=f"{batch_job_state.batchjob_id}")
    if batch_job_state.num_runs > 0:
        train_state_item.rerun_awsbatchjob_cw_log_url = batch_job_cw_url
        train_state_item.update(actions=[
            TrainStateDataModel.rerun_awsbatchjob_cw_log_url.set(
                batch_job_cw_url)
        ])
    else:
        train_state_item.update(actions=[
            TrainStateDataModel.first_run_awsbatchjob_cw_log_url.set(
                batch_job_cw_url)
        ])


def reupdate_train_job_state_table_onjobsubmission(batch_job_state, rerun_batchjob_id, attempt_cnt=1):
    """
    :param batch_job_state: state table row object of the batch job
    :param rerun_batchjob_id: on submitting job a jobid is returned and for second time re-run try
    :param attempt_cnt: variable to control reattempt tries of this function
    :return: exit code
    """

    try:
        item = TrainStateDataModel.get(hash_key=batch_job_state.batchjob_id)
        item.cur_awsbatchjob_id = rerun_batchjob_id
        item.rerun_awsbatchjob_id = rerun_batchjob_id
        item.num_runs = batch_job_state.num_runs + 1
        item.awsbatch_job_status_overall = "SUBMITTED"
        item.save()
        logger.info(
            f"Updated state table rerun details for batchjob_id:{batch_job_state.batchjob_id}")

    except Exception:
        traceback.print_exc()
        if attempt_cnt <= 3:
            time.sleep(2)
            logger.error(
                f"batchjob_id:{batch_job_state.batchjob_id} attempt : {attempt_cnt} failed, retrying")
            reupdate_train_job_state_table_onjobsubmission(
                batch_job_state, rerun_batchjob_id, attempt_cnt + 1)
        else:
            logger.error(f"batchjob_id:{batch_job_state.batchjob_id} failed after {attempt_cnt} attempts. "
                         f"Stopping execution")
            sys.exit(-1)


def status_update_train_job_state_table(batchjob_id, batch_job_status_overall, attempt_cnt=1):
    """
    :param batchjob_id: haskey for the record to update
    :param batch_job_status_overall
    :param attempt_cnt: variable to control reattempt tries of this function
    :return: exit code
    """

    try:
        item = TrainStateDataModel.get(hash_key=batchjob_id)
        logger.info("Updating JOBID- {} status to {} in StateTable".
                    format(batchjob_id, batch_job_status_overall))

        item.awsbatch_job_status_overall = batch_job_status_overall
        item.save()

    except Exception:
        traceback.print_exc()
        logger.error(
            f"batchjob_id:{batchjob_id} attempt : {attempt_cnt} failed, retrying")
        if attempt_cnt <= 3:
            time.sleep(2)
            status_update_train_job_state_table(
                batchjob_id, batch_job_status_overall, attempt_cnt + 1)

        logger.error(
            "batchjob_id:{batchjob_id} failed after {attempt_cnt} attempts. Stopping execution")


def submit_failed_job_train_state_table(batch_job_state, bucket_name,
                                        s3_training_prefix_output_path, s3_pred_or_eval_prefix_output_path):
    """
    Method submit to AWS Batch job queue for RE-RUN and update TrainState DDB Table
    @:param job:
    @:param batch_client:
    :return: Returns exit code otherwise exception
    """

    metaitemtemp = TrainingMetaDataModel.get("fixedlookupkey")
    aws_batch_job_name = metaitemtemp.aws_batch_job_prefixname
    aws_batch_job_queue = metaitemtemp.aws_batch_job_queue
    aws_batch_job_def = metaitemtemp.aws_batch_job_definition

    delete_folder_from_s3(s3_resource, bucket=bucket_name,
                          marker=s3_training_prefix_output_path)
    delete_folder_from_s3(s3_resource, bucket=bucket_name,
                          marker=s3_pred_or_eval_prefix_output_path)

    
    state_machine_id = extract_hash_from_string(batch_job_state.inference_step_job_id)

    unique_batch_job_name = """{}_{}_{}_{}""".format(aws_batch_job_name, state_machine_id, batch_job_state.pk,
                                                     batch_job_state.mapping_id)

    status, batch_job_id, _ = (
        submit_aws_batch_job(boto3_client=batch_client,
                             algo_names_list=batch_job_state.algo_names,
                             s3_pk_mappingid_data_input_path=batch_job_state.s3_pk_mappingid_data_input_path,
                             s3_training_prefix_output_path=s3_training_prefix_output_path,
                             s3_pred_or_eval_prefix_output_path=s3_pred_or_eval_prefix_output_path,
                             train_metatable_name=metaitemtemp.train_metatable_name,
                             pk=batch_job_state.pk,
                             mapping_id=batch_job_state.mapping_id,
                             job_id=batch_job_state.batchjob_id,
                             aws_batch_job_name=unique_batch_job_name,
                             aws_batch_job_queue=aws_batch_job_queue,
                             aws_batch_job_definition=aws_batch_job_def,
                             region=batch_job_state.Meta.region,
                             aws_batch_compute_scale_factor=2))

    reupdate_train_job_state_table_onjobsubmission(batch_job_state=batch_job_state,
                                                   rerun_batchjob_id=batch_job_id)


def check_batch_job_failure_threshold(batch_job_failure_count, total_batch_job_count):
    batch_job_failure_percent = 100 * batch_job_failure_count / total_batch_job_count
    if batch_job_failure_percent > float(BATCH_JOB_FAILURE_THRESHOLD_PERCENT):
        logger.error(f"Total batch jobs count: {total_batch_job_count}")
        logger.error(f"Failed batch jobs count : {batch_job_failure_count}")
        logger.error(f"Batch job failure percentage : {batch_job_failure_percent} exceeded batch job failure "
                     f"threshold percentage : {BATCH_JOB_FAILURE_THRESHOLD_PERCENT}")
        sys.exit(-1)


def drop_batch_prefix_from_path(path):
    s3_prefix_part_list = []
    for s3_prefix_part in path.split("/"):
        if s3_prefix_part.split("=")[0] == "batchjobid":
            break
        s3_prefix_part_list.append(s3_prefix_part)

    return "/".join(s3_prefix_part_list)


def resubmit_batch_jobs(batch_job_state):
    bucket_name, path = (str(batch_job_state.s3_training_prefix_output_path)
                         .replace("s3://", "").split("/", 1))
    s3_training_prefix_output_path = drop_batch_prefix_from_path(path)

    bucket_name, path = (str(batch_job_state.s3_pred_or_eval_prefix_output_path)
                         .replace("s3://", "").split("/", 1))
    s3_pred_or_eval_prefix_output_path = drop_batch_prefix_from_path(path)

    submit_failed_job_train_state_table(batch_job_state=batch_job_state,
                                        bucket_name=bucket_name,
                                        s3_training_prefix_output_path=s3_training_prefix_output_path,
                                        s3_pred_or_eval_prefix_output_path=s3_pred_or_eval_prefix_output_path)


def increment_succeeded_algo_per_job(job, models_cnt) -> int:
    for item in job.algo_execution_status:
        if item.algorithm_execution_status == 'SUCCESS':
            models_cnt += 1
    return models_cnt


def get_args():
    return getResolvedOptions(sys.argv,
                              [
                                  'train_inputtable_name',
                                  'train_statetable_name',
                                  'train_metatable_name',
                                  'ssm_training_complete_status',
                                  'region',
                                  'batch_job_failure_threshold_percent'
                              ])


def dynamo_setup():
    # dynamically set the table names for input, state and meta dynamoDB tables
    TrainInputDataModel.setup_model(
        TrainInputDataModel, args['train_inputtable_name'], args['region'])
    TrainStateDataModel.setup_model(
        TrainStateDataModel, args['train_statetable_name'], args['region'])
    TrainingMetaDataModel.setup_model(
        TrainingMetaDataModel, args['train_metatable_name'], args['region'])


def update_batch_job_status() -> bool:
    """
    Method  fetches realtime status of AWS batch jobs and update it in State DynamoDb table
    :return: bool status
    """
    all_batch_jobs = TrainStateDataModel.scan()

    total_batch_job_count = TrainStateDataModel.count()
    logging.info(f"total_batch_job_count:{total_batch_job_count}")
    logging.info('running update_batch_job_status method')
    for batch_job_state in all_batch_jobs:
        cur_batch_job_status, _ = get_aws_job_status_and_compute_requirement(
            batchjob_id=batch_job_state.cur_awsbatchjob_id, boto3_client=batch_client)

        if (cur_batch_job_status == "SUCCEEDED") or (cur_batch_job_status == "FAILED"):
            update_job_cw_url(batch_job_state=batch_job_state)

        # Update only if the status changes - else pass
        if cur_batch_job_status != batch_job_state.awsbatch_job_status_overall:
            status_update_train_job_state_table(batchjob_id=batch_job_state.batchjob_id,
                                                batch_job_status_overall=cur_batch_job_status)

        if (batch_job_state.num_runs == 0) and (cur_batch_job_status == JOB_STATUS_DICT['failed']):
            resubmit_batch_jobs(batch_job_state)

    return True


def update_train_meta():
    train_metaitem.total_numb_batch_job_succeeded = total_batch_success
    train_metaitem.total_num_batch_job_failed = total_batch_failures
    train_metaitem.total_num_models_created = model_created_count
    temp_start = train_metaitem.model_creation_pred_or_eval_timelaps.start_time
    train_metaitem.model_creation_pred_or_eval_timelaps = Timelaps(start_time=temp_start,
                                                                   end_time=int(time.time()))
    train_metaitem.save()
    logger.info("Updated Train meta table")


def get_per_job_train_success_count(job) -> int:
    per_job_train_success_count = 0
    for item in job.algo_execution_status:
        if item.algorithm_execution_status == 'SUCCESS':
            per_job_train_success_count += 1
    return per_job_train_success_count


def check_overall_train_batch_completion() -> tuple:
    """
    Method checks if any job is still pending to complete, if yes then returns False else True
    :return: bool status
    """
    logger.info("Checking Overall batch job(s) completion")
    completed = True
    train_batch_jobs_state = TrainStateDataModel.scan()
    overall_train_success_count = 0

    logging.info('running check_overall_batch_completion method')
    for train_batch_job in train_batch_jobs_state:
        if train_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['succeeded']:
            overall_train_success_count = (overall_train_success_count +
                                           get_per_job_train_success_count(train_batch_job))
        if ((train_batch_job.num_runs == 0) and
                (train_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['failed'])):
            logging.info('Not all jobs completed, wait for completion...')
            return False, None
        if ((train_batch_job.num_runs == 1) and
                (train_batch_job.awsbatch_job_status_overall == JOB_STATUS_DICT['failed'])):
            overall_train_success_count = (overall_train_success_count +
                                           get_per_job_train_success_count(train_batch_job))
        if (train_batch_job.awsbatch_job_status_overall != JOB_STATUS_DICT['failed']) and (
                train_batch_job.awsbatch_job_status_overall != JOB_STATUS_DICT['succeeded']):
            logging.info('Not all jobs completed, wait for completion...')
            return False, None
    return completed, overall_train_success_count


def get_object_name():
    year = train_metaitem.execution_year
    month = train_metaitem.execution_month
    day = train_metaitem.execution_day
    sf_exec_id = train_metaitem.step_job_id
    return (f"debug/year={year}/month={month}/day={day}/stepjobid={sf_exec_id}/"
            f"step_job_overall_summary.json")


def get_total_success_failure_number() -> tuple:
    item_failed = TrainStateDataModel.scan(
        TrainStateDataModel.awsbatch_job_status_overall == "FAILED")
    item_success = TrainStateDataModel.scan(
        TrainStateDataModel.awsbatch_job_status_overall == "SUCCEEDED")
    total_batch_success = len(list(item_success))
    total_batch_failures = len(list(item_failed))
    logger.info(
        f"failed job {total_batch_failures}, succeeded jobs {total_batch_success}")
    return total_batch_success, total_batch_failures


if __name__ == "__main__":
    try:
        args = get_args()
        dynamo_setup()
        BATCH_JOB_FAILURE_THRESHOLD_PERCENT = int(
            args['batch_job_failure_threshold_percent'])

        update_batch_job_status()

        all_job_completion_flag, model_created_count = check_overall_train_batch_completion()
        logging.info("All Job(s) completion flag {}".format(
            all_job_completion_flag))

        if all_job_completion_flag:
            train_metaitem = TrainingMetaDataModel.get("fixedlookupkey")
            object_name = get_object_name()

            dump_data_to_s3(s3_ouput_bucket=train_metaitem.s3_bucket_name_shared,
                            s3_output_object_name=object_name, ddb_model=TrainStateDataModel)
            total_batch_success, total_batch_failures = get_total_success_failure_number()

            logging.info(f"total_batch_success:{total_batch_success}, total_batch_failures:{total_batch_failures}")

            check_batch_job_failure_threshold(
                total_batch_failures, total_batch_failures + total_batch_success)

            update_train_meta()
            ssm_client = boto3.client('ssm')
            response = ssm_client.put_parameter(
                Name=args['ssm_training_complete_status'],
                Description='status complete',
                Value='True',
                Overwrite=True
            )
    except Exception:
        traceback.print_exc()
        logger.error("Exception in main")
        sys.exit(1)
