from turtle import st
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric

from financial_bot_backend import chatbot

from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

def run_deepeval(question):
    CONFIG = {'configurable': {'thread_id': "thread_id-1"}}
    
    # 1. Get the state dictionary from the chatbot
    result = chatbot.invoke({"messages": [(HumanMessage(content=question))]}, config=CONFIG)
    messages = result.get("messages", [])

    # 2. Extract the actual_output (The last AIMessage content)
    # We iterate backwards to find the last AI response
    actual_output = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            actual_output = msg.content
            break

    # 3. Extract the retrieval_context (The content of the ToolMessage)
    retrieval_context = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            import json
            try:
                # Assuming your tool returns a JSON string with a 'context' key
                data = json.loads(msg.content)
                if isinstance(data.get("context"), list):
                    retrieval_context = data["context"]
            except:
                # Fallback if it's not JSON
                retrieval_context = [msg.content]

    # 4. Create the test case with extracted data
    test_case = LLMTestCase(
        input=question,
        actual_output=actual_output,
        retrieval_context=retrieval_context
    )

    # 5. Measure
    metric = FaithfulnessMetric()
    metric.measure(test_case)
    print(f"Score: {metric.score}")
    print(f"Reason: {metric.reason}")
