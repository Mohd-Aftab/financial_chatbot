import uuid
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric
)
from financial_bot_backend import chatbot
from langchain_core.messages import HumanMessage, ToolMessage

current_dir = os.path.dirname(os.path.abspath(__file__))

json_path = os.path.join(current_dir, "test_case.json")

with open(json_path, "r") as f:
    test_data = json.load(f)

def get_chatbot_response(question: str):
    # Use a fresh thread ID for every test to ensure isolation
    thread_id = str(uuid.uuid4()) 
    CONFIG = {"configurable": {"thread_id": thread_id}}

    state = {"messages": [HumanMessage(content=question)]}
    result_state = chatbot.invoke(state, config=CONFIG)
    
    # Get the final answer
    answer = result_state["messages"][-1].content
    
    # Extract Context
    # We look for the MOST RECENT ToolMessage from 'rag_tool' or 'ingest_company_news'
    retrieved_context = []
    
    # Iterate through all messages to capture ANY tool output
    for message in result_state["messages"]:
        if isinstance(message, ToolMessage):
            # 1. Handle RAG Tool (JSON or Text)
            if message.name == "rag_tool":
                try:
                    parsed = json.loads(message.content)
                    if isinstance(parsed, dict) and "retrieved_context" in parsed:
                        retrieved_context.extend(parsed["retrieved_context"])
                    else:
                        retrieved_context.append(message.content)
                except:
                    retrieved_context.append(message.content)
            
            # 2. Handle News Ingestion
            elif message.name == "ingest_company_news":
                pass
                # retrieved_context.append(f"Ingested News Content: {message.content}")

            # 3. Handle Live Stock Price (CRITICAL FIX FOR TESLA CASE)
            elif message.name == "get_stock_price":
                 retrieved_context.append(f"Live Stock Data: {message.content}")
                 
    return answer, retrieved_context

# Prepare DeepEval Test Cases
test_cases = []

for entry in test_data:
    input_text = entry["input"]
    actual_output, retrieved_context = get_chatbot_response(input_text)
    
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        retrieval_context=retrieved_context
    )
    test_cases.append(test_case)

# Define Metrics
faithfulness = FaithfulnessMetric(threshold=0.7, model="gpt-4o", include_reason=True)
answer_relevancy = AnswerRelevancyMetric(threshold=0.7, model="gpt-4o", include_reason=True)
context_relevancy = ContextualRelevancyMetric(threshold=0.7, model="gpt-4o", include_reason=True)

# Run Evaluation
print("Running Evaluation...")
evaluate(
    test_cases=test_cases,
    metrics=[faithfulness, answer_relevancy, context_relevancy]
)