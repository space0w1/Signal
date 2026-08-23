import yfinance as yf
from datetime import datetime

# Specific tickers to pull conversion to SGD
tickers = ["HKDSGD=X", "USDSGD=X"]

print(f"Fetching current SGD rates for HKD and USD: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Fetch data snapshot
fx_data = yf.Tickers(tickers)

for ticker in tickers:
    try:
        info = fx_data.tickers[ticker].info
        current_rate = info.get("regularMarketPrice")
        prev_close = info.get("previousClose")

        # Format names cleanly (e.g., HKD to SGD)
        base_currency = ticker[:3]

        if current_rate:
            print(f"💵 1 {base_currency} = {current_rate:.4f} SGD")
            print(f"   • Previous Session Close: {prev_close:.4f}")
            print("-" * 40)
        else:
            print(f"⚠️ {base_currency} to SGD data is temporarily unavailable.")

    except Exception as e:
        print(f"❌ Error pulling {ticker}: {e}")
