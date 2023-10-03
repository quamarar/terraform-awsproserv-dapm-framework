--Create this table in the EAP account
CREATE EXTERNAL TABLE `modelquality`(
  `metric_name` string,
  `unit` string,
  `expected_value` string,
  `actual_value` bigint,
  `audit_timestamp` timestamp,
  `stepjobid` string,
  `algo` string,
  `green_threshold` double,
  `amber_threshold` double,
  `red_threshold` double,
  `status` string,
  `algoname` string)
PARTITIONED BY (
  `usecase_name` string,
  `year` string,
  `month` string,
  `day` string)
ROW FORMAT SERDE
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
STORED AS INPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat'
OUTPUTFORMAT
  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'
LOCATION
  's3://dashboard-apsouth1-dev-monitoringdb/modelquality/'