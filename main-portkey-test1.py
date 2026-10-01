"""A minimal LangGraph example using Portkey with application and user metadata.

Reference: https://docs.langchain.com/oss/python/langgraph/overview
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, convert_to_openai_messages
from langgraph.graph import END, START, MessagesState, StateGraph
from portkey_ai import Portkey


load_dotenv(Path(__file__).with_name(".env"))


def require_settings(*names):
    """Check that the required Portkey settings are configured."""
    missing = [
        name for name in names
        if not os.getenv(name, "").strip() or os.getenv(name, "").startswith("your-")
    ]
    if missing:
        raise SystemExit("Set these values in .env: " + ", ".join(missing))


def call_model(state: MessagesState):
    """Call Portkey and append its reply to the conversation."""
    require_settings("PORTKEY_API_KEY", "PORTKEY_MODEL")
    with Portkey(
        api_key=os.environ["PORTKEY_API_KEY"],
        metadata={"app_name": "journo", "app_id": "1001", "_user": "jdoe"},
        max_retries=0,
    ) as client:
        response = client.chat.completions.create(
            model=os.environ["PORTKEY_MODEL"],
            messages=convert_to_openai_messages(state["messages"]),
            max_completion_tokens=512,
        )
    return {"messages": [AIMessage(content=response.choices[0].message.content or "")]}


# State holds the conversation; nodes return updates to that state.
builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model)

# Edges define the flow: START -> call_model -> END.
builder.add_edge(START, "call_model")
builder.add_edge("call_model", END)
graph = builder.compile()


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Say hello in one short sentence."
    result = graph.invoke({"messages": [{"role": "user", "content": prompt}]})
    for message in result["messages"]:
        print(f"{message.type}: {message.content}")
