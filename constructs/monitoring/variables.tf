variable "name_prefix" {
  type        = string
  description = "name prefix to be appened to resources"
}

variable "event_bus_name" {
  type        = string
  description = "Exposed event bus from common module"
}

variable "training_events" {
  type        = map(any)
  description = "Exposed training from DAPF batch_training module"
}

variable "training_internal_bucket_name" {
  type        = string
  description = "training internal s3 bucket"
}

variable "utils_path" {
  type        = string
  description = "Path of Utils folder. Same as training and inference"
}

variable "glue_data_quality" {
  type        = any
  description = "Gatekeeper glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.glue_data_quality), "path")
  }
}

variable "glue_training_model_quality" {
  type        = any
  description = "Gatekeeper glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.glue_training_model_quality), "path")
  }
}

variable "glue_inferencing_model_quality" {
  type        = any
  description = "Gatekeeper glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.glue_inferencing_model_quality), "path")
  }
  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.glue_inferencing_model_quality), "use_case_name")
  }
}

variable "glue_feature_store" {
  type        = any
  description = "Gatekeeper glue job params"

  validation {
    error_message = "Must contain path key."
    condition     = contains(keys(var.glue_feature_store), "path")
  }
}

variable "eap_dq_bucket_name" {
  type        = string
  description = "EAP account s3 bucket"
}

variable "inferencing_shared_bucket_name" {
  type        = string
  description = "inferencing shared s3 bucket"
}

variable "monitoring_athena_db" {
  type        = string
  description = "Monitoring athena database"
}
