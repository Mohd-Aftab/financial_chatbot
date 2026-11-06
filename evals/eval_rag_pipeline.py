"""Run the retriever and generator together and score the RAG triad.

For each question the retriever returns chunks, the generator answers from
those chunks, and the three triad metrics score that pair:

- contextual relevancy: are the retrieved chunks about the question
- faithfulness: does the answer stay inside those chunks
- answer relevancy: does the answer address the question

The hand-written generator context is not used. Context comes from retrieval.

    python -m evals.eval_rag_pipeline
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from evals.eval_generator import generate
from evals.eval_retriever import DATASET_PATH, load_cases, retrieve
from evals.report import print_eval_report

JUDGE_MODEL = "gpt-4o-mini"
THRESHOLD = 0.5

TRIAD = (
    "ContextualRelevancyMetric",
    "FaithfulnessMetric",
    "AnswerRelevancyMetric",
)


def build_metrics() -> list[tuple[str, object]]:
    shared = {
        "threshold": THRESHOLD,
        "model": JUDGE_MODEL,
        "async_mode": False,
        "include_reason": True,
    }
    return [
        ("ContextualRelevancyMetric", ContextualRelevancyMetric(**shared)),
        ("FaithfulnessMetric", FaithfulnessMetric(**shared)),
        ("AnswerRelevancyMetric", AnswerRelevancyMetric(**shared)),
    ]


def _metric_row(name, score, passed, reason):
    return {"name": name, "score": score, "passed": passed, "reason": reason}


def evaluate_case(case: dict) -> dict:
    print(f"\n=== {case['id']} ===")
    documents = retrieve(case["input"], case.get("category", "all"))
    contexts = [doc.page_content for doc in documents]
    print(f"Retrieved {len(contexts)} chunks")

    if not contexts:
        print("No chunks retrieved. Triad scores are 0.")
        return {
            "id": case["id"],
            "metrics": [
                _metric_row(name, 0.0, False, "No chunks retrieved.")
                for name in TRIAD
            ],
        }

    answer = generate(case["input"], contexts)
    print(answer)

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=answer,
        retrieval_context=contexts,
    )

    metrics = []
    for name, metric in build_metrics():
        score = metric.measure(test_case, _log_metric_to_confident=False)
        row = _metric_row(name, score, metric.is_successful(), getattr(metric, "reason", None))
        metrics.append(row)
        print(f"{name}: {score:.3f} (pass={row['passed']})")
        if row["reason"]:
            print(f"  reason: {row['reason']}")
    return {"id": case["id"], "metrics": metrics}


def main() -> None:
    cases = load_cases(DATASET_PATH)
    results = [evaluate_case(case) for case in cases]
    passed = print_eval_report("RAG triad evaluation", results)
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
