from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from dotenv import load_dotenv
load_dotenv()

print("Loading PDF document...", FAISS)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

def ingest_multiple_pdfs(filePath, company, ticker):
    all_docs = []
    
    for file in filePath:
        loader = PyPDFLoader(file)
        docs = loader.load()
        
        for doc in docs:
            doc.metadata.update({
                "company": company,
                "ticker": ticker,
                "data_type": "earnings_call",
                "source": "investor_relations",
                "filename": file
            })
        all_docs.extend(docs)
        
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    
    chunks = splitter.split_documents(all_docs)
    
    vector_store = FAISS.from_documents(chunks, embeddings)
    
    return vector_store