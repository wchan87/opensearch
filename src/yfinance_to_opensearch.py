import os
import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import concat, lit
import yfinance as yf

def get_data(ticker_symbol: str) -> pd.DataFrame:
    ticker: yf.Ticker = yf.Ticker(ticker_symbol)
    bars: pd.DataFrame = ticker.history(period="7d", interval="1m", prepost=True,
                                        auto_adjust=False, actions=False)
    bars = bars.tz_convert("America/New_York")
    bars.index.name = "timestamp"
    bars = bars[["Open", "High", "Low", "Close", "Volume"]]
    bars.columns = [c.lower() for c in bars.columns]
    return bars.reset_index()

def main():
    spark_session: SparkSession = SparkSession.builder.appName("OpenSearchIngestion").getOrCreate()
    password: str = os.environ["OPENSEARCH_INITIAL_ADMIN_PASSWORD"]
    ticker_symbol: str = "TSLA"
    bars: pd.DataFrame = get_data(ticker_symbol)
    df: DataFrame = spark_session.createDataFrame(bars)
    df = df.withColumn("symbol", lit(ticker_symbol))
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
