from langchain_core.tools import tool

from vector_store_manager import vector_store

from langchain_core.runnables import RunnableConfig

@tool
def rag_tool(query: str, config:RunnableConfig) -> dict:
    """
    Retrieve contextually relevant information using a Retrieval-Augmented
    Generation (RAG) pipeline built from company earnings call transcripts
    and recently ingested news articles.

    This tool searches a FAISS vector store that may contain:
      1) Earnings call transcript documents
         - management commentary
         - analyst Q&A discussions
      2) News articles related to one or more companies
         - recent developments and announcements
         - partnerships, launches, and regulatory updates
         - macroeconomic or industry events impacting companies

    The tool is intended for answering qualitative, explanatory, and
    context-driven questions such as:
      - company strategy, outlook, and guidance
      - key risks and challenges discussed by leadership
      - growth drivers and long-term vision
      - explanations behind recent performance or decisions
      - how recent news events may impact a company’s future direction

    The tool retrieves information only from the existing vector store
    available in the current LangGraph state. It does NOT:
      - fetch live or real-time data
      - trigger news ingestion or external API calls
      - compute structured financial metrics such as prices, revenues,
        ratios, or tabular financial statements
    """
    
    thread_id = config["configurable"].get("thread_id")
    
    search_filter = {"thread_id": thread_id}

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 4, 
            "filter": lambda metadata: (
              metadata.get("thread_id") == thread_id 
              or metadata.get("data_type") == "earnings_call"
              or metadata.get("data_type") == "news"
            )
        }
    )

    result = retriever.invoke(query)

    return {
        "query": query,
        "context": [doc.page_content for doc in result],
        "metadata": [doc.metadata for doc in result],
    }