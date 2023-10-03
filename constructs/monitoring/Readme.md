# SNS
1. Create identity in SES service
2. Create an Amazon SNS Topic "model_start_dq_notification"
3. Create Email subscription to the Amazon SNS Topic

# Event Bridge 
1. Event Bus to be created - async_monitoring_event_bus
2. Rules need to be created parameterizing the use case in the event pattern 
3. rules target can be fetched from isengard UI 

# Lambdas
Environment variable to be picked from isengard UI

# Glue Deployment 
Additional parameters to be picked from the isengard UI

#  Cross Account access bucket in EAP
Bucket Name: dashboard-apsouth1-dev-monitoringdb
Account: EAP

# Glue Database in EAP 
Database name: dashboard_monitoring_db

# Glue crawler in EAP account
### data_quality_crawler
    path: s3://dashboard-apsouth1-dev-monitoringdb/dataquality
    glue database: dashboard_monitoring_db

### model_quality_crawler
    path: s3://dashboard-apsouth1-dev-monitoringdb/modelquality
    glue database: dashboard_monitoring_db
   


