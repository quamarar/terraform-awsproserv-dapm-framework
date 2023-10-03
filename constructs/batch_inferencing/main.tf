locals {

  context             = "inferencing"
  const_glue_job_path = "${path.module}/python"
  batch_compute_environments = coalesce(var.batch_compute_environments, {
    inferencing = {
      min_vcpus      = 0
      max_vcpus      = 216
      desired_vcpus  = 0
      instance_types = ["m5.large"]
      type           = "EC2"
    }
  })
}

module "inferencing_contruct" {
  source = "../../"

  context       = local.context
  use_case_name = var.use_case_name
  name_prefix   = var.name_prefix
  environment   = var.environment

  ddb_params = var.ddb_params
  utils_path = var.utils_path

  const_glue_job_path   = local.const_glue_job_path
  evaluation_job_params = var.evaluation_job_params
  gatekeeper_job_params = var.gatekeeper_job_params

  eap_dq_bucket_name = var.eap_dq_bucket_name
  ecr_attributes     = var.ecr_attributes

  sagemaker_processing_job_execution_role_arn = var.sagemaker_processing_job_execution_role_arn

  batch_container_properties = var.batch_container_properties

  batch_compute_environments = { for k, v in local.batch_compute_environments : k => {
    name_prefix = replace("${var.name_prefix}-${k}", "_", "-")
    compute_resources = merge({
      security_group_ids = [module.vpc_endpoint_security_group.security_group_id]
      subnets            = var.batch_vpc.subnet_ids
      # Note - any tag changes here will force compute environment replacement
      # which can lead to job queue conflicts. Only specify tags that will be static
      # for the lifetime of the compute environment
      tags = {
        # This will set the name on the Ec2 instances launched by this compute environment
        Name = replace("${var.name_prefix}-${k}-instance", "_", "-")
      }
    }, v)
    }
  }

  s3_configs = var.s3_configs
}

################################################################################
# VPC
################################################################################

module "vpc_endpoint_security_group" {
  source = "git::github.com/MSIL-Analytics-ACE/terraform-common-modules//terraform-aws-security-group"

  name        = "${var.name_prefix}-${local.context}-vep-sg"
  description = "Security group for VPC endpoints"
  vpc_id      = var.batch_vpc.vpc_id

  ingress_with_self = [
    {
      rule = "all-all"
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      description = "Container to VPC endpoint service"
      self        = true
    },
  ]

  egress_cidr_blocks = ["0.0.0.0/0"]
  egress_rules       = ["https-443-tcp"]
}
