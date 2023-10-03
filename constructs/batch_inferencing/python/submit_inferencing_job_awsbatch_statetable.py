import time
import boto3
import sys

import pandas as pd
from awsglue.utils import getResolvedOptions
import logging
import awswrangler as wr
from inference_dynamodb_model import (InferenceStateDataModel, InferenceMetaDataModel,
                                      InferenceInputDataModel, Timelaps, InferenceAlgorithmS3OutputPath)
from ddb_helper_functions import (read_json_from_s3, submit_aws_batch_job, delete_table_record, get_job_logstream,
                                  fetch_all_records, read_athena_table_data, update_ssm_store, submit_inference_aws_batch_job,
                                  extract_hash_from_string)
import traceback
#########################################################################
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def insert_inference_job_state_table(batchjob_id,
                                     inference_step_job_id,
                                     pk,
                                     mapping_id,
                                     mapping_json_s3_inference_path,
                                     inference_usecase_name,
                                     algo_execution_status,
                                     inference_algo_names,
                                     s3_pk_mappingid_data_input_path,
                                     algo_final_run_s3outputpaths,
                                     batch_job_definition,
                                     s3_inference_prefix_output_path,
                                     s3_infer_summary_prefix_output_path,
                                     first_run_awsbatchjob_cw_log_url,
                                     batch_job_status_overall,
                                     inference_input_data_set,
                                     meta_table_item,
                                     algo_to_model_input_paths_mapping,
                                     s3_pk_mapping_model_prefix_input_path,
                                     s3_output_bucket_name
                                     ) -> int:
    """
    Takes input all columns and saves data in TrainState DDB Table

    :param batch_triggered_num_runs:
    :param batchjob_id:
    :param batchjob_id:
    :param step_job_id:
    :param skuid:
    :param mapping_id:
    :param algo_execution_status:
    :param algo_names: list of algorithms
    :param s3_pk_mappingid_data_input_path:
    :param algo_final_run_s3outputpaths:
    :param batch_job_definition:
    :param s3_training_output_path:
    :param s3_eval_summary_prefix_output_path:
    :param cur_batchjob_id:
    :param batch_job_status_overall:
     **kwargs
    :return: exit code
    """
    try:

        InferenceStateDataModel(batchjob_id=batchjob_id,
                                inference_step_job_id=inference_step_job_id,
                                training_step_job_id=meta_table_item.training_step_job_id,
                                inference_usecase_name=inference_usecase_name,
                                inference_execution_year=meta_table_item.inference_execution_year,
                                inference_execution_month=meta_table_item.inference_execution_month,
                                inference_execution_day=meta_table_item.inference_execution_day,
                                training_execution_year=meta_table_item.training_execution_year,
                                training_execution_month=meta_table_item.training_execution_month,
                                training_execution_day=meta_table_item.training_execution_day,
                                pk=pk,
                                mapping_id=mapping_id,
                                mapping_json_s3_inference_path=mapping_json_s3_inference_path,
                                mapping_json_s3_training_path=meta_table_item.mapping_json_s3_training_path,
                                inference_input_data_set=inference_input_data_set,
                                inference_algo_names=inference_algo_names,
                                training_algo_names=meta_table_item.training_algo_names,
                                s3_pk_mappingid_data_input_path=s3_pk_mappingid_data_input_path,
                                s3_pk_mapping_model_prefix_input_path=s3_pk_mapping_model_prefix_input_path,
                                s3_output_bucket_name=s3_output_bucket_name,
                                batch_job_definition=batch_job_definition,
                                batch_job_status_overall=batch_job_status_overall,
                                algo_execution_status=algo_execution_status,
                                algo_to_model_input_paths_mapping=algo_to_model_input_paths_mapping,
                                algo_final_run_s3_outputpaths=algo_final_run_s3outputpaths,
                                s3_inference_prefix_output_path=s3_inference_prefix_output_path,
                                s3_infer_summary_prefix_output_path=s3_infer_summary_prefix_output_path,
                                cur_awsbatchjob_id=batchjob_id,
                                first_run_awsbatchjob_cw_log_url=first_run_awsbatchjob_cw_log_url,
                                awsbatch_job_status_overall=batch_job_status_overall,
                                training_winning_algo_name=meta_table_item.training_winning_algo_name

                                ).save()

    except Exception:
        traceback.print_exc()
        return False
    return True


def get_args():
    return getResolvedOptions(sys.argv,
                              [
                                  'inference_inputtable_name',
                                  'inference_statetable_name',
                                  'inference_metatable_name',
                                  'region'])


def dynamo_setup():
    # dynamically set the table names for input, state and meta dynamoDB tables
    InferenceInputDataModel.setup_model(InferenceInputDataModel,
                                        args['inference_inputtable_name'],
                                        args['region'])
    InferenceStateDataModel.setup_model(InferenceStateDataModel,
                                        args['inference_statetable_name'],
                                        args['region'])
    InferenceMetaDataModel.setup_model(InferenceMetaDataModel,
                                       args['inference_metatable_name'],
                                       args['region'])

    if not InferenceStateDataModel.exists():
        InferenceStateDataModel.create_table(
            read_capacity_units=100, write_capacity_units=100)
        time.sleep(20)


def get_training_state():
    training_state_table_athena_query = ("""select algo_final_run_s3outputpaths,year, month, day, pk, mapping_id,
        step_job_id from {}.{} where year = '{}' and month = '{}' and day = '{}' and step_job_id='{}'""".
                                         format(inference_meta.training_athenadb_name,
                                                inference_meta.training_athenadb_debug_table_name,
                                                inference_meta.training_execution_year,
                                                inference_meta.training_execution_month,
                                                inference_meta.training_execution_day,
                                                inference_meta.training_step_job_id))

    train_state_df = wr.athena.read_sql_query(training_state_table_athena_query,
                                              database=inference_meta.training_athenadb_name)
    if train_state_df.shape[0] == 0:
        raise Exception("Train StateTable debug cannot have 0 records")

    return train_state_df


def get_corresponding_train_state():
    training_stepjob_id = inference_meta.training_step_job_id
    training_mapping_id_column_name = inference_meta.training_mapping_id_column_name
    inferencing_mapping_id_column_name = inference_meta.mapping_id_column_name

    corresponding_train_state = None
    if training_mapping_id_column_name == inferencing_mapping_id_column_name:
        corresponding_train_state = train_state_table_df[
            (train_state_table_df["pk"] == inference_input.pk) &
            (train_state_table_df["mapping_id"] == inference_input.mapping_id) &
            (train_state_table_df['step_job_id'] == training_stepjob_id)]

    elif training_mapping_id_column_name == "default":
        corresponding_train_state = train_state_table_df[
            (train_state_table_df["pk"] == inference_input.pk) &
            (train_state_table_df["mapping_id"] == "default") &
            (train_state_table_df['step_job_id'] == training_stepjob_id)]

    if corresponding_train_state.shape[0] != 1:
        raise Exception(f"1 Primary Key and 1 Mapping Id should have 1 record in Train State Table"
                        f"but found {corresponding_train_state.shape[0]}. Raising Exception")
    return corresponding_train_state


def append_to_algo_mapping_list():
    algo_mapping_list_temp = []
    for training_algorithms_object in corresponding_train_state_df['algo_final_run_s3outputpaths']:
        for algo_obj in training_algorithms_object:
            algo_name = algo_obj['algorithm_name']
            algo_model_path = algo_obj['model_s3_output_path']
            if (algo_name in inference_input.inference_algo_names) or (
                    algo_name == inference_meta.training_winning_algo_name):
                algo_to_model_mapping = InferenceAlgorithmS3OutputPath(algorithm_name=algo_name,
                                                                       inference_s3_output_path=algo_model_path)
                algo_mapping_list_temp.append(algo_to_model_mapping)

    logger.info(f"Number of Algorithms in Job: {len(algo_mapping_list_temp)}")

    return algo_mapping_list_temp


def update_inference_meta_table():
    submit_end_epoch = int(time.time())
    inference_meta.s3_eval_summary_prefix_output_path = inference_step_prefix_path
    inference_meta.aws_batch_submission_timelaps = Timelaps(
        start_time=submit_start_epoch, end_time=submit_end_epoch)
    inference_meta.model_creation_pred_or_eval_timelaps = (
        Timelaps(start_time=submit_end_epoch, end_time=submit_end_epoch))
    inference_meta.state_table_total_num_batch_jobs = state_table_total_num_batch_jobs
    inference_meta.save()


if __name__ == '__main__':
    try:
        args = get_args()
        submit_start_epoch = int(time.time())
        dynamo_setup()
        inference_meta = InferenceMetaDataModel.get("fixedlookupkey")
        state_machine_id = extract_hash_from_string(inference_meta.inference_step_job_id)
        batch_client = boto3.client('batch')

        logger.info(" Inference_algo_names is {},  training winning algo name is {}"
                    .format(inference_meta.inference_algo_names, inference_meta.training_winning_algo_name))

        train_state_table_df = get_training_state()
        Inference_input_rows = InferenceInputDataModel.scan()
        state_table_total_num_batch_jobs = 0
        for inference_input in Inference_input_rows:
            logger.info(f"Preparing Inference batch job submit for Primary Key : {inference_input.pk}, "
                        f"Mapping ID : {inference_input.mapping_id}")
            corresponding_train_state_df = get_corresponding_train_state()
            algo_mapping_list = append_to_algo_mapping_list()

            inference_prefix_output_path = (f"s3://{inference_input.s3_output_bucket_name}/inferenceout/"
                                            f"year={inference_input.inference_execution_year}/"
                                            f"month={inference_input.inference_execution_month}/"
                                            f"day={inference_input.inference_execution_day}/"
                                            f"stepjobid={inference_input.inference_step_job_id}/"
                                            f"pk={inference_input.pk}/mapping={inference_input.mapping_id}")

            unique_batch_job_name = (
                f"{inference_meta.aws_batch_job_prefixname}_{state_machine_id}_{inference_input.pk}_{inference_input.mapping_id}")

            logger.info(f"unique_batch_job_name:{unique_batch_job_name}")
            status, job_id, aws_batch_job_definition = (
                submit_inference_aws_batch_job(
                    batch_client,
                    s3_inferencing_prefix_input_path=inference_input.s3_pk_mappingid_data_input_path,
                    s3_inferencing_prefix_output_path=inference_prefix_output_path,
                    inference_metatable_name=inference_meta.inference_metatable_name,
                    mapping_id=inference_input.mapping_id,
                    s3_approved_model_prefix_path=inference_input.s3_pk_mapping_model_prefix_input_path,
                    pk_id=inference_input.pk,
                    region=args['region'],
                    aws_batch_job_name=unique_batch_job_name,
                    aws_batch_job_queue=inference_meta.aws_batch_job_queue,
                    aws_batch_job_definition=inference_meta.aws_batch_job_definition))

            s3_inferences_output_path = f"{inference_prefix_output_path}/batchjobid={job_id}"
            logger.info(f"Batch job Submitted, Job Id:{job_id}")

            first_run_awsbatchjob_cw_log_url = ""
            batch_job_status_overall = "SUBMITTED"

            if status:
                insert_inference_job_state_table(
                    batchjob_id=job_id,
                    inference_step_job_id=inference_input.inference_step_job_id,
                    pk=inference_input.pk,
                    mapping_id=inference_input.mapping_id,
                    mapping_json_s3_inference_path=inference_input.mapping_json_s3_inference_path,
                    inference_usecase_name=inference_input.inference_usecase_name,
                    algo_execution_status=[],
                    inference_algo_names=inference_input.inference_algo_names,
                    s3_pk_mappingid_data_input_path=inference_input.s3_pk_mappingid_data_input_path,
                    algo_final_run_s3outputpaths=[],
                    batch_job_definition=aws_batch_job_definition,
                    s3_inference_prefix_output_path=s3_inferences_output_path,
                    first_run_awsbatchjob_cw_log_url=first_run_awsbatchjob_cw_log_url,
                    batch_job_status_overall=batch_job_status_overall,
                    inference_input_data_set=inference_input.inference_input_data_set,
                    meta_table_item=inference_meta,
                    algo_to_model_input_paths_mapping=algo_mapping_list,
                    s3_pk_mapping_model_prefix_input_path=inference_input.s3_pk_mappingid_data_input_path,
                    s3_output_bucket_name=inference_input.s3_output_bucket_name,
                    s3_infer_summary_prefix_output_path="")
                state_table_total_num_batch_jobs = state_table_total_num_batch_jobs + 1
            else:
                raise Exception(f"Inference batch job submit for Primary Key : {inference_input.pk}, "
                                f"Mapping ID : {inference_input.mapping_id} failed")

        inference_step_prefix_path = """s3://{}/inferenceout/year={}/month={}/day={}/stepjobid={}/""".format(
            inference_meta.s3_bucket_name_shared, inference_meta.inference_execution_year,
            inference_meta.inference_execution_month,
            inference_meta.inference_execution_day, inference_meta.inference_step_job_id)
        update_inference_meta_table()

        if state_table_total_num_batch_jobs != Inference_input_rows.total_count:
            raise Exception(f"Inference Batch Jobs Submitted Count :{state_table_total_num_batch_jobs} not equal to "
                            f"Inference input count:{Inference_input_rows.total_count}")

    except Exception:
        traceback.print_exc()
        raise Exception("Exception in main")
