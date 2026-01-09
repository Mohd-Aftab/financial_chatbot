# vector_store_manager.py
import os
from data_ingestion.earning_retriever import ingest_multiple_pdfs

EARNINGS_DIR = "earning_calls"

# Collect all paths (this is still simple/hardcoded for your current setup)
pdf_paths = [
    os.path.join(EARNINGS_DIR, file)
    for file in os.listdir(EARNINGS_DIR)
    if file.lower().endswith(".pdf")
]

# NOTE: In a real app, you would ingest these differently, likely by folder.
# For now, we ensure the existing Tata PDFs get the "Tata Motors" tag.
vector_store = ingest_multiple_pdfs(
    filePath=pdf_paths,
    company="Tata consumers products", # <--- This metadata is what the RAG tool filters on
    ticker="TMPV.NS",
)