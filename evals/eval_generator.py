"""Score the answer generator against golden_datasets/generator_context.json.

The context on each row is supplied by hand. This script does not call the
retriever. It asks the model to answer from that context, then scores
faithfulness, answer relevancy, and completeness.
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

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from evals.report import print_eval_report

DATASET_PATH = ROOT / "golden_datasets" / "generator_context.json"
JUDGE_MODEL = "gpt-4o-mini"
ANSWER_MODEL = "gpt-4o-mini"
THRESHOLD = 0.5

llm = ChatOpenAI(model=ANSWER_MODEL, temperature=0)


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data["cases"]
    return data


def as_context_list(context) -> list[str]:
    if isinstance(context, str):
        return [context]
    return list(context)


def generate(query: str, context: list[str]) -> str:
    joined = "\n\n".join(context)
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Answer the question using only the context below. "
                    "If the context does not contain a fact needed to answer, say so. "
                    "Do not add facts from outside the context.\n\n"
                    f"Context:\n{joined}"
                )
            ),
            HumanMessage(content=query),
        ]
    )
    return response.content


def build_metrics() -> list[tuple[str, object]]:
    shared = {
        "threshold": THRESHOLD,
        "model": JUDGE_MODEL,
        "async_mode": False,
        "include_reason": True,
    }
    completeness = GEval(
        name="Completeness",
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        criteria=(
            "Completeness: the answer covers every part of the question. "
            "The expected output lists the points that should be covered."
        ),
        evaluation_steps=[
            "Split the input into the separate points it asks about.",
            "Check the actual output addresses each of those points.",
            "Use the expected output as the checklist of points that count as addressed.",
            "A point that is missing from the actual output is not addressed.",
        ],
        threshold=THRESHOLD,
        model=JUDGE_MODEL,
        async_mode=False,
    )
    return [
        ("FaithfulnessMetric", FaithfulnessMetric(**shared)),
        ("AnswerRelevancyMetric", AnswerRelevancyMetric(**shared)),
        ("Completeness", completeness),
    ]


def _metric_row(name, score, passed, reason):
    return {"name": name, "score": score, "passed": passed, "reason": reason}


def evaluate_case(case: dict) -> dict:
    print(f"\n=== {case['id']} ===")
    context = as_context_list(case["context"])
    answer = generate(case["input"], context)
    print(answer)

    test_case = LLMTestCase(
        input=case["input"],
        actual_output=answer,
        expected_output=case["expected_output"],
        retrieval_context=context,
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
    passed = print_eval_report("Generator evaluation", results)
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
