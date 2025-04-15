from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import json

def load_schema():
    with open('/app/config/log_schema.json', 'r') as f:
        schema_json = json.load(f)
    return StructType.fromJson(schema_json)

def create_spark_session():
    return SparkSession.builder \
        .appName("LogAnalyticsPipeline") \
        .config("spark.jars.packages", 
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,"
                "org.elasticsearch:elasticsearch-spark-30_2.12:8.7.1") \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoints") \
        .config("spark.es.nodes", "elasticsearch") \
        .config("spark.es.port", "9200") \
        .config("spark.es.nodes.wan.only", "true") \
        .getOrCreate()

def process_stream(spark, schema):
    # Read from Kafka
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:9092") \
        .option("subscribe", "app_logs") \
        .option("startingOffsets", "latest") \
        .load()
    
    # Parse JSON and apply schema
    parsed_df = kafka_df.select(
        from_json(col("value").cast("string"), schema).alias("data")) \
        .select("data.*")
    
    # Add processing timestamp and window
    processed_df = parsed_df \
        .withColumn("processing_timestamp", current_timestamp()) \
        .withColumn("log_timestamp", to_timestamp(col("timestamp"))) \
        .withWatermark("log_timestamp", "5 minutes") \
        .withColumn("date", to_date(col("log_timestamp")))
    
    # Error detection - create unique ID for each window-service combination
    error_counts = processed_df.filter(col("level") == "ERROR") \
        .groupBy(
            window(col("log_timestamp"), "5 minutes").alias("time_window"),
            col("service")
        ) \
        .count() \
        .withColumnRenamed("count", "error_count") \
        .withColumn("doc_id", 
                   concat(
                       date_format(col("time_window.start"), "yyyyMMddHHmm"),
                       lit("_"),
                       col("service")
                   )) \
        .withColumn("window_start", col("time_window.start")) \
        .withColumn("window_end", col("time_window.end")) \
        .drop("time_window")
    
    return processed_df, error_counts

def write_to_elasticsearch(processed_df, error_counts):
    # Write main logs to ES (append mode)
    logs_query = processed_df.writeStream \
        .outputMode("append") \
        .format("es") \
        .option("checkpointLocation", "/tmp/checkpoint/logs") \
        .start("logs")
    
    # Write error counts using update mode with document IDs
    errors_query = error_counts.writeStream \
        .outputMode("update") \
        .format("es") \
        .option("checkpointLocation", "/tmp/checkpoint/error_counts") \
        .option("es.mapping.id", "doc_id") \
        .option("es.write.operation", "upsert") \
        .start("error_counts")
    
    return logs_query, errors_query

def main():
    spark = create_spark_session()
    schema = load_schema()
    
    processed_df, error_counts = process_stream(spark, schema)
    logs_query, errors_query = write_to_elasticsearch(processed_df, error_counts)
    
    print("Streaming queries started successfully")
    print(f"Logs query status: {logs_query.status}")
    print(f"Errors query status: {errors_query.status}")
    
    # Wait for termination
    logs_query.awaitTermination()
    errors_query.awaitTermination()

if __name__ == "__main__":
    main()