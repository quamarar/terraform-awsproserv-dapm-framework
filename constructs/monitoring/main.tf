locals {
  context = "monitoring"

  util_files = [
    "ddb_helper_functions.py",
    "dynamodb_util.py",
    "constants.py",
    "inference_dynamodb_model.py",
    "inference_utils.py",
    "dataquality_helper_functions.py"
  ]


  default_params = {
    type              = "glueetl"
    python_version    = 3
    number_of_workers = 10
    worker_type       = "G.1X"
    glue_version      = "4.0"
    additional_arguments = {
      "--eap_central_bucket"                = var.eap_dq_bucket_name
      "--same_account_monitoring_athena_db" = var.monitoring_athena_db
      "--additional-python-modules"         = "pythena==1.6.0"
      "--extra-py-files" = join(",", [
        for file in local.util_files : "s3://${var.training_internal_bucket_name}/src/python/utils/${file}"
      ])
    }
  }

  glue_jobs = {

    data_quality = merge(local.default_params, {
      file_name = basename(var.glue_data_quality.path)
      default_arguments = merge(local.default_params.additional_arguments, {
        "--dashboard_consoilidated_dq_tablename" = "ml-dd-dataquality"
      }, try(var.glue_data_quality.additional_arguments, {}))
    })

    training_model_quality = merge(local.default_params, {
      file_name = basename(var.glue_training_model_quality.path)
      default_arguments = merge(local.default_params.additional_arguments, {
        "--model_quality_prefix" = "model-quality"
        "--threshold_data_path"  = "s3://${var.training_internal_bucket_name}/src/python/monitoring/model_quality_threshold.csv"
      }, try(var.glue_training_model_quality.additional_arguments, {}))
    })

    inferencing_model_quality = merge(local.default_params, {
      file_name = basename(var.glue_inferencing_model_quality.path)
      default_arguments = merge(local.default_params.additional_arguments, {
        "--usecase_name"                  = var.glue_inferencing_model_quality.use_case_name
        "--threshold_data_path"           = "s3://${var.training_internal_bucket_name}/src/python/monitoring/model_quality_threshold.csv"
        "--inferencing_shared_bucketname" = var.inferencing_shared_bucket_name
      }, try(var.glue_inferencing_model_quality.additional_arguments, {}))
    })

    feature_store = merge(local.default_params, {
      file_name = basename(var.glue_feature_store.path)
      default_arguments = merge(local.default_params.additional_arguments, {
        "--additional-python-modules" = "sagemaker==2.187.0,pythena==1.6.0,sagemaker-feature-store-pyspark-3-1"
        "--extra-jars"                = "s3://${var.training_internal_bucket_name}/src/python/utils/sagemaker-feature-store-spark-sdk.jar"
      }, try(var.glue_feature_store.additional_arguments, {}))
    })

  }
}

/* ---------------------- Terraform driven file uploads --------------------- */

resource "aws_s3_object" "upload_ext_scripts" {
  for_each = toset([
    var.glue_data_quality.path,
    var.glue_training_model_quality.path,
    var.glue_inferencing_model_quality.path,
    var.glue_feature_store.path,
  ])

  bucket = var.training_internal_bucket_name
  key    = "src/python/${local.context}/${basename(each.value)}"

  source      = each.value
  source_hash = filemd5(each.value)

  lifecycle {
    ignore_changes = [
      tags,
      tags_all
    ]
  }
}

/* -------------------------------------------------------------------------- */
/*                             Glue Job creation                              */
/* -------------------------------------------------------------------------- */

module "glue_jobs" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-glue-job?ref=master"

  for_each = local.glue_jobs

  job_name = "${var.name_prefix}-${replace(each.key, "_", "-")}"

  glue_version = try(each.value.glue_version, null)
  role_arn     = module.glue_job_role.iam_role_arn

  # Specific to glueetl
  number_of_workers = try(each.value.number_of_workers, null)
  worker_type       = try(each.value.worker_type, null)

  # This is to ensure there are no concurrent runs
  max_capacity = try(each.value.max_capacity, null)
  max_retries  = 0
  timeout      = 2880

  command = {
    name            = each.value.type
    script_location = "s3://${var.training_internal_bucket_name}/src/python/${local.context}/${each.value.file_name}"
    python_version  = try(each.value.python_version, 3.9)
  }

  default_arguments = each.value.default_arguments
}

module "lambda" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-lambda?ref=master"

  function_name = "${var.name_prefix}-glue-trigger-on-event"
  description   = "Lambda function to trigger other lambda functions"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"
  publish       = true

  source_path = "${path.module}/lambda/lambda_function.py"

  allowed_triggers = { for key, rule in var.training_events :
    key => {
      principal  = "events.amazonaws.com"
      source_arn = rule.arn
    }
  }
  environment_variables = {
    data_quality_glue_job     = module.glue_jobs["data_quality"].name
    feature_store_glue_job    = module.glue_jobs["feature_store"].name
    model_monitoring_glue_job = module.glue_jobs["training_model_quality"].name
  }
}

resource "aws_cloudwatch_event_target" "lambda_target" {

  for_each = var.training_events

  event_bus_name = var.event_bus_name
  rule           = each.value.name
  arn            = module.lambda.lambda_function_arn
}
