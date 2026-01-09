from langchain_core.tools import tool
import yfinance as yf
from typing import Optional

from utils.company_resolver import resolve_company



def is_likely_ticker(text: str) -> bool:
    """
    Heuristic to determine if text is a ticker symbol vs company name.
    Tickers are usually:
    - Short (1-5 characters typically)
    - All caps
    - May contain dots (e.g., TCS.NS)
    """
    # Remove exchange suffix for checking
    base = text.split('.')[0]
    
    if len(base) <= 5 and base.isupper():
        return True
    
    return False


@tool
def get_stock_price(
    query: str,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
) -> dict:
    """
    Fetch stock price for ANY company by name or ticker symbol.
    
    This tool intelligently handles:
    - Company names (e.g., "Tesla", "Tata Consumer Products")
    - Ticker symbols (e.g., "TSLA", "TATACONSUM.NS")
    - Ambiguous references (e.g., "Tata" → suggests specific company)
    
    The tool will:
    1. Determine if input is a ticker or company name
    2. If company name, resolve to correct ticker using LLM
    3. Verify ticker exists in yfinance
    4. Fetch and return price data
    
    Parameters:
    - query: Company name or ticker symbol
    - period: Time period (e.g., "1d", "5d", "1mo", "1y")
    - start_date: Start date for historical data (YYYY-MM-DD)
    - end_date: End date for historical data (YYYY-MM-DD)
    
    Returns dict with price data or error message with suggestions.
    """
    
    ticker_symbol = None
    company_name = None
    
    # Step 1: Determine if input is ticker or company name
    if is_likely_ticker(query):
        # Likely a ticker symbol - try to use directly
        ticker_symbol = query.upper()
        company_name = query  # Fallback
        
        # Quick validation
        try:
            test_ticker = yf.Ticker(ticker_symbol)
            info = test_ticker.info
            if info and 'symbol' in info:
                company_name = info.get('longName', info.get('shortName', query))
            else:
                # Invalid ticker, try resolving as company name
                ticker_symbol = None
        except:
            ticker_symbol = None
    
    # Step 2: If not a valid ticker, resolve as company name
    if not ticker_symbol:
        resolved, candidates = resolve_company(query, auto_select=False)
        
        if resolved:
            # Unambiguous - use it
            ticker_symbol = resolved.ticker
            company_name = resolved.common_name
            
        elif candidates and len(candidates) > 1:
            # Ambiguous - return options for user to clarify
            candidates_text = "\n".join([
                f"  - {c.common_name} ({c.ticker}): {c.description}"
                for c in candidates
            ])
            
            return {
                "error": "ambiguous_company",
                "message": f"Multiple companies found for '{query}'. Please specify:",
                "candidates": candidates_text,
                "suggestion": "Try using the specific company name or ticker symbol from the list above."
            }
        
        elif candidates and len(candidates) == 1:
            # Single candidate found
            ticker_symbol = candidates[0].ticker
            company_name = candidates[0].common_name
        
        else:
            # No matches found
            return {
                "error": "company_not_found",
                "message": f"Could not find company or ticker: '{query}'",
                "suggestion": "Please check the spelling or try using the official ticker symbol."
            }
    
    # Step 3: Fetch stock price using resolved ticker
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Get historical data
        if start_date:
            df = ticker.history(start=start_date, end=end_date)
        else:
            df = ticker.history(period=period or "5d", interval="1d")
        
        if df.empty:
            return {
                "error": "no_data",
                "symbol": ticker_symbol,
                "company": company_name,
                "message": f"No price data found for {company_name} ({ticker_symbol})",
                "suggestion": "The ticker might be delisted or data might be unavailable for the specified period."
            }
        
        latest = df.iloc[-1]
        
        # Calculate change if we have multiple days
        change = None
        change_percent = None
        if len(df) > 1:
            previous = df.iloc[-2]["Close"]
            current = latest["Close"]
            change = float(current - previous)
            change_percent = float((change / previous) * 100)
        
        result = {
            "success": True,
            "company": company_name,
            "symbol": ticker_symbol,
            "price": float(latest["Close"]),
            "date": str(df.index[-1].date()),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"]),
        }
        
        if change is not None:
            result["change"] = round(change, 2)
            result["change_percent"] = round(change_percent, 2)
        
        return result
    
    except Exception as e:
        return {
            "error": "fetch_failed",
            "symbol": ticker_symbol,
            "company": company_name,
            "message": f"Error fetching stock price: {str(e)}",
            "suggestion": "Please verify the ticker symbol or try again later."
        }


@tool
def compare_stock_prices(
    queries: list[str],
    period: str = "1mo"
) -> dict:
    """
    Compare stock prices of multiple companies over a period.
    
    Useful for queries like:
    - "Compare Tesla and GM stock prices"
    - "Show me Tata Steel vs Tata Motors performance"
    
    Parameters:
    - queries: List of company names or ticker symbols
    - period: Time period for comparison (e.g., "1mo", "3mo", "1y")
    
    Returns comparison data for all requested companies.
    """
    
    results = []
    
    for query in queries:
        price_data = get_stock_price.invoke({"query": query, "period": period})
        results.append(price_data)
    
    # Calculate relative performance if all successful
    successful_results = [r for r in results if r.get("success")]
    
    if len(successful_results) > 1:
        # Add relative performance comparison
        baseline = successful_results[0]["price"]
        for result in successful_results:
            result["relative_performance"] = round(
                ((result["price"] - baseline) / baseline) * 100, 2
            )
    
    return {
        "comparison": results,
        "period": period,
        "compared_count": len(successful_results)
    }