from langchain_core.tools import tool
from data_ingestion.auto_news_pipeline import auto_ingest_company_news
from vector_store_manager import final_vector_store
from dotenv import load_dotenv
import os

load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


@tool
def ingest_company_news(company_query: str) -> dict:
    """
    Ingest recent news articles for any company into the vector store.
    
    This tool:
    1. Resolves the company name to canonical form and ticker
    2. Handles ambiguous company references (e.g., "Tata" → asks for clarification)
    3. Fetches recent news from NewsAPI
    4. Embeds and stores news in the vector store with rich metadata
    5. Prevents duplicate ingestion
    
    Use this tool when:
    - User asks about recent news or current events for a company
    - You need up-to-date context before answering qualitative questions
    - User wants to know "what's happening" with a company
    
    After successful ingestion, you MUST use rag_tool to retrieve
    and summarize the news for the user.
    
    Parameters:
    - company_query: Company name (e.g., "Tesla", "Tata Consumer Products", "TCS")
    
    Returns:
    - Status of ingestion with details about articles added
    - If ambiguous, returns list of candidates for clarification
    """
    
    result = auto_ingest_company_news(
        company_query=company_query,
        news_api_key=NEWS_API_KEY,
        existing_vector_store=final_vector_store
    )
    
    # Format response based on status
    if result["status"] == "success":
        return {
            "status": "success",
            "message": f"✅ Successfully ingested {result['articles_ingested']} news articles for {result['company']} ({result['ticker']}). NOW use rag_tool to retrieve and summarize these articles.",
            "company": result["company"],
            "ticker": result["ticker"],
            "articles_count": result["articles_ingested"],
            "next_action": "Use rag_tool to retrieve these articles"
        }
    
    elif result["status"] == "ambiguous":
        return {
            "status": "needs_clarification",
            "message": result["message"],
            "candidates": result["candidates"],
            "next_action": "Ask user to specify which company they mean"
        }
    
    elif result["status"] == "no_news":
        return {
            "status": "no_news",
            "message": f"No recent news found for {result['company']}. This might mean:\n- Company is not in major news currently\n- NewsAPI limits reached\n- Company name not well-known in news sources",
            "company": result["company"],
            "ticker": result["ticker"],
            "next_action": "Inform user and offer to check stock price or earnings data instead"
        }
    
    elif result["status"] == "already_ingested":
        return {
            "status": "already_current",
            "message": f"News for {result['company']} is already up to date. Use rag_tool to retrieve existing news.",
            "company": result["company"],
            "ticker": result["ticker"],
            "next_action": "Use rag_tool to retrieve existing news"
        }
    
    else:  # error
        return {
            "status": "error",
            "message": result.get("message", "Unknown error during news ingestion"),
            "next_action": "Inform user and suggest alternative approaches"
        }