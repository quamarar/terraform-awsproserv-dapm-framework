/*========================================================
#       5x Glue Jobs - 3X Constant & 2X customizable
=========================================================*/

data "aws_region" "current" {}

locals {
  region_name = data.aws_region.current.name

  framework_util_files = {
    training = [
      "ddb_helper_functions.py",
      "dynamodb_util.py",
      "constants.py"
    ]
    inferencing = [
      "ddb_helper_functions.py",
      "dynamodb_util.py",
      "constants.py",
      "inference_dynamodb_model.py",
      "inference_utils.py"
    ]
  }

  extra_py_files = join(",", [for v in local.framework_util_files[local.context] : "s3://${module.s3_buckets["internal"].s3_bucket_id}/src/python/utils/${v}"])

  glue_common_arguments = {
    "--additional-python-modules"              = "pythena,ndjson==0.3.1,pynamodb==5.5.0,scikit-learn==1.3.0,pandas==1.5.3"
    "--extra-files"                            = local.extra_py_files
    "--region"                                 = local.region_name
    "--${local.short_context}_inputtable_name" = module.ddb_tables["input_table"].dynamodb_table_id
    "--${local.short_context}_metatable_name"  = module.ddb_tables["meta_table"].dynamodb_table_id
    "--${local.short_context}_statetable_name" = module.ddb_tables["state_table"].dynamodb_table_id
  }
  constant_glue_jobs = {
    context_submit_awsbatch_statetable = {
      file_name = "submit_${local.context}_job_awsbatch_statetable.py"
      default_arguments = merge(local.glue_common_arguments, {
      })
      type         = "pythonshell"
      max_capacity = 1
      glue_version = "2.0"
    }
    context_job_awsbatch_status_check = {
      file_name = "${local.context}_job_awsbatch_status_check.py"
      default_arguments = merge(local.glue_common_arguments, {
        "--ssm_${local.context}_complete_status" = aws_ssm_parameter.ssm_params["context_complete_status"].name
        "--athenadb_name"                        = "default"
        "--batch_job_failure_threshold_percent"  = "0"
      })
      type         = "pythonshell"
      max_capacity = 1
      glue_version = "2.0"
    }
    context_clean_up_job = {
      file_name = "clean_up_job.py",
      default_arguments = merge(local.glue_common_arguments, {
        "--ssm_${local.context}_complete_status" = aws_ssm_parameter.ssm_params["context_complete_status"].name
      })
      type         = "pythonshell"
      max_capacity = 1
      glue_version = "2.0"
    }
  }
  external_glue_jobs = {
    context_evaluation = {
      file_name = basename(var.evaluation_job_params.path)
      default_arguments = merge(local.glue_common_arguments, {
        "--extra-py-files"     = local.extra_py_files,
        "--eap_central_bucket" = var.eap_dq_bucket_name
      }, try(var.evaluation_job_params.additional_arguments, {}))
      type              = "glueetl"
      python_version    = 3
      number_of_workers = try(var.evaluation_job_params.number_of_workers, 10)
      worker_type       = try(var.evaluation_job_params.worker_type, "G.1X")
      glue_version      = "4.0"
    }
    context_gatekeeper = {
      file_name         = basename(var.gatekeeper_job_params.path)
      default_arguments = merge(local.glue_common_arguments, try(var.gatekeeper_job_params.additional_arguments, {}))
      type              = "pythonshell"
      max_capacity      = 1
      glue_version      = "2.0"
    }
  }

  glue_jobs = merge(local.constant_glue_jobs, local.external_glue_jobs)
}

/* ---------------------- Terraform driven file uploads --------------------- */

resource "aws_s3_object" "upload_py_glue_scripts" {
  for_each = fileset(var.const_glue_job_path, "**")

  bucket = module.s3_buckets["internal"].s3_bucket_id
  key    = "src/python/${local.context}/${each.value}"

  source      = "${var.const_glue_job_path}/${each.value}"
  source_hash = filemd5("${var.const_glue_job_path}/${each.value}")

  lifecycle {
    ignore_changes = [
      tags,
      tags_all
    ]
  }
}

resource "aws_s3_object" "upload_utils" {
  for_each = fileset(var.utils_path, "**")

  bucket = module.s3_buckets["internal"].s3_bucket_id
  key    = "src/python/utils/${each.value}"

  source      = "${var.utils_path}/${each.value}"
  source_hash = filemd5("${var.utils_path}/${each.value}")

  lifecycle {
    ignore_changes = [
      tags,
      tags_all
    ]
  }
}

resource "aws_s3_object" "upload_ext_scripts" {
  for_each = toset([var.evaluation_job_params.path, var.gatekeeper_job_params.path])

  bucket = module.s3_buckets["internal"].s3_bucket_id
  key    = "src/python/${local.context}/${basename(each.value)}"

  source      = each.value
  source_hash = filemd5("${each.value}")

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
  source = "github.com/MSIL-Analytics-ACE/terraform-common-modules//terraform-aws-glue-job?ref=v1.0.0"

  for_each = local.glue_jobs

  job_name = "${var.name_prefix}-${replace(replace(each.key, "context", local.context), "_", "-")}"

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
    script_location = "s3://${module.s3_buckets["internal"].s3_bucket_id}/src/python/${local.context}/${each.value.file_name}"
    python_version  = try(each.value.python_version, 3.9)
  }

  execution_property = try(each.value.execution_property, {
    max_concurrent_runs = 1
  })

  default_arguments = each.value.default_arguments
}

