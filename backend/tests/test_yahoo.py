import yfinance as yf
import trafilatura

TICKER_SYMBOLS = ["AIY.SI", "0700.HK", "AAPL"]


def fetch_article_text(url: str) -> str:
    """Download a news article and extract its main text content."""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return "(Could not download article)"

    text = trafilatura.extract(downloaded)
    return text or "(Could not extract article content)"


def process_ticker(ticker_symbol: str) -> None:
    stock = yf.Ticker(ticker_symbol)

    # 1. Fetch Key Metadata
    info = stock.info
    print("=" * 45)
    print(f"  Company: {info.get('longName', ticker_symbol)}")
    print(f"  Sector:  {info.get('sector', 'N/A')}")
    print(f"  Market Cap: ${info.get('marketCap', 0):,}")
    print("=" * 45)

    # 2. Fetch Historical Stock Prices (Last 5 Days)
    print("\n--- Last 5 Trading Days ---")
    hist = stock.history(period="5d")
    print(hist[['Open', 'High', 'Low', 'Close', 'Volume']])

    # 3. Fetch Recent News Headlines
    print("\n--- Recent News Headlines ---")
    news = stock.news
    for idx, item in enumerate(news[:5], 1):
        # Handle both new 'content' schema and legacy schema
        content = item.get('content', {}) if isinstance(item.get('content'), dict) else item

        title = content.get('title') or item.get('title', 'No Title')
        publisher = (
                content.get('provider', {}).get('displayName')
                or item.get('publisher', 'Unknown')
        )

        # Extract Article URL
        click_through = content.get('canonicalUrl') or content.get('clickThroughUrl')
        link = click_through.get('url') if isinstance(click_through, dict) else (
                content.get('link') or item.get('link', 'No Link Available')
        )

        print(f"{idx}. {title}")
        print(f"   Source: {publisher}")
        print(f"   URL:    {link}\n")

        if link and link != "No Link Available":
            article_text = fetch_article_text(link)
            print(f"   --- Article Content ---\n{article_text}\n")


for ticker_symbol in TICKER_SYMBOLS:
    process_ticker(ticker_symbol)
