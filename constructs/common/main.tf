
data "aws_caller_identity" "current" {}

/*===============================
#            KMS
===============================*/

module "kms_default" {
  source = "git::https://github.com/quamarar/terraform-common-modules//terraform-aws-kms?ref=master"

  aliases = [
    "${var.name_prefix}-kms-key"
  ]
}

resource "aws_sagemaker_model_package_group" "mpg" {
  model_package_group_name = "${var.name_prefix}-dapf-mpg"
}

resource "aws_cloudwatch_event_bus" "messenger" {
  name = "${var.name_prefix}-dapf-cb"
}

resource "aws_sns_topic" "framework_sns" {
  name = "${var.name_prefix}-dapf-notifier"
  kms_master_key_id = "${var.name_prefix}-kms-key"
}
