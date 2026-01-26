import os

from data_ingestion.earning_retriever import ingest_multiple_pdfs
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

EARNINGS_DIR = "earning_calls"


all_vectorstores = []

for company_name in os.listdir(EARNINGS_DIR):
    company_path = os.path.join(EARNINGS_DIR, company_name)
    if not os.path.isdir(company_path):
        continue

    pdf_paths = [
        os.path.join(company_path, f)
        for f in os.listdir(company_path)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_paths:
        continue

    first_file = os.path.basename(pdf_paths[0])
    ticker = first_file.split("_")[0]
    
    print(f"Ingesting earnings for {company_name} ({ticker})")
    

    vs = ingest_multiple_pdfs(
        filePath=pdf_paths,
        company=company_name,
        ticker=ticker
    )
    all_vectorstores.append(vs)

# Merge
final_vs = all_vectorstores[0]
for vs in all_vectorstores[1:]:
    final_vs.merge_from(vs)

# Save to disk
final_vs.save_local("faiss_index")

print("✅ Earnings ingestion completed and saved")
