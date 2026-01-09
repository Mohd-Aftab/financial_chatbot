from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Optional
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


class CompanyCandidate(BaseModel):
    """A potential company match"""
    canonical_name: str = Field(description="Official company name (e.g., 'Tata Consultancy Services Limited')")
    common_name: str = Field(description="Commonly used name (e.g., 'TCS')")
    ticker: str = Field(description="Stock ticker symbol (e.g., 'TCS.NS' for NSE, 'TCS.BO' for BSE)")
    exchange: str = Field(description="Primary exchange (NSE, BSE, NYSE, NASDAQ, etc.)")
    description: str = Field(description="Brief description to help user distinguish (e.g., 'IT Services and Consulting')")


class CompanyResolution(BaseModel):
    """Result of company name resolution"""
    is_ambiguous: bool = Field(description="True if multiple companies match")
    candidates: List[CompanyCandidate] = Field(description="List of possible companies")
    reasoning: str = Field(description="Explanation of the resolution logic")


class ResolvedCompany(BaseModel):
    """Final resolved company with verified symbol"""
    canonical_name: str
    common_name: str
    ticker: str
    exchange: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_verified: bool = Field(default=False, description="Whether ticker was verified with yfinance")


def resolve_company_query(user_query: str) -> CompanyResolution:
    """
    Step 1: Analyze user query and identify potential company matches.
    This uses LLM to understand context and find all possible interpretations.
    """
    
    prompt = f"""You are a financial data expert. Analyze this user query and identify ALL possible companies they might be referring to.

User query: "{user_query}"

Consider:
1. Parent companies vs subsidiaries (e.g., "Tata" could mean Tata Sons, TCS, Tata Motors, Tata Steel, Tata Consumer)
2. Common abbreviations (e.g., "TCS" = Tata Consultancy Services)
3. Name variations (e.g., "Tesla" = "Tesla Inc" = "Tesla Motors")
4. Indian companies: Provide both NSE (.NS) and BSE (.BO) symbols when applicable
5. Context clues in the query (e.g., "IT company" suggests TCS over Tata Steel)

Rules:
- If query is SPECIFIC (e.g., "Tata Consumer Products"), return only that company
- If query is AMBIGUOUS (e.g., "Tata", "Apple" when both Apple Inc and Apple Hospitality REIT exist), return ALL matches
- Include sector/industry info to help disambiguation
- For Indian companies, prefer NSE symbols (.NS) as primary
- Verify ticker symbols are in correct yfinance format

Return a structured analysis of potential matches."""

    structured_llm = llm.with_structured_output(CompanyResolution)
    result = structured_llm.invoke(prompt)
    
    return result


def verify_ticker_with_yfinance(ticker: str) -> tuple[bool, dict]:
    """
    Step 2: Verify that a ticker symbol actually exists and get additional metadata.
    Returns (is_valid, info_dict)
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if we got valid data
        if not info or 'symbol' not in info:
            return False, {}
        
        # Extract useful information
        verified_info = {
            'longName': info.get('longName', ''),
            'shortName': info.get('shortName', ''),
            'symbol': info.get('symbol', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'exchange': info.get('exchange', 'Unknown'),
            'currency': info.get('currency', 'USD'),
        }
        
        return True, verified_info
        
    except Exception as e:
        print(f"Ticker verification failed for {ticker}: {e}")
        return False, {}


def select_best_candidate(
    candidates: List[CompanyCandidate],
    user_query: str
) -> CompanyCandidate:
    """
    Step 3: If multiple candidates, use LLM to select the most likely match
    based on query context.
    """
    
    if len(candidates) == 1:
        return candidates[0]
    
    candidates_text = "\n".join([
        f"{i+1}. {c.common_name} ({c.canonical_name}) - {c.ticker} - {c.description}"
        for i, c in enumerate(candidates)
    ])
    
    prompt = f"""Given this user query: "{user_query}"

Which company is most likely being referenced?

Candidates:
{candidates_text}

Consider:
- Specific context in the query
- Most commonly referenced company with that name
- If still ambiguous, prefer the largest/most prominent company

Return ONLY the number (1, 2, 3, etc.) of the most likely candidate."""

    response = llm.invoke(prompt)
    
    try:
        selected_idx = int(response.content.strip()) - 1
        return candidates[selected_idx]
    except:
        # Default to first candidate if parsing fails
        return candidates[0]


def resolve_company(
    user_query: str,
    auto_select: bool = False
) -> tuple[Optional[ResolvedCompany], Optional[List[CompanyCandidate]]]:
    """
    Main function: Complete company resolution pipeline.
    
    Args:
        user_query: User's input (e.g., "What's the stock price of Tata?")
        auto_select: If True, automatically picks best match for ambiguous queries
                    If False, returns candidates for user to choose from
    
    Returns:
        (resolved_company, candidates_for_disambiguation)
        
        If unambiguous: (ResolvedCompany, None)
        If ambiguous and auto_select=True: (ResolvedCompany, None)
        If ambiguous and auto_select=False: (None, List[CompanyCandidate])
    """
    
    # Step 1: Analyze query
    resolution = resolve_company_query(user_query)
    
    if not resolution.candidates:
        return None, None
    
    # Step 2: If unambiguous, verify and return
    if not resolution.is_ambiguous or len(resolution.candidates) == 1:
        candidate = resolution.candidates[0]
        
        # Verify ticker
        is_valid, info = verify_ticker_with_yfinance(candidate.ticker)
        
        resolved = ResolvedCompany(
            canonical_name=info.get('longName', candidate.canonical_name),
            common_name=info.get('shortName', candidate.common_name),
            ticker=candidate.ticker,
            exchange=info.get('exchange', candidate.exchange),
            sector=info.get('sector'),
            industry=info.get('industry'),
            is_verified=is_valid
        )
        
        return resolved, None
    
    # Step 3: Handle ambiguous cases
    if auto_select:
        # Let LLM pick the most likely candidate
        best_candidate = select_best_candidate(resolution.candidates, user_query)
        
        is_valid, info = verify_ticker_with_yfinance(best_candidate.ticker)
        
        resolved = ResolvedCompany(
            canonical_name=info.get('longName', best_candidate.canonical_name),
            common_name=info.get('shortName', best_candidate.common_name),
            ticker=best_candidate.ticker,
            exchange=info.get('exchange', best_candidate.exchange),
            sector=info.get('sector'),
            industry=info.get('industry'),
            is_verified=is_valid
        )
        
        return resolved, None
    else:
        # Return candidates for user to choose
        return None, resolution.candidates


# Helper function for getting ticker from company name
def get_ticker_for_company(company_name: str) -> Optional[str]:
    """
    Convenience function: Given a company name, return verified ticker symbol.
    """
    resolved, _ = resolve_company(company_name, auto_select=True)
    
    if resolved and resolved.is_verified:
        return resolved.ticker
    
    return None