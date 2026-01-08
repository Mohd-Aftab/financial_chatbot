from langchain_core.tools import tool
from vector_store_manager import vector_store
from langchain_core.runnables import RunnableConfig

@tool
def rag_tool(query: str, ticker: str, config: RunnableConfig) -> dict:
    """
    Retrieve contextually relevant information using a RAG pipeline.
    
    Args:
        query: The user's search query.
        ticker: The stock ticker symbol (e.g., "AAPL", "NVDA"). 
                Must match the ticker used during data ingestion.
    """
    
    # DEBUG: Print what the bot is searching for
    print(f"🔍 RAG Tool Search - Query: '{query}' | Ticker: '{ticker}'")

    thread_id = config["configurable"].get("thread_id")
    
    def metadata_filter(metadata):
        # 1. Allow thread-specific documents (private context)
        if metadata.get("thread_id") == thread_id:
            return True
        
        # 2. For shared public data, check Ticker (CASE INSENSITIVE)
        if metadata.get("data_type") in ["earnings_call", "news"]:
            stored_ticker = metadata.get("ticker", "")
            # Normalize both to uppercase for comparison
            return stored_ticker.upper() == ticker.upper()
            
        return False

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 4, 
            "filter": metadata_filter
        }
    )

    result = retriever.invoke(query)
    
    # DEBUG: Print how many docs were found
    print(f"✅ Found {len(result)} documents for {ticker}")

    return {
        "query": query,
        "ticker": ticker,
        "context": [doc.page_content for doc in result],
        "metadata": [doc.metadata for doc in result],
    }