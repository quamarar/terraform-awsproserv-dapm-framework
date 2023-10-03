/*===============================
#           Batch Job
===============================*/

locals {
  batch_container_properties = merge({ command = ["python3", "/opt/ml/${local.context}.py"],
    jobRoleArn       = module.batch_executioner_role.iam_role_arn
    executionRoleArn = module.batch_executioner_role.iam_role_arn
    resourceRequirements = [
      {
        type  = "VCPU"
        value = "1"
      },
      {
        type  = "MEMORY"
        value = "2048"
      }
  ] }, var.batch_container_properties)
}

resource "aws_cloudwatch_log_group" "batch" {
  name              = "${var.name_prefix}/batch/${local.context}"
  retention_in_days = 7
}

module "batch" {
  source = "github.com/MSIL-Analytics-ACE/terraform-common-modules//terraform-aws-batch?ref=v1.0.0"

  instance_iam_role_name        = "${var.name_prefix}-dapf-${local.context}"
  instance_iam_role_path        = "/batch/"
  instance_iam_role_description = "IAM instance role/profile for AWS Batch EC2 instance(s)"
  instance_iam_role_additional_policies = [
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ]

  service_iam_role_name        = "${var.name_prefix}-dapf-${local.context}"
  service_iam_role_path        = "/batch/"
  service_iam_role_description = "IAM service role for AWS Batch"

  compute_environments = var.batch_compute_environments

  # Job queues and scheduling policies
  job_queues = {
    low_priority = {
      create_scheduling_policy = false
      name                     = "${var.name_prefix}-dapf-batch-${local.context}-job-queue"
      state                    = "ENABLED"
      priority                 = 1
      order                    = 1

      compute_environments = keys(var.batch_compute_environments)
      tags = { 
        deployed_by  = "TFProviders"
      }
    }

  }
}

resource "aws_batch_job_definition" "job_def" {
  name = "${var.name_prefix}-dapf-batch-${local.context}-job-def"
  type = "container"

  container_properties = jsonencode(merge(local.batch_container_properties, {
    image = aws_ssm_parameter.ssm_params["ecr_context"].insecure_value
  }))

  # Image is continousely pushed hence container properties are expected to drift
  lifecycle {
    ignore_changes = [container_properties]
  }
}
