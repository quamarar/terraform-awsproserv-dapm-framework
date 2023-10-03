--Create this table in the EAP account
CREATE EXTERNAL TABLE `dataquality_fb910c37b0a377054646a71b9b18d699`(
  `variablename` string,
  `unit` string,
  `rule` string,
  `maxthreshold` double,
  `minthreshold` double,
  `frequency` string,
  `dqrule` string,
  `outcome` string,
  `failurereason` string,
  `evaluatedmetrics` map<string,double>,
  `actual_value` string,
  `audit_timestamp` timestamp)
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
  's3://dashboard-apsouth1-dev-monitoringdb/dataquality/'