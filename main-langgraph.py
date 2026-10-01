"""A minimal LangGraph example with Portkey, Azure, or AWS selected in .env.

Reference: https://docs.langchain.com/oss/python/langgraph/overview
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, convert_to_openai_messages
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph


load_dotenv(Path(__file__).with_name(".env"))


def require_settings(*names):
    """Only require settings for the selected provider."""
    missing = [
        name for name in names
        if not os.getenv(name, "").strip() or os.getenv(name, "").startswith("your-")
    ]
    if missing:
        raise SystemExit("Set these values in .env: " + ", ".join(missing))


def call_model(state: MessagesState):
    """Call the selected provider and append its reply to the conversation."""
    provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()

    if provider == "portkey":
        from portkey_ai import Portkey

        require_settings("PORTKEY_API_KEY", "PORTKEY_MODEL")
        with Portkey(api_key=os.environ["PORTKEY_API_KEY"], max_retries=0) as client:
            response = client.chat.completions.create(
                model=os.environ["PORTKEY_MODEL"],
                messages=convert_to_openai_messages(state["messages"]),
                max_completion_tokens=512,
            )
        return {"messages": [AIMessage(content=response.choices[0].message.content or "")]}

    if provider == "azure":
        require_settings(
            "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_API_KEY",
        )
        model = AzureChatOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            timeout=60,
            max_retries=0,
        )
    elif provider == "aws":
        from botocore.config import Config
        from langchain_aws import ChatBedrockConverse

        require_settings("AWS_REGION", "BEDROCK_MODEL_ID", "AWS_BEARER_TOKEN_BEDROCK")
        model = ChatBedrockConverse(
            model_id=os.environ["BEDROCK_MODEL_ID"],
            region_name=os.environ["AWS_REGION"],
            api_key=os.environ["AWS_BEARER_TOKEN_BEDROCK"],
            max_tokens=512,
            config=Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 0}),
        )
    else:
        raise SystemExit("LLM_PROVIDER must be portkey, azure, or aws.")

    return {"messages": [model.invoke(state["messages"])]}


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
