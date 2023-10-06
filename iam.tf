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
    "arn:aws:iam::aws:policy/SecretsManagerReadWrite",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  ]
}

/* ----------------------- Glue permissions ---------------------- */

module "glue_custom_iam_policy" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-policy?ref=master""

  name   = "${var.name_prefix}-dapf-${local.context}-glue-job-policy"
  path   = "/"
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "athena:StartQueryExecution",
                "states:ListStateMachines",
                "cloudwatch:PutMetricData",
                "ecr:DescribeRegistry",
                "ecr:DescribePullThroughCacheRules",
                "ecr:GetAuthorizationToken",
                "logs:DescribeAccountPolicies",
                "athena:*",
                "logs:CreateLogGroup",
                "logs:GetLogDelivery",
                "logs:PutLogEvents",
                "logs:ListLogDeliveries",
                "logs:CreateLogDelivery",
                "logs:CreateLogStream",
                "logs:PutResourcePolicy",
                "batch:DescribeJobs",
                "logs:UpdateLogDelivery",
                "ssm:*",
                "logs:GetLogEvents",
                "batch:DescribeJobDefinitions",
                "logs:DeleteLogDelivery",
                "ec2:DescribeRouteTables"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "glue:SearchTables",
                "states:DescribeStateMachine",
                "glue:GetTableVersions",
                "glue:GetPartitions",
                "glue:UpdateTable",
                "glue:DeleteTable",
                "s3:CreateBucket",
                "states:TagResource",
                "sagemaker:CreateModelPackageGroup",
                "ecr:BatchDeleteImage",
                "codestar-connections:UseConnection",
                "dynamodb:DescribeTable",
                "states:GetExecutionHistory",
                "dynamodb:GetItem",
                "glue:GetColumnStatisticsForTable",
                "events:RemoveTargets",
                "glue:GetUserDefinedFunctions",
                "ecr:BatchCheckLayerAvailability",
                "events:PutEvents",
                "dynamodb:BatchGetItem",
                "events:DescribeRule",
                "glue:UpdateDatabase",
                "ecr:DescribeImageScanFindings",
                "dynamodb:PutItem",
                "glue:CreateTable",
                "glue:GetTables",
                "lambda:InvokeFunction",
                "states:UpdateStateMachine",
                "ecr:GetDownloadUrlForLayer",
                "sagemaker:CreateModelPackage",
                "dynamodb:Scan",
                "states:StopExecution",
                "states:UntagResource",
                "dynamodb:UpdateItem",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:GetObject",
                "glue:GetPartition",
                "states:DescribeExecution",
                "ecr:BatchGetImage",
                "ecr:DescribeImages",
                "glue:BatchDeleteTable",
                "glue:DeletePartition",
                "dynamodb:UpdateTable",
                "glue:DeleteDatabase",
                "states:ListExecutions",
                "batch:SubmitJob",
                "events:PutRule",
                "glue:DeleteTableVersion",
                "ecr:DescribeImageReplicationStatus",
                "s3:ListBucket",
                "iam:PassRole",
                "glue:GetTableVersion",
                "sns:Publish",
                "s3:AbortMultipartUpload",
                "glue:UpdateColumnStatisticsForTable",
                "ecr:CompleteLayerUpload",
                "ecr:DescribeRepositories",
                "glue:CreatePartition",
                "glue:UpdatePartition",
                "s3:ListBucketMultipartUploads",
                "s3:PutBucketPublicAccessBlock",
                "glue:BatchGetPartition",
                "glue:DeleteColumnStatisticsForTable",
                "glue:GetDatabases",
                "glue:GetTable",
                "glue:GetDatabase",
                "states:DescribeStateMachineForExecution",
                "events:DeleteRule",
                "events:PutTargets",
                "glue:CreateDatabase",
                "glue:BatchDeleteTableVersion",
                "states:StartExecution",
                "s3:GetBucketLocation",
                "states:ListTagsForResource"
            ],
            "Resource": [
                "arn:aws:iam::{var.account_number}:role/*",
                "arn:aws:states:*:*:stateMachine:sagemaker-*",
                "arn:aws:states:*:*:execution:sagemaker-*:*",
                "arn:aws:sagemaker:ap-south-1:{var.account_number}:model-package/*",
                "arn:aws:dynamodb:ap-south-1:{var.account_number}:table/*",
                "arn:aws:lambda:*:*:function:sagemaker-*",
                "arn:aws:events:ap-south-1:{var.account_number}:event-bus/*",
                "arn:aws:events:*:*:rule/*/*",
                "arn:aws:codestar-connections:*:*:connection/*",
                "arn:aws:ecr:ap-south-1:{var.account_number}:repository/*",
                "arn:aws:batch:ap-south-1:{var.account_number}:job-definition/*",
                "arn:aws:batch:ap-south-1:{var.account_number}:job-queue/*",
                "arn:aws:glue:*:*:table/*/*",
                "arn:aws:glue:*:*:database/default",
                "arn:aws:glue:*:*:database/global_temp",
                "arn:aws:glue:*:*:database/sagemaker-*",
                "arn:aws:glue:*:*:catalog",
                "arn:aws:sns:ap-south-1:{var.account_number}:*",
                "arn:aws:s3:::*",
                "arn:aws:s3:::aws-athena-query-results-*"
            ]
        },
        {
            "Sid": "VisualEditor2",
            "Effect": "Allow",
            "Action": "athena:*",
            "Resource": [
                "arn:aws:codestar-connections:*:*:connection/*",
                "arn:aws:events:ap-south-1:{var.account_number}:event-bus/*",
                "arn:aws:events:*:*:rule/*/*",
                "arn:aws:sns:ap-south-1:{var.account_number}:*",
                "arn:aws:ecr:ap-south-1:{var.account_number}:repository/*",
                "arn:aws:s3:::*",
                "arn:aws:s3:::aws-athena-query-results-*",
                "arn:aws:batch:ap-south-1:{var.account_number}:job-definition/*",
                "arn:aws:batch:ap-south-1:{var.account_number}:job-queue/*",
                "arn:aws:iam::{var.account_number}:role/*",
                "arn:aws:sagemaker:ap-south-1:{var.account_number}:model-package/*",
                "arn:aws:states:*:*:stateMachine:sagemaker-*",
                "arn:aws:states:*:*:execution:sagemaker-*:*",
                "arn:aws:dynamodb:ap-south-1:{var.account_number}:table/*",
                "arn:aws:lambda:*:*:function:sagemaker-*",
                "arn:aws:glue:*:*:table/*/*",
                "arn:aws:glue:*:*:database/default",
                "arn:aws:glue:*:*:database/global_temp",
                "arn:aws:glue:*:*:database/sagemaker-*",
                "arn:aws:glue:*:*:catalog"
            ]
        }
    ]
}
EOF
}


module "glue_job_role" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-role?ref=master"

  create_role           = true
  role_name             = "${var.name_prefix}-dapf-${local.context}-glue-job-role"
  role_description      = "Role for Glue job"
  trusted_role_actions  = ["sts:AssumeRole"]
  trusted_role_services = ["glue.amazonaws.com"]
  max_session_duration  = 3600
  custom_role_policy_arns = [
    module.glue_custom_iam_policy.arn
  ]
}


/* ----------------------- Sagemaker Preprocessing permissions ---------------------- */

module "sagemaker_proprocessing_iam_policy" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-policy?ref=master"

  count = var.sagemaker_processing_job_execution_role_arn != null ? 0 : 1

  name   = "${var.name_prefix}-dapf-${local.context}-sagemaker-pp-policy"
  path   = "/"
  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ecr-public:DescribeImageTags",
                "ecr-public:DescribeImages",
                "dynamodb:BatchGetItem",
                "dynamodb:PutItem",
                "ecr:GetDownloadUrlForLayer",
                "ecr-public:DescribeRegistries",
                "ecr-public:GetRepositoryCatalogData",
                "ecr-public:GetRepositoryPolicy",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:GetObjectAcl",
                "s3:GetObject",
                "ecr-public:DescribeRepositories",
                "dynamodb:DescribeTable",
                "ecr:BatchGetImage",
                "ecr:DescribeImages",
                "ecr-public:GetRegistryCatalogData",
                "dynamodb:GetItem",
                "s3:DeleteObject",
                "ecr:BatchCheckLayerAvailability",
                "ecr-public:BatchCheckLayerAvailability",
                "s3:GetObjectVersion"
            ],
            "Resource": [
                "arn:aws:ecr:ap-south-1:{var.account_number}:repository/*",
                "arn:aws:ecr-public::{var.account_number}:registry/*",
                "arn:aws:ecr-public::{var.account_number}:repository/*",
                "arn:aws:s3:::*/*",
                "arn:aws:dynamodb:ap-south-1:{var.account_number}:table/*"
            ]
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucketMultipartUploads",
                "s3:GetBucketTagging",
                "s3:ListBucketVersions",
                "s3:ListBucket",
                "s3:GetBucketOwnershipControls",
                "s3:PutBucketCORS",
                "s3:GetBucketAcl",
                "s3:GetBucketPolicy"
            ],
            "Resource": "arn:aws:s3:::*"
        },
        {
            "Sid": "VisualEditor2",
            "Effect": "Allow",
            "Action": [
                "ecr-public:GetAuthorizationToken",
                "ecr:GetAuthorizationToken",
                "sts:GetServiceBearerToken"
            ],
            "Resource": "*"
        }
    ]
}
EOF
}


module "sagemaker_proprocessing_role" {
  source = "git::https://github.com/quamarar/terraform-common-modules//iam-role?ref=master"

  count = var.sagemaker_processing_job_execution_role_arn != null ? 0 : 1

  create_role           = true
  role_name             = "${var.name_prefix}-dapf-${local.context}-sagemake-pp-role"
  role_description      = "Role for Sagemaker preprocessing job"
  trusted_role_actions  = ["sts:AssumeRole"]
  trusted_role_services = ["sagemaker.amazonaws.com"]
  max_session_duration  = 3600
  custom_role_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
    "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole",
    module.sagemaker_proprocessing_iam_policy[0].arn
  ]
}
