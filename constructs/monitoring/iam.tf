# TODO: Review glue job permissions

data "aws_iam_policy_document" "glue_job_policy" {
  statement {
    sid = "glue01"

    actions = [
      "sts:*",
      "kms:*"
    ]
    resources = ["*"]
  }
}

module "glue_job_policy" {
  source = "github.com/MSIL-Analytics-ACE/terraform-common-modules//iam-policy?ref=v1.0.0"

  create_policy = true
  name          = "${var.name_prefix}-dapf-${local.context}-glue-job-policy"
  path          = "/"
  description   = "Policy for Glue job"
  policy        = data.aws_iam_policy_document.glue_job_policy.json
}

module "glue_job_role" {
  source = "github.com/MSIL-Analytics-ACE/terraform-common-modules//iam-role?ref=v1.0.0"

  create_role           = true
  role_name             = "${var.name_prefix}-dapf-${local.context}-glue-job-role"
  role_description      = "Role for Glue job"
  trusted_role_actions  = ["sts:AssumeRole"]
  trusted_role_services = ["glue.amazonaws.com"]
  max_session_duration  = 3600
  custom_role_policy_arns = [
    module.glue_job_policy.arn,
    "arn:aws:iam::aws:policy/CloudWatchFullAccess",
    "arn:aws:iam::aws:policy/AmazonKinesisFullAccess",
    "arn:aws:iam::aws:policy/IAMFullAccess",
    "arn:aws:iam::aws:policy/AmazonS3FullAccess",
    "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
  ]
}
