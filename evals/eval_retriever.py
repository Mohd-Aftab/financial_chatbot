"""Score the earnings retriever against golden_datasets/retrieved_context.json.

Uses the same company resolution, metadata filter, and top-5 similarity search
as rag_tool. Scores each case with DeepEval contextual recall, contextual
precision, and contextual relevancy.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase

from evals.report import print_eval_report
from tools.rag_tool import build_metadata_filter, extract_company_from_query
from vector_store_manager import final_vector_store

DATASET_PATH = ROOT / "golden_datasets" / "retrieved_context.json"
JUDGE_MODEL = "gpt-4o-mini"
TOP_K = 5
THRESHOLD = 0.5


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data["cases"]
    return data


def target_data_types(category: str) -> list[str]:
    if category == "news":
        return ["news"]
    if category in ("earnings", "earnings_call"):
        return ["earnings_call"]
    return ["earnings_call", "news"]


def retrieve(query: str, category: str) -> list:
    company_name, ticker = extract_company_from_query(query)
    print(f"Resolved company: {company_name}, ticker: {ticker}")

    filter_fn = build_metadata_filter(
        company_name=company_name,
        ticker=ticker,
        data_types=target_data_types(category),
        thread_id="retriever-eval",
    )
    retriever = final_vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K, "filter": filter_fn},
    )
    try:
        return retriever.invoke(query)
    except Exception as exc:
        print(f"Retrieval error: {exc}")
        return []


def build_metrics() -> list:
    shared = {
        "threshold": THRESHOLD,
        "model": JUDGE_MODEL,
        "async_mode": False,
        "include_reason": True,
    }
    return [
        ContextualRecallMetric(**shared),
        ContextualPrecisionMetric(**shared),
        ContextualRelevancyMetric(**shared),
    ]


def gold_chunk_retrieved(case: dict, documents: list) -> bool:
    gold_context = case.get("gold_context")
    if not gold_context:
        return False
    return any(doc.page_content == gold_context for doc in documents)


def _metric_row(name, score, passed, reason):
    return {"name": name, "score": score, "passed": passed, "reason": reason}


def evaluate_case(case: dict) -> dict:
    print(f"\n=== {case['id']} ===")
    documents = retrieve(case["input"], case.get("category", "all"))
    contexts = [doc.page_content for doc in documents]
    print(f"Retrieved {len(contexts)} chunks")
    print(f"Gold chunk in top {TOP_K}: {gold_chunk_retrieved(case, documents)}")

    if not contexts:
        print("No chunks retrieved. Recall, precision, and relevancy score 0.")
        metrics = [
            _metric_row(name, 0.0, False, "No chunks retrieved.")
            for name in (
                "ContextualRecallMetric",
                "ContextualPrecisionMetric",
                "ContextualRelevancyMetric",
            )
        ]
        return {"id": case["id"], "metrics": metrics}

    test_case = LLMTestCase(
        input=case["input"],
        expected_output=case["expected_output"],
        retrieval_context=contexts,
    )

    metrics = []
    for metric in build_metrics():
        score = metric.measure(test_case, _log_metric_to_confident=False)
        row = _metric_row(
            metric.__class__.__name__,
            score,
            metric.is_successful(),
            metric.reason,
        )
        metrics.append(row)
        print(f"{row['name']}: {score:.3f} (pass={row['passed']})")
        if row["reason"]:
            print(f"  reason: {row['reason']}")
    return {"id": case["id"], "metrics": metrics}


def main() -> None:
    cases = load_cases(DATASET_PATH)
    results = [evaluate_case(case) for case in cases]
    passed = print_eval_report("Retriever evaluation", results)
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
