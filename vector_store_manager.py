# vector_store_manager.py
import os
from data_ingestion.earning_retriever import ingest_multiple_pdfs

EARNINGS_DIR = "earning_calls"

# Initialize the global instance here
pdf_paths = [
    os.path.join(EARNINGS_DIR, file)
    for file in os.listdir(EARNINGS_DIR)
    if file.lower().endswith(".pdf")
]

# This runs once when the app starts
vector_store = ingest_multiple_pdfs(
    filePath=pdf_paths,
    company="Tata Motors",
    ticker="TATAMOTORS",
)