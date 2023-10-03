import sys
import time
import logging
import boto3
from awsglue.utils import getResolvedOptions
from ddb_helper_functions import submit_aws_batch_job, update_ssm_store, read_json_from_s3, extract_hash_from_string
from dynamodb_util import (
    TrainInputDataModel, TrainStateDataModel, TrainingMetaDataModel, Timelaps)
import traceback

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def insert_train_job_state_table(batchjob_id,
                                 step_job_id,
                                 pk,
                                 mapping_id,
                                 mapping_json_s3_path, usecase_name,
                                 algo_execution_status,
                                 algo_names,
                                 s3_pk_mappingid_data_input_path,
                                 algo_final_run_s3outputpaths,
                                 batch_job_definition,
                                 s3_training_output_path,
                                 s3_pred_or_eval_output_path,
                                 cur_batchjob_id,
                                 first_run_awsbatchjob_cw_log_url,
                                 batch_job_status_overall, input_data_set, **kwargs) -> int:

    TrainStateDataModel(batchjob_id=batchjob_id,
                        step_job_id=step_job_id,
                        pk=pk,
                        mapping_id=mapping_id,
                        mapping_json_s3_path=mapping_json_s3_path,
                        usecase_name=usecase_name,
                        algo_execution_status=algo_execution_status,
                        algo_names=algo_names,
                        s3_pk_mappingid_data_input_path=s3_pk_mappingid_data_input_path,
                        algo_final_run_s3outputpaths=algo_final_run_s3outputpaths,
                        batch_job_definition=batch_job_definition,
                        s3_training_prefix_output_path=s3_training_output_path,
                        s3_pred_or_eval_prefix_output_path=s3_pred_or_eval_output_path,
                        cur_awsbatchjob_id=batchjob_id,
                        first_run_awsbatchjob_cw_log_url=first_run_awsbatchjob_cw_log_url,
                        awsbatch_job_status_overall=batch_job_status_overall,
                        input_data_set=input_data_set
                        ).save()
    return True


def dynamo_setup():
    # dynamically set the table names for input, state and meta dynamoDB tables
    TrainInputDataModel.setup_model(TrainInputDataModel,
                                    args['train_inputtable_name'],
                                    args['region'])
    TrainStateDataModel.setup_model(TrainStateDataModel,
                                    args['train_statetable_name'],
                                    args['region'])
    TrainingMetaDataModel.setup_model(TrainingMetaDataModel,
                                      args['train_metatable_name'],
                                      args['region'])

    if not TrainStateDataModel.exists():
        TrainStateDataModel.create_table(
            read_capacity_units=100, write_capacity_units=100)
        time.sleep(20)


def get_args():
    return getResolvedOptions(sys.argv,
                              [
                                  'train_inputtable_name',
                                  'train_statetable_name',
                                  'train_metatable_name',
                                  'region'])


def update_training_meta_table():
    # Crate entries to save into Meta
    training_step_prefix_path = (f"s3://{metaitemtemp.s3_bucket_name_shared}/training/"
                                 f"year={metaitemtemp.execution_year}/month={metaitemtemp.execution_month}/"
                                 f"day={metaitemtemp.execution_day}/stepjobid={metaitemtemp.step_job_id}/")

    pred_or_eval_step_prefix_path = (f"s3://{metaitemtemp.s3_bucket_name_shared}/pred_or_eval/"
                                     f"year={metaitemtemp.execution_year}/month={metaitemtemp.execution_month}/"
                                     f"day={metaitemtemp.execution_day}/stepjobid={metaitemtemp.step_job_id}/")

    submit_end_epoch = int(time.time())
    metaitemtemp.s3_pred_or_eval_prefix_output_path = pred_or_eval_step_prefix_path
    metaitemtemp.s3_eval_summary_prefix_output_path = training_step_prefix_path
    metaitemtemp.aws_batch_submission_timelaps = Timelaps(
        start_time=submit_start_epoch, end_time=submit_end_epoch)
    metaitemtemp.model_creation_pred_or_eval_timelaps = Timelaps(
        start_time=submit_end_epoch, end_time=submit_end_epoch)
    metaitemtemp.state_table_total_num_batch_jobs = batch_jobs_submitted_count
    metaitemtemp.save()


if __name__ == '__main__':
    try:
        # https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-crawler-pyspark-extensions-get-resolved-options.html
        args = get_args()
        submit_start_epoch = int(time.time())
        dynamo_setup()
        metaitemtemp = TrainingMetaDataModel.get("fixedlookupkey")
        state_machine_id = extract_hash_from_string(metaitemtemp.step_job_id)

        s3_client = boto3.client('s3')
        mapping_json_constants = read_json_from_s3(
            metaitemtemp.mapping_json_s3_path, s3_client)
        mapping_id = mapping_json_constants["mapping_json_data"]['Training']["mappingColumn"]

        batch_client = boto3.client('batch')
        batch_jobs_submitted_count = 0
        train_inputs = TrainInputDataModel.scan()
        for train_input in train_inputs:
            logger.info(f"Preparing Training batch job submit for Primary Key : {train_input.pk}, "
                        f"Mapping ID : {train_input.mapping_id}")

            # The S3 folder paths are in the form of key=value as
            # that enables creating athena table on top of it implicitly
            training_output_path = (f"s3://{train_input.s3_output_bucket_name}/training/"
                                    f"year={train_input.execution_year}/month={train_input.execution_month}/"
                                    f"day={train_input.execution_day}/stepjobid={train_input.step_job_id}/"
                                    f"pk={train_input.pk}/mapping={train_input.mapping_id}/")

            pred_or_eval_output_path = (f"s3://{train_input.s3_output_bucket_name}/pred_or_eval/"
                                        f"year={train_input.execution_year}/month={train_input.execution_month}/"
                                        f"day={train_input.execution_day}/stepjobid={train_input.step_job_id}/"
                                        f"pk={train_input.pk}/mapping={train_input.mapping_id}/")

            unique_batch_job_name = (
                f"{metaitemtemp.aws_batch_job_prefixname}_{state_machine_id}_{train_input.pk}_{train_input.mapping_id}")

            logging.info(
                f"Logging job with unique_batch_job_name: {unique_batch_job_name}")

            status, job_id, aws_batch_job_definition = submit_aws_batch_job(
                boto3_client=batch_client,
                algo_names_list=train_input.algo_names,
                s3_pk_mappingid_data_input_path=train_input.s3_pk_mappingid_data_input_path,
                s3_training_prefix_output_path=training_output_path,
                s3_pred_or_eval_prefix_output_path=pred_or_eval_output_path,
                train_metatable_name=args['train_metatable_name'],
                pk=train_input.pk,
                mapping_id=train_input.mapping_id,
                aws_batch_job_name=unique_batch_job_name,
                aws_batch_job_queue=metaitemtemp.aws_batch_job_queue,
                aws_batch_job_definition=metaitemtemp.aws_batch_job_definition,
                region=args['region']
            )

            s3_training_output_path = (
                f"{training_output_path}/batchjobid={job_id}/")

            s3_pred_or_eval_output_path = (
                f"{pred_or_eval_output_path}/batchjobid={job_id}")

            first_run_awsbatchjob_cw_log_url = ""

            logger.info(f"Batch Job submitted:{job_id}")
            batch_job_status_overall = "SUBMITTED"

            if status:
                insert_train_job_state_table(
                    batchjob_id=job_id,
                    step_job_id=train_input.step_job_id,
                    pk=train_input.pk,
                    mapping_id=train_input.mapping_id,
                    algo_execution_status=[],
                    algo_names=train_input.algo_names,
                    algo_final_run_s3outputpaths=[],
                    batch_job_definition=aws_batch_job_definition,
                    s3_training_output_path=s3_training_output_path,
                    s3_pred_or_eval_output_path=s3_pred_or_eval_output_path,
                    cur_batchjob_id=job_id,
                    first_run_awsbatchjob_cw_log_url=first_run_awsbatchjob_cw_log_url,
                    batch_job_status_overall=batch_job_status_overall,
                    mapping_json_s3_path=train_input.mapping_json_s3_path,
                    usecase_name=train_input.usecase_name,
                    s3_pk_mappingid_data_input_path=train_input.s3_pk_mappingid_data_input_path,
                    input_data_set=train_input.input_data_set)

                batch_jobs_submitted_count = batch_jobs_submitted_count + 1

            else:
                raise Exception(f"Training batch job submit for Primary Key : {train_input.pk}, "
                                f"Mapping ID : {train_input.mapping_id} failed")

        update_training_meta_table()

        if int(batch_jobs_submitted_count) != int(train_inputs.total_count):
            raise Exception(f"Training Batch Jobs Submitted Count :{batch_jobs_submitted_count} not equal to "
                            f"Training input count:{train_inputs.total_count}")

    except Exception:
        traceback.print_exc()
        sys.exit(1)
