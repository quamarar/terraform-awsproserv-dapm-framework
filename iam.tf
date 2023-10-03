# TODO: Review glue job permissions

/* -------------------------- Glue Job permissions -------------------------- */
module "batch_executioner_role" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-role?ref=master"

  create_role           = true
  role_name             = "${var.name_prefix}-dapf-${local.context}-executioner"
  role_description      = "Role for Batch Container execution"
  trusted_role_actions  = ["sts:AssumeRole"]
  trusted_role_services = ["ecs-tasks.amazonaws.com"]
  max_session_duration  = 3600
  custom_role_policy_arns = [
    "arn:aws:iam::aws:policy/AdministratorAccess",
  ]
}

/* ----------------------- Glue permissions ---------------------- */

# data "aws_iam_policy_document" "glue_job_policy" {
#   statement {
#     sid = "glue01"

#     actions = [
#       "*"
#     ]

#     resources = [
#       "arn:aws:iam::aws:policy/IAMFullAccess",
#       "arn:aws:iam::aws:policy/AmazonS3FullAccess",
#       "arn:aws:iam::aws:policy/CloudWatchFullAccess",
#       "arn:aws:iam::aws:policy/AmazonKinesisFullAccess",
#       "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess",
#       "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
#     ]
#   }
# }

# module "glue_job_policy" {
#   source = "git::https://github.com/quamarar/terraform-common-modules//iam-policy"

#   create_policy = true
#   name          = "${var.name_prefix}-dapf-${local.context}-glue-job-policy"
#   path          = "/"
#   description   = "Policy for Glue job"
#   policy        = data.aws_iam_policy_document.glue_job_policy.json
# }

module "glue_job_role" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-role?ref=master"

  create_role           = true
  role_name             = "${var.name_prefix}-dapf-${local.context}-glue-job-role"
  role_description      = "Role for Glue job"
  trusted_role_actions  = ["sts:AssumeRole"]
  trusted_role_services = ["glue.amazonaws.com"]
  max_session_duration  = 3600
  custom_role_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonAthenaFullAccess",
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess",
    "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess",
    "arn:aws:iam::aws:policy/AmazonSSMFullAccess",
    "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess",
    "arn:aws:iam::aws:policy/CloudWatchFullAccess",
    "arn:aws:iam::aws:policy/AWSBatchFullAccess",
    "arn:aws:iam::aws:policy/AmazonEventBridgeFullAccess"
  ]
}
