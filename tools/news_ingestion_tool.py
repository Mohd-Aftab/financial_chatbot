from langchain_core.tools import tool
from data_ingestion.auto_news_pipeline import auto_ingest_company_news
from dotenv import load_dotenv

import os
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

@tool
def ingest_company_news(
    company_query: str,
) -> dict:
    """
    Ingest recent news articles for a specified company into the vector store.

    This tool performs a full automated news ingestion pipeline:
        1) Resolves the canonical company name and official stock ticker
            from a user-provided company reference (e.g. "Tesla", "Tesla Motors").
        2) Fetches recent news articles related to the company from NewsAPI.
        3) Extracts full article content from each news URL.
        4) Embeds and stores the processed news content into the existing
            vector store used by the RAG pipeline.

    The vector store is retrieved from the current LangGraph state,
    updated in-place with newly ingested news documents, and written
    back to the state.

    Intended use cases:
        - When the user asks about recent news, current events, or developments
        affecting a company.
        - To ensure the RAG system has up-to-date contextual information
        before answering qualitative questions.

    This tool does NOT:
        - Return news content directly to the user.
        - Perform live financial data queries (prices, ratios, metrics).
        - Answer user questions by itself.
    """
    auto_ingest_company_news(
        company_query=company_query,
        news_api_key=NEWS_API_KEY,
    )
    # 2. NEW: Retrieve the top articles to return to the LLM immediately
    # We can quickly fetch the added articles from the vector store or return a simple summary
    # For simplicity, let's return a prompt forcing the LLM to check the store.
    
    return f"Successfully ingested news for {company_query}. NOW, you must use the rag_tool to retrieve these articles and summarize them for the user."