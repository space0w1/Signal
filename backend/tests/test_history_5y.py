import yfinance as yf

ticker_symbol = "AAPL"
stock = yf.Ticker(ticker_symbol)

hist = stock.history(period="5y")
print(hist)
