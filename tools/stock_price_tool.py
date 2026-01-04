from langchain_core.tools import tool
import yfinance as yf

@tool
def get_stock_price(
    symbol: str,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
) -> dict:
    """
    Fetch stock price using Yahoo Finance.
    Supports both recent prices and historical date comparison.
    """
    try:
        ticker = yf.Ticker(symbol)

        # Historical date-based query
        if start_date:
            df = ticker.history(start=start_date, end=end_date)
        else:
            df = ticker.history(period=period or "5d", interval="1d")

        if df.empty:
            return {"error": f"No price data found for {symbol}"}

        latest = df.iloc[-1]

        return {
            "symbol": symbol,
            "price": float(latest["Close"]),
            "date": str(df.index[-1]),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"])
        }

    except Exception as e:
        return {"error": str(e)}