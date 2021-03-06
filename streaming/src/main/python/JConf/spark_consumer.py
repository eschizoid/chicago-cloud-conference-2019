import logging
import os
import time as time_

from pyspark import SparkConf, SparkContext, RDD
from pyspark.sql import SQLContext
from pyspark.sql.types import StringType
from pyspark.streaming import StreamingContext

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')


def reverse_current_time_millis() -> str:
    return str(int(round(time_.time() * 1000)))[::-1]


def get_sql_context_instance(spark_context: SparkContext) -> SQLContext:
    if "sqlContextSingletonInstance" not in globals():
        globals()["sqlContextSingletonInstance"] = SQLContext(spark_context)
    return globals()["sqlContextSingletonInstance"]


def process_rdd(time: time_, rdd: RDD) -> None:
    if rdd.isEmpty():
        return
    else:
        logging.info("----------- %s -----------" % str(time))
        sql_context = get_sql_context_instance(rdd.context)
        tweets_df = sql_context.createDataFrame(rdd, StringType())
        tweets_df.write.json(
            f"""s3a://jconf-2020/bronze/{time_.strftime("%Y-%m-%d")}/{reverse_current_time_millis()}""")


def configure_spark_streaming_context() -> StreamingContext:
    conf = SparkConf()
    conf.setAppName("jconf-2020 - Streaming")
    conf.setMaster(os.getenv("SPARK_MASTER"))
    sc = SparkContext(conf=conf)
    logging.info("Spark driver version: " + sc.version)
    hadoop_conf = sc._jsc.hadoopConfiguration()
    hadoop_conf.set("fs.s3.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    hadoop_conf.set("fs.s3.awsAccessKeyId", os.getenv("AWS_ACCESS_KEY_ID"))
    hadoop_conf.set("fs.s3.awsSecretAccessKey", os.getenv("AWS_SECRET_ACCESS_KEY"))
    hadoop_conf.set("fs.s3a.fast.upload", "true")
    sc.setLogLevel(os.getenv("LOGGING_LEVEL"))
    ssc = StreamingContext(sc, 1)
    ssc.checkpoint("checkpoint_streaming_jconf")
    return ssc


def main():
    try:
        logging.info("Starting up consumer...")
        ssc = configure_spark_streaming_context()
        datastream = ssc.socketTextStream(os.getenv("TCP_IP"), int(os.getenv("TCP_PORT")))
        datastream.foreachRDD(process_rdd)
        ssc.start()
        ssc.awaitTermination()
    except KeyboardInterrupt:
        logging.info('Closing producer.')


if __name__ == "__main__":
    main()
