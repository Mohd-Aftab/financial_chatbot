from data_ingestion.fetch_articles import fetch_company_news
from data_ingestion.state import INGESTED_NEWS_URLS, NEWS_HISTORY_FILE
from utils.company_resolver import resolve_company
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

def filter_new_articles(articles):
    """Filter out already ingested articles to avoid duplicates"""
    new_articles = []
    
    with open(NEWS_HISTORY_FILE, "a", encoding="utf-8") as f:
        for article in articles:
            url = article.get("url")
            
            if not url or url in INGESTED_NEWS_URLS:
                continue
            
            INGESTED_NEWS_URLS.add(url)
            f.write(f"{url}\n")
            new_articles.append(article)
    
    return new_articles


def ingest_news_into_vector_store(
    canonical_name: str,
    ticker: str,
    articles: list,
    existing_vector_store,
    sector: Optional[str] = None,
    industry: Optional[str] = None
):
    """
    Ingest news articles with enhanced metadata.
    
    Metadata includes:
    - company: Canonical company name (for filtering)
    - ticker: Stock symbol
    - data_type: Always "news"
    - source: Article source
    - title: Article title
    - url: Original URL
    - published_at: Publication date
    - sector: Company sector (optional)
    - industry: Company industry (optional)
    """
    
    documents = []
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    for article in articles:
        print(f"Processing article: {type(article)} - {article.get('title', 'No Title')}")
        # Validate content
        full_text = article.get("full_content", "")
        
        if not full_text or len(full_text.strip()) < 50:
            continue
        
        # Create rich metadata
        metadata = {
            "company": canonical_name,
            "ticker": ticker,
            "data_type": "news",
            "source": article.get("source", {}),
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "published_at": article.get("publishedAt", ""),
            "ingested_at": datetime.now().isoformat(),
        }
        
        # Add optional metadata
        if sector:
            metadata["sector"] = sector
        if industry:
            metadata["industry"] = industry
        
        doc = Document(
            page_content=full_text,
            metadata=metadata
        )
        
        documents.append(doc)
    
    if not documents:
        print(f"⚠️  No valid news content found for {canonical_name}")
        return existing_vector_store, 0
    
    # Split documents
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    
    chunks = splitter.split_documents(documents)
    
    # Add to vector store
    existing_vector_store.add_documents(chunks)
    
    print(f"✅ Ingested {len(chunks)} chunks from {len(documents)} news articles for {canonical_name}")
    
    return existing_vector_store, len(documents)


def auto_ingest_company_news(
    company_query: str,
    news_api_key: str,
    existing_vector_store
) -> dict:
    """
    Fully automated news ingestion pipeline with company resolution.
    
    Returns:
    - dict with status, company info, and ingestion summary
    """
    
    # Step 1: Resolve company identity
    resolved, candidates = resolve_company(company_query, auto_select=False)
    
    if not resolved and candidates:
        # Ambiguous - return for user to clarify
        candidates_text = "\n".join([
            f"  - {c.common_name} ({c.ticker}): {c.description}"
            for c in candidates
        ])
        
        return {
            "status": "ambiguous",
            "message": f"Multiple companies found for '{company_query}'. Please specify:",
            "candidates": candidates_text
        }
    
    if not resolved:
        return {
            "status": "error",
            "message": f"Could not resolve company: {company_query}"
        }
    
    canonical_name = resolved.canonical_name
    ticker = resolved.ticker
    sector = resolved.sector
    industry = resolved.industry
    
    print(f"📰 Fetching news for {canonical_name} ({ticker})...")
    
    # Step 2: Fetch news articles
    try:
        articles = fetch_company_news(canonical_name, news_api_key)
    except Exception as e:
        return {
            "status": "error",
            "company": canonical_name,
            "message": f"Failed to fetch news: {str(e)}"
        }
    
    if not articles:
        return {
            "status": "no_news",
            "company": canonical_name,
            "ticker": ticker,
            "message": f"No recent news found for {canonical_name}"
        }
    
    # Step 3: Filter for new articles
    new_articles = filter_new_articles(articles)
    
    if not new_articles:
        return {
            "status": "already_ingested",
            "company": canonical_name,
            "ticker": ticker,
            "message": f"All news for {canonical_name} has already been ingested"
        }
    
    # Step 4: Prepare full content (using description as fallback)
    for article in new_articles:
        article["source"] = "news"
        article["full_content"] = article.get("description", article.get("content", ""))
    
    # Step 5: Ingest into vector store
    _, ingested_count = ingest_news_into_vector_store(
        canonical_name=canonical_name,
        ticker=ticker,
        articles=new_articles,
        existing_vector_store=existing_vector_store,
        sector=sector,
        industry=industry
    )
    
    return {
        "status": "success",
        "company": canonical_name,
        "ticker": ticker,
        "articles_ingested": ingested_count,
        "message": f"Successfully ingested {ingested_count} news articles for {canonical_name}"
    }