output "ddb_tables" {
  value = module.ddb_tables
}

output "ssm_params" {
  value = { for k, v in aws_ssm_parameter.ssm_params : k => v.name }
}

output "glue_jobs" {
  value = module.glue_jobs
}

output "ecr" {
  value = module.ecr_repositories
}

output "step_function" {
  value = module.step_function
}

output "s3_buckets" {
  value = module.s3_buckets
}

output "s3_uploads" {
  value = {
    utils            = values(aws_s3_object.upload_utils).*.id
    constant_scripts = values(aws_s3_object.upload_py_glue_scripts).*.id
    ext_scripts      = values(aws_s3_object.upload_ext_scripts).*.id
  }
}

output "batch" {
  value = {
    cloudwatch_lg  = aws_cloudwatch_log_group.batch
    batch          = module.batch
    job_definition = aws_batch_job_definition.job_def
  }
}
