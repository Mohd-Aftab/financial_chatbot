from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from vector_store_manager import vector_store
from typing import Optional
from utils.company_resolver import resolve_company


def extract_company_from_query(query: str) -> Optional[str]:
    """
    Extract and resolve company name from the query.
    Returns canonical company name if found, None otherwise.
    """
    try:
        # Use our resolver to identify the company
        resolved, candidates = resolve_company(query, auto_select=True)
        
        if resolved:
            return resolved.canonical_name
        
        return None
    except Exception as e:
        print(f"Company extraction failed: {e}")
        return None


def build_metadata_filter(
    company_name: Optional[str] = None,
    data_types: Optional[list[str]] = None,
    thread_id: Optional[str] = None
):
    """
    Build a metadata filter function for FAISS retrieval.
    
    This ensures:
    - Only documents for the specified company are retrieved
    - Only specified data types are included (news, earnings_call)
    - Thread-specific data is included when available
    """
    
    def filter_fn(metadata: dict) -> bool:
        # Always include thread-specific temporary data
        if thread_id and metadata.get("thread_id") == thread_id:
            return True
        
        # Check company match (CRITICAL: prevents cross-contamination)
        if company_name:
            doc_company = metadata.get("company", "").lower()
            query_company = company_name.lower()
            
            # Exact match or substring match
            if query_company not in doc_company and doc_company not in query_company:
                return False
        
        # Check data type
        if data_types:
            doc_type = metadata.get("data_type")
            if doc_type not in data_types:
                return False
        
        return True
    
    return filter_fn


@tool
def rag_tool(query: str, config: RunnableConfig) -> dict:
    """
    Enhanced RAG tool with company-aware retrieval.
    
    Improvements:
    1. Extracts company name from query
    2. Filters results to ONLY that company's documents
    3. Returns empty context if no data exists (safe fallback)
    4. Provides metadata about what data was found
    """
    
    thread_id = config["configurable"].get("thread_id")
    
    # Step 1: Identify which company is being asked about
    company_name = extract_company_from_query(query)
    
    # Step 2: Build smart filter
    filter_fn = build_metadata_filter(
        company_name=company_name,
        data_types=["earnings_call", "news"],
        thread_id=thread_id
    )
    
    # Step 3: Retrieve with filtering
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 5,  # Increased from 4 to get more context
            "filter": filter_fn
        }
    )
    
    try:
        results = retriever.invoke(query)
    except Exception as e:
        print(f"Retrieval error: {e}")
        results = []
    
    # Step 4: Validate and structure results
    if not results:
        return {
            "query": query,
            "company": company_name,
            "context": [],
            "metadata": [],
            "warning": f"No data found for {company_name}. Vector store may not contain earnings calls or news for this company."
        }
    
    # Step 5: Organize by data type for better context
    earnings_docs = []
    news_docs = []
    other_docs = []
    
    for doc in results:
        data_type = doc.metadata.get("data_type", "unknown")
        
        if data_type == "earnings_call":
            earnings_docs.append(doc)
        elif data_type == "news":
            news_docs.append(doc)
        else:
            other_docs.append(doc)
    
    return {
        "query": query,
        "company": company_name,
        "context": [doc.page_content for doc in results],
        "metadata": [doc.metadata for doc in results],
        "summary": {
            "total_documents": len(results),
            "earnings_calls": len(earnings_docs),
            "news_articles": len(news_docs),
            "other": len(other_docs)
        }
    }


@tool  
def check_data_availability(company_name: str, config: RunnableConfig) -> dict:
    """
    Check what data is available for a specific company in the vector store.
    
    Use this BEFORE attempting to answer questions about earnings or company analysis.
    This prevents hallucinations by explicitly checking data availability.
    """
    
    thread_id = config["configurable"].get("thread_id")
    
    # Resolve company name
    resolved, _ = resolve_company(company_name, auto_select=True)
    
    if not resolved:
        return {
            "company": company_name,
            "available": False,
            "message": f"Could not resolve company name: {company_name}"
        }
    
    canonical_name = resolved.canonical_name
    
    # Search for any documents related to this company
    filter_fn = build_metadata_filter(
        company_name=canonical_name,
        thread_id=thread_id
    )
    
    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 20,  # Get more docs to check
            "filter": filter_fn
        }
    )
    
    # Use a generic query to find any company documents
    test_query = f"{canonical_name} company information"
    
    try:
        results = retriever.invoke(test_query)
    except:
        results = []
    
    if not results:
        return {
            "company": canonical_name,
            "ticker": resolved.ticker,
            "available": False,
            "earnings_calls": 0,
            "news_articles": 0,
            "message": f"No data available for {canonical_name}. Consider ingesting news or earnings data first."
        }
    
    # Count data types
    earnings_count = sum(1 for doc in results if doc.metadata.get("data_type") == "earnings_call")
    news_count = sum(1 for doc in results if doc.metadata.get("data_type") == "news")
    
    return {
        "company": canonical_name,
        "ticker": resolved.ticker,
        "available": True,
        "earnings_calls": earnings_count,
        "news_articles": news_count,
        "total_documents": len(results),
        "message": f"Data available: {earnings_count} earnings call documents, {news_count} news articles"
    }