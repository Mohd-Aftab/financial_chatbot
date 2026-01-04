from data_ingestion.fetch_articles import fetch_company_news
from data_ingestion.fetch_fullcontent import fetch_full_article
from data_ingestion.news_ingestor import ingest_news_articles
from output_schemas.company_schema import resolve_company_identity
from data_ingestion.state import INGESTED_NEWS_URLS, NEWS_HISTORY_FILE

from vector_store_manager import vector_store


def filter_new_articles(articles):
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


def auto_ingest_company_news(
    company_query: str,
    news_api_key: str,
):
    """
    Fully automated news ingestion pipeline for any company.
    Handles:
    - company name normalization
    - ticker resolution
    - news fetching
    - full article extraction
    - vector store ingestion
    """

    # 1️⃣ Resolve canonical identity
    identity = resolve_company_identity(company_query)

    canonical_name = identity["canonical_name"]
    ticker = identity["ticker"]

    # 2️⃣ Fetch news using canonical name
    articles = fetch_company_news(canonical_name, news_api_key)
    
    new_articles = filter_new_articles(articles)

    # 3️⃣ Fetch full article content
    for article in new_articles:
        # article["full_content"] = fetch_full_article(article["url"])
        article["source"] = "news"
        # article['full_content'] = article["content"]
        article['full_content'] = article["description"]
        
    

    # 4️⃣ Ingest into vector store
    ingest_news_articles(
        company=canonical_name,
        ticker=ticker,
        articles=new_articles,
        existing_vector_store=vector_store
    )

    return
