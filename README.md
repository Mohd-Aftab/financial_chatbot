# Financial Market Assistant

A LangGraph-powered financial chatbot that answers questions about stocks, company news, and earnings. It resolves company names to tickers, fetches live prices, ingests recent news into a FAISS vector store, and retrieves grounded context before answering.

The primary interface is a Streamlit chat UI with multi-thread conversation history.

---

## Features

- **Live stock prices** via Yahoo Finance (company name or ticker, including Indian `.NS` / `.BO` listings)
- **Price comparison** across multiple companies over a chosen period
- **Company disambiguation** when a name is ambiguous (e.g. “Tata”, “Apple”)
- **On-demand news ingestion** from NewsAPI into the vector store (duplicate URLs skipped)
- **RAG over earnings transcripts and news**, filtered by company, ticker, and data type
- **Web search** (DuckDuckGo) for market-wide questions, rankings, and current events
- **Conversation memory** persisted in SQLite (`financebot.db`) with Streamlit thread switching
- **DeepEval tests** for faithfulness, answer relevancy, and contextual relevancy

---

## Architecture

```
User (Streamlit)
        │
        ▼
financial_bot_backend.py   LangGraph: chat_node ⇄ tools
        │
        ├── get_stock_price / compare_stock_prices   (yfinance + yahooquery)
        ├── clarify_company                          (LLM company resolver)
        ├── ingest_company_news                      (NewsAPI → FAISS)
        ├── rag_tool / check_data_availability       (FAISS retrieval)
        └── DuckDuckGoSearchRun                      (general market search)
```

1. The LLM plans tool calls (never answers from training data for prices, earnings, or company news).
2. Tools fetch or ingest data. News and earnings live in a local FAISS index with metadata (`company`, `ticker`, `data_type`).
3. `rag_tool` retrieves company-scoped chunks; the model then writes a formatted answer.
4. LangGraph checkpoints each thread in SQLite so chats can be resumed.

Embeddings: `text-embedding-3-small`. Chat model: `gpt-4o-mini`.

---

## Project structure

```
financial_chatbot/
├── streamlit_frontend.py      # Streamlit UI (main entry point)
├── financial_bot_backend.py   # LangGraph agent, tools, SQLite checkpointer
├── chatbot.py                 # Simple CLI loop (experimental)
├── vector_store_manager.py    # Loads the local FAISS index
├── ingest_earnings.py         # One-time PDF → FAISS ingestion
├── requirements.txt
├── .env                       # API keys (not committed)
│
├── tools/
│   ├── stock_price_tool.py    # Prices + multi-stock comparison
│   ├── news_ingestion_tool.py # NewsAPI ingest wrapper
│   └── rag_tool.py            # Company-aware retrieval + data checks
│
├── data_ingestion/
│   ├── auto_news_pipeline.py  # Resolve company → fetch → embed news
│   ├── fetch_articles.py      # NewsAPI client
│   ├── earning_retriever.py   # PDF load, chunk, FAISS
│   ├── news_ingestor.py       # Alternate news ingest helper
│   └── state.py               # Duplicate-URL tracking (ingested_news.txt)
│
├── utils/
│   ├── company_resolver.py    # LLM + yfinance ticker resolution
│   ├── parsed_date_format.py  # Relative/absolute date parsing
│   └── prompt2.py             # System prompt used by Streamlit
│
├── evaluation/
│   ├── deepeval_test.py       # RAG / answer quality eval
│   └── test_case.json
│
├── output_schemas/            # Pydantic helpers for ticker / company identity
├── earning_calls/             # Input PDFs (create this; not in git)
└── faiss_index/               # Generated vector store (gitignored)
```

---

## Prerequisites

- Python 3.11+ recommended
- [OpenAI API](https://platform.openai.com/) key
- [NewsAPI](https://newsapi.org/) key (for company news ingestion)
- Earnings PDFs if you want transcript RAG (optional for prices/search)

---

## Setup

```bash
git clone <repo-url>
cd financial_chatbot

python -m venv myenv
# Windows
myenv\Scripts\activate
# macOS / Linux
source myenv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
NEWS_API_KEY=...

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=finance-assistant
```

Never commit `.env`. It is listed in `.gitignore`.

---

## Earnings data (optional but needed for transcript RAG)

`vector_store_manager.py` loads `faiss_index/` at startup. That folder is generated, not shipped.

1. Create `earning_calls/` with one folder per company.
2. Put PDF transcripts inside. The first filename’s prefix before `_` is treated as the ticker.

Example:

```
earning_calls/
  Tata Consultancy Services Limited/
    TCS.NS_Q3FY24.pdf
  Tata Consumer Products Limited/
    TATACONSUM.NS_Q3FY24.pdf
```

3. Build the index:

```bash
python ingest_earnings.py
```

This writes `faiss_index/`. News ingested later is added to the same store.

If you only care about prices, search, and live news, you still need a FAISS index on disk (the backend loads it on import). Run `ingest_earnings.py` with at least one PDF, or create an empty index yourself before starting the app.

---

## Run the app

**Streamlit (recommended):**

```bash
streamlit run streamlit_frontend.py
```

Use **New Chat** in the sidebar for a fresh thread. Previous threads are restored from `financebot.db`.

**CLI (experimental):**

```bash
python chatbot.py
```

Type `exit` or `quit` to stop. The CLI currently imports a `vector_store` symbol that the backend does not export; prefer Streamlit for a working UI.

---

## How to use it

Examples of questions the agent is designed for:

| Intent | Example |
| --- | --- |
| Price | “What’s Tesla’s stock price?” |
| History | “TCS performance over the last year” |
| Compare | “Compare Tata Steel and Tata Motors over 3 months” |
| Disambiguate | “Stock price of Tata” → asks which Tata company |
| Company news | “Latest news on Microsoft” (ingests, then summarizes via RAG) |
| Earnings | “What did Tata Consumer say about margins?” (needs ingested PDFs) |
| Market | “How is the market today?” / “top performing stocks this year” (web search) |

The system prompt instructs the model to:

- Clarify ambiguous company names before calling other tools
- Check `check_data_availability` before claiming earnings facts
- Ingest news, then call `rag_tool` (never dump raw JSON to the user)
- Use DuckDuckGo for lists, rankings, and general market questions — not for a single ticker’s price

---

## Evaluation

```bash
python evaluation/deepeval_test.py
```

This runs the questions in `evaluation/test_case.json` through the live agent and scores them with DeepEval (`gpt-4o`): Faithfulness, Answer Relevancy, Contextual Relevancy (threshold 0.7). Each case uses a fresh LangGraph thread ID.

---

## Generated / ignored files

These are created at runtime and are gitignored:

| Path | Purpose |
| --- | --- |
| `.env` | Secrets |
| `faiss_index/` | Vector store |
| `financebot.db` | Conversation checkpoints |
| `ingested_news.txt` | URLs already ingested (dedup) |
| `myenv/` | Local virtualenv |

---

## Tech stack

| Area | Library |
| --- | --- |
| Agent graph | LangGraph + LangChain |
| LLM / embeddings | OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) |
| Vector store | FAISS |
| Prices | yfinance, yahooquery |
| News | NewsAPI |
| Search | DuckDuckGo |
| UI | Streamlit |
| Memory | SQLite (`SqliteSaver`) |
| Eval | DeepEval |

---

## Notes

- This is a research / demo assistant, not investment advice.
- NewsAPI free tiers are rate-limited; ingestion may return `no_news` when the quota is exhausted.
- Company resolution and ticker verification call the LLM and Yahoo Finance on every lookup, so the first answer can take several seconds.
- `output_schemas/` and older prompt files (`utils/prompts.py`, `utils/prompt3.py`) are supporting or earlier versions; Streamlit uses `utils/prompt2.py`.
