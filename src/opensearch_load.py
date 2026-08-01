import os
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import concat, lit, date_format
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
import re
from typing import Optional

def extract_ticker_symbol(file_name: str) -> Optional[str]:
    pattern = r"^1min_(\w+).csv$"
    match = re.search(pattern, file_name)
    return match.group(1) if match else None

def main():
    spark_session: SparkSession = SparkSession.builder.appName("OpenSearchIngestion").getOrCreate()
    password: str = os.environ["OPENSEARCH_INITIAL_ADMIN_PASSWORD"]
    schema: StructType = StructType([
        StructField("timestamp", TimestampType(), False),
        StructField("open", DoubleType(), False),
        StructField("high", DoubleType(), False),
        StructField("low", DoubleType(), False),
        StructField("close", DoubleType(), False),
        StructField("volume", IntegerType(), False)
    ])
    directory_path: str = "/opt/spark/work-dir/temp"
    for file_name in os.listdir(directory_path):
        ticker_symbol = extract_ticker_symbol(file_name)
        if ticker_symbol:
            file_path = os.path.join(directory_path, file_name)
            print(f"Processing: {file_path}")
            df: DataFrame = spark_session.read.option("header", True).csv(file_path)
            df = df.withColumn("symbol", lit(ticker_symbol).cast(StringType()))
            # Convert timestamp to strict_date_time_no_millis format string
            df = df.withColumn("timestamp", date_format("timestamp", "yyyy-MM-dd'T'HH:mm:ssXXX"))
            # lit("-") is needed, otherwise it will try to find a column with that name
            df = df.withColumn("id", concat(df["symbol"], lit("-"), df["timestamp"]))
            df.write.format("opensearch") \
                .option("opensearch.nodes", "host.docker.internal") \
                .option("opensearch.net.ssl", "true") \
                .option("opensearch.net.ssl.cert.allow.self.signed", "true") \
                .option("opensearch.net.http.auth.user", "admin") \
                .option("opensearch.net.http.auth.pass", password) \
                .option("opensearch.write.operation", "upsert") \
                .option("opensearch.mapping.id", "id") \
                .save("ticker_history", mode="append") # append is needed in addition to upsert

if __name__ == "__main__":
    main()
