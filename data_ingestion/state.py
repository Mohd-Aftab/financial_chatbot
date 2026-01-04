# state.py
import os

INGESTED_NEWS_URLS = set()
INGESTED_COMPANIES = set()

# Persistence file path
NEWS_HISTORY_FILE = "ingested_news.txt"

# 1. Load history on startup
if os.path.exists(NEWS_HISTORY_FILE):
    with open(NEWS_HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            INGESTED_NEWS_URLS.add(line.strip())

print(f"Loaded {len(INGESTED_NEWS_URLS)} previously ingested news URLs.")