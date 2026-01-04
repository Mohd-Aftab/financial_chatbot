from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

def ingest_news_articles(
    company:str,
    articles:list,
    ticker:str,
    existing_vector_store: FAISS | None = None
):
    """
    Ingest news articles into FAISS vector store.
    If existing_vector_store is provided, news is added to it.
    """
    
    documents = []
    
    for article in articles:
        
        full_text = article.get("full_content")

        # 🔐 HARD VALIDATION (prevents FAISS crash)
        if (
            not full_text
            or not isinstance(full_text, str)
            or len(full_text.strip()) < 50
        ):
            continue
        
        doc = Document(
            page_content=full_text,
            metadata = {
                "company": company,
                "ticker": ticker,
                "data_type": "news",
                "source": article.get("source", "NewsAPI"),
                "title": article.get("title"),
                "url": article.get("url"),
            }
        )
        
        documents.append(doc)
        
    if not documents or len(documents) == 0:
        print(f"No valid news content found for {company}. Skipping FAISS update.")
        return existing_vector_store
        
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    chunks = splitter.split_documents(documents)
    
    if existing_vector_store:
        existing_vector_store.add_documents(chunks)
        return existing_vector_store
    else:
        vector_store = FAISS.from_documents(chunks, embeddings)
        return vector_store
        