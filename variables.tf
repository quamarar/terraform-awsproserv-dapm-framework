variable "context" {
  type        = string
  description = "Contextual Name. Choose between training & inferencing"

  validation {
    error_message = "Must be one of training / inferencing"
    condition     = contains(["training", "inferencing"], var.context)
  }
}

variable "use_case_name" {
  type        = string
  description = "Name of the use case. Identifier"
}

variable "name_prefix" {
  type        = string
  description = "Prefix to be appended to all resource names"
}

variable "environment" {
  type        = string
  description = "Stage / Environment identifier"
}

variable "ddb_params" {
  type        = object({ ddb_delete_protection = optional(bool) })
  description = "Enable framework DDB delete protection?"
  default = {
    ddb_delete_protection = false
  }
}

variable "const_glue_job_path" {
  type        = string
  description = "paths to constant glue scripts"
}

variable "utils_path" {
  type        = string
  description = "paths to utilities"
}

variable "evaluation_job_params" {
  type        = any
  description = "Evaluation glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.evaluation_job_params), "path")
  }
}
variable "gatekeeper_job_params" {
  type        = any
  description = "Gatekeeper glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.gatekeeper_job_params), "path")
  }
}

variable "ecr_attributes" {
  type        = any
  description = "Provide ECR attributes"

  default = {}
  validation {
    error_message = "Only valid key values for var.ecr_attributes: \"create_lifecycle_policy\", \"repository_lifecycle_policy\" & \"repository_force_delete\"."
    condition = length(setsubtract(keys(var.ecr_attributes), [
      "create_lifecycle_policy",
      "repository_lifecycle_policy",
      "repository_force_delete"
    ])) == 0
  }
}

variable "sagemaker_processing_job_execution_role_arn" {
  type        = string
  description = "To be removed"
}

variable "batch_compute_environments" {
  type        = any
  description = "Map of compute environment for batch"
}

variable "batch_container_properties" {
  type        = any
  description = "Provide training image container properties."
  default     = {}
}

variable "s3_configs" {
  type        = any
  description = "Overwrite s3 policies or configuration. Default it creates two buckets internal * shared"
  default     = {}
}

variable "eap_dq_bucket_name" {
  type        = string
  description = "EAP account s3 bucket"
}
