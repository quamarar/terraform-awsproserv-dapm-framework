data "aws_caller_identity" "current" {}

# SSM Parameters, S3, Step function, Exposed Events from Evaluation & Dynamodb tables

locals {

  available_contexts = {
    "training"    = "train"
    "inferencing" = "inference"
  }

  context = var.context

  short_context = local.available_contexts[local.context]

  s3_configs = merge({
    internal = {
      attach_policy                         = false
      force_destroy                         = true
      policy                                = null
      attach_deny_insecure_transport_policy = true
      attach_require_latest_tls_policy      = true
      control_object_ownership              = true
    }
    shared = {
      attach_policy                         = false
      force_destroy                         = true
      policy                                = null
      attach_deny_insecure_transport_policy = true
      attach_require_latest_tls_policy      = true
      control_object_ownership              = true
    }
  }, var.s3_configs)

  /* -------------------------------------------------------------------------- */
  /*                                 ssm params                                 */
  /* -------------------------------------------------------------------------- */
  framework_ssm_params = {
    ecr_preprocessing = {
      description = "Complete preprocessing job ecr preprocessing image url. This is used by step function"
      value       = "${module.ecr_repositories["preprocessing"].repository_url}:default"
    }
    ecr_context = {
      description = "Complete preprocessing job ecr preprocessing image url. This is used by Batch job"
      value       = "${module.ecr_repositories[local.context].repository_url}:default"
    }
    context_complete_status = {
      description = "Internal Framework param. Used by glue jobs."
    }
    live_context_batch_job_definition = {
      description = "Arn of currently active version of batch job definition contains latest ${local.context} image."
    }
  }

  /* -------------------------------------------------------------------------- */
  /*                               ECR Parameters                               */
  /* -------------------------------------------------------------------------- */

  ecr_attributes = merge({
    create_lifecycle_policy = true
    repository_lifecycle_policy = jsonencode({
      rules = [
        {
          rulePriority = 1,
          description  = "Keep last 30 images",
          selection = {
            countType   = "imageCountMoreThan",
            countNumber = 30,
            tagStatus   = "any",
          },
          action = {
            type = "expire"
          }
        }
      ]
    })
    repository_force_delete = true
  }, var.ecr_attributes)

  /* -------------------------------------------------------------------------- */
  /*                             DynamoDB parameters                            */
  /* -------------------------------------------------------------------------- */
  ddb_params = {
    input_table = {
      description = "Complete preprocessing job ecr preprocessing image url. This is used by step function"
      hash_key    = "pk_mappingid"
    }
    state_table = {
      description = "Complete preprocessing job ecr preprocessing image url. This is used by Batch job"
      hash_key    = "batchjob_id"
    }
    meta_table = {
      description = "Internal Framework param. Used by glue jobs."
      hash_key    = "metaKey"
    }
  }
}

/* ------------------------------------------------------------------------------------ */
/*                                Implement Step Function                               */
/* ------------------------------------------------------------------------------------ */

module "step_function" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-step-functions?ref=master"

  name = "${var.name_prefix}-modelops-${local.context}-orchestrator"
  type = "standard"

  definition = templatefile("${path.module}/${local.context}-step-function-definiton.tpl.json",
    {
      context                                     = local.context
      ssm_param_batch_job_definition              = aws_ssm_parameter.ssm_params["live_context_batch_job_definition"].name
      ssm_param_preprocessing_image               = aws_ssm_parameter.ssm_params["ecr_preprocessing"].name
      ssm_param_complete_status                   = aws_ssm_parameter.ssm_params["context_complete_status"].name
      ssm_param_aws_batch_ecr_url                 = aws_ssm_parameter.ssm_params["ecr_context"].name
      sagemaker_processing_job_execution_role_arn = var.sagemaker_processing_job_execution_role_arn
      glue_gatekeeper_job_name                    = module.glue_jobs["context_gatekeeper"].name
      glue_submit_job_name                        = module.glue_jobs["context_submit_awsbatch_statetable"].name
      glue_batch_status_check_job_name            = module.glue_jobs["context_job_awsbatch_status_check"].name
      glue_evaluation_job_name                    = module.glue_jobs["context_evaluation"].name
      glue_cleanup_job_name                       = module.glue_jobs["context_clean_up_job"].name
    }
  )

  service_integrations = {
    glue_Sync = {
      glue = values(module.glue_jobs).*.arn
    }
  }

  # TODO: Refine policy below
  attach_policy_json = true
  policy_json        = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "iam:PassRole",
                "glue:StartJobRun",
                "glue:GetJobRun",
                "glue:BatchStopJobRun",
                "sagemaker:AddTags",
                "sagemaker:CreateProcessingJob",
                "ssm:GetParameter",
                "glue:GetJobRuns"
            ],
            "Resource": [
                "arn:aws:iam::{var.account_number}:role/*",
                "arn:aws:glue:ap-south-1:{var.account_number}:job/*",
                "arn:aws:sagemaker:ap-south-1:{var.account_number}:processing-job/*",
                "arn:aws:ssm:ap-south-1:{var.account_number}:parameter/*"
            ]
        }
    ]
}
EOF

  logging_configuration = {
    include_execution_data = true
    level                  = "ALL"
  }
}

resource "aws_ssm_parameter" "ssm_params" {

  for_each = local.framework_ssm_params

  name           = "/${var.name_prefix}-dapf-ssm/${local.context}/${replace(each.key, "context", local.context)}"
  description    = each.value.description
  type           = "String"
  insecure_value = try(each.value.value, "default")
  lifecycle {
    ignore_changes = [
      insecure_value,
    ]
  }
}

module "ddb_tables" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-dynamodb-table?ref=master"

  for_each = local.ddb_params

  name                        = "${var.name_prefix}-${local.context}-${replace(each.key, "_", "-")}"
  hash_key                    = each.value.hash_key
  table_class                 = "STANDARD"
  deletion_protection_enabled = var.ddb_params.ddb_delete_protection

  attributes = [
    {
      "name" : each.value.hash_key
      "type" : "S"
    }
  ]
}

module "ecr_repositories" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-ecr?ref=master"

  for_each = toset([local.context, "preprocessing"])

  repository_name = replace("${var.name_prefix}/${local.context}-job/${replace(each.key, "context", local.context)}", "_", "-")

  # repository_read_write_access_arns = [data.aws_caller_identity.current.arn]
  create_lifecycle_policy = local.ecr_attributes.create_lifecycle_policy

  repository_lifecycle_policy = local.ecr_attributes.repository_lifecycle_policy
  repository_force_delete     = local.ecr_attributes.repository_force_delete
}

/*===============================
#            S3
===============================*/

module "s3_buckets" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-s3-bucket?ref=master"

  for_each = local.s3_configs

  bucket                = replace("${var.name_prefix}-${local.context}-${each.key}", "_", "-")
  expected_bucket_owner = data.aws_caller_identity.current.account_id

  attach_policy                         = each.value.attach_policy
  force_destroy                         = each.value.force_destroy
  policy                                = each.value.policy
  attach_deny_insecure_transport_policy = each.value.attach_deny_insecure_transport_policy
  attach_require_latest_tls_policy      = each.value.attach_require_latest_tls_policy
  control_object_ownership              = each.value.control_object_ownership
}


