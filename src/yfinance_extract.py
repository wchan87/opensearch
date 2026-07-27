import argparse
import pandas as pd
import sys
import yfinance as yf

def main(ticker_symbol: str) -> int:
    ticker: yf.Ticker = yf.Ticker(ticker_symbol)
    bars: pd.DataFrame = ticker.history(period="7d", interval="1m", prepost=True,
                          auto_adjust=False, actions=False)
    bars = bars.tz_convert("America/New_York")
    bars.index.name = "timestamp"
    bars = bars[["Open", "High", "Low", "Close", "Volume"]]
    bars.columns = [c.lower() for c in bars.columns]
    bars.to_csv(f"temp/1min_{ticker_symbol}.csv")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script for extracting historical financial data from Yahoo Finance.")
    parser.add_argument("-t", "--ticker", required=True, help="Specify ticker symbol")
    args = parser.parse_args()
    sys.exit(main(args.ticker))
