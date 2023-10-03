output "training_contruct" {
  value = module.training_construct
}

# output "vpc" {
#   value = {
#     vpc = module.vpc
#     vpc_endpoints = {
#       sg        = module.vpc_endpoint_security_group
#       endpoints = module.vpc_endpoints
#     }
#   }
# }

output "exposed_events" {
  value = aws_cloudwatch_event_rule.scan_events
}

output "sm_model_approved_event" {
  value = aws_cloudwatch_event_rule.sm_registry_event
}

output "ssm_model_params" {
  value = aws_ssm_parameter.ssm_params
}
