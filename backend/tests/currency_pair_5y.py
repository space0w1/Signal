import yfinance as yf

tickers = ["HKDSGD=X", "USDSGD=X"]

# Option 1: Batch download for multiple FX tickers at once
print("Downloading 5 years of daily data...")
fx_history = yf.download(tickers, period="5y", interval="1d")

# View the Close prices for both currencies
close_prices = fx_history["Close"]
print("\n--- Last 5 Rows ---")
print(close_prices.tail())

# Option 2: Loop using individual Ticker objects
for ticker_symbol in tickers:
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period="5y")

    print(f"\nFetched {len(df)} trading days for {ticker_symbol}")
    print(df[['Open', 'High', 'Low', 'Close']].head(3))