from langchain_core.tools import tool
import yfinance as yf
from datetime import datetime
from yahooquery import search


from utils.company_resolver import resolve_company
from utils.parsed_date_format import parse_date_string

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
    - Date ranges (e.g., "last year", "2024-01-01", "January 1, 2024")
    
    The tool will:
    1. Determine if input is a ticker or company name
    2. If company name, resolve to correct ticker using LLM
    3. Verify ticker exists in yfinance
    4. Parse and convert dates to proper format
    5. Fetch and return price data
    
    Parameters:
    - query: Company name or ticker symbol
    - period: Time period (e.g., "1d", "5d", "1mo", "1y") - used if no dates provided
    - start_date: Start date - accepts many formats:
        - "YYYY-MM-DD" (e.g., "2024-01-09")
        - "last year", "1 year ago"
        - "last month", "1 month ago"
        - "January 9, 2024"
    - end_date: End date (same formats as start_date, defaults to today if not provided)
    
    Returns dict with price data or error message with suggestions.
    """
    
    ticker_symbol = None
    company_name = None
    
    print("Searching for:", query)
    
    # Fixed: Add proper error handling for yahooquery search
    try:
        ticker01 = search(query)
        
        # Check if search returned results with quotes
        if ticker01 and "quotes" in ticker01 and len(ticker01["quotes"]) > 0:
            print("Search results:", ticker01["quotes"][0]["symbol"])
            query = ticker01["quotes"][0]["symbol"]
        else:
            print("No search results found, using original query:", query)
    except Exception as e:
        print(f"Search error (using original query): {e}")
        # Continue with original query if search fails
    
    # Step 1: Determine if input is ticker or company name
    # if is_likely_ticker(query):
    # Likely a ticker symbol - try to use directly
    print("INPUT TICKER OF QUERY:", query)
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
    
    # Step 3: Parse dates if provided
    parsed_start_date = None
    parsed_end_date = None
    
    if start_date:
        parsed_start_date = parse_date_string(start_date)
        if not parsed_start_date:
            return {
                "error": "invalid_date",
                "message": f"Could not parse start date: '{start_date}'",
                "suggestion": "Use format like '2024-01-09' or 'last year' or 'January 9, 2024'"
            }
    
    if end_date:
        parsed_end_date = parse_date_string(end_date)
        if not parsed_end_date:
            return {
                "error": "invalid_date",
                "message": f"Could not parse end date: '{end_date}'",
                "suggestion": "Use format like '2024-01-09' or 'today' or 'January 9, 2024'"
            }
    
    # If start_date provided but no end_date, default to today
    if parsed_start_date and not parsed_end_date:
        parsed_end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Step 4: Fetch stock price using resolved ticker
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Get historical data
        if parsed_start_date:
            df = ticker.history(start=parsed_start_date, end=parsed_end_date)
        else:
            df = ticker.history(period=period or "5d", interval="1d")
        
        
        if df.empty:
            return {
                "error": "no_data",
                "symbol": ticker_symbol,
                "company": company_name,
                "message": f"No price data found for {company_name} ({ticker_symbol})",
                "suggestion": "The ticker might be delisted or data might be unavailable for the specified period.",
                "date_range": f"{parsed_start_date} to {parsed_end_date}" if parsed_start_date else None
            }
        
        latest = df.iloc[-1]
        first = df.iloc[0]
        
        # Calculate change from first to latest in the period
        change = float(latest["Close"] - first["Close"])
        change_percent = float((change / first["Close"]) * 100)
        
        result = {
            "success": True,
            "company": company_name,
            "symbol": ticker_symbol,
            "current_price": float(latest["Close"]),
            "current_date": str(df.index[-1].date()),
            "period_start_price": float(first["Close"]),
            "period_start_date": str(df.index[0].date()),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest["Volume"]),
        }
        
        # Add period info if date range was used
        if parsed_start_date:
            result["date_range"] = f"{df.index[0].date()} to {df.index[-1].date()}"
            result["days_in_period"] = len(df)
        
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
        baseline = successful_results[0]["current_price"]
        for result in successful_results:
            result["relative_performance"] = round(
                ((result["current_price"] - baseline) / baseline) * 100, 2
            )
    
    return {
        "comparison": results,
        "period": period,
        "compared_count": len(successful_results)
    }