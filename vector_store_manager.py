# vector_store_manager.py
import os
from data_ingestion.earning_retriever import ingest_multiple_pdfs

EARNINGS_DIR = "earning_calls"

all_vectorstores = []

for company_name in os.listdir(EARNINGS_DIR):
    company_path = os.path.join(EARNINGS_DIR, company_name)

    if not os.path.isdir(company_path):
        continue

    pdf_paths = [
        os.path.join(company_path, file)
        for file in os.listdir(company_path)
        if file.lower().endswith(".pdf")
    ]

    if not pdf_paths:
        continue

    # 🔹 Extract ticker from first PDF filename
    # Example: TATACONSUM.NS_Q1_2026.pdf → TATACONSUM.NS
    first_file = os.path.basename(pdf_paths[0])
    ticker = first_file.split("_")[0]

    print(f"Ingesting earnings for {company_name} ({ticker})")

    vector_store = ingest_multiple_pdfs(
        filePath=pdf_paths,
        company=company_name,
        ticker=ticker
    )

    all_vectorstores.append(vector_store)

# 🔹 Merge all company vector stores into one
if all_vectorstores:
    final_vector_store = all_vectorstores[0]
    for vs in all_vectorstores[1:]:
        final_vector_store.merge_from(vs)
else:
    final_vector_store = None
