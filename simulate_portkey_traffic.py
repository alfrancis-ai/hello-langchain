"""Simulate PG&E-style Portkey traffic with invented app metadata.

Assumes your LangGraph script is agent.py in the same folder (rename the import if not).
Run:  python simulate_traffic.py 30
"""

import random
import sys
import time
import uuid

from agent import graph  # your working LangGraph script

# Invented personas. Keys mirror the IBM SOW drill-downs:
# application, department, project, user, order (internal order / cost object).
# Portkey metadata values must be strings. "_user" is a reserved key that
# Portkey surfaces as the user in analytics.
PERSONAS = [
    {
        "app_id": "APP-1042", "app_name": "outage-comms-assistant",
        "department": "Electric Operations", "project": "Storm Readiness",
        "internal_order": "IO-7781203", "environment": "prod",
        "_user": "svc-outage-comms",
    },
    {
        "app_id": "APP-2210", "app_name": "vegetation-mgmt-summarizer",
        "department": "Wildfire Mitigation", "project": "EVM Inspections",
        "internal_order": "IO-7781455", "environment": "dev",
        "_user": "jdoe",
    },
    {
        "app_id": "APP-3307", "app_name": "finops-chargeback-bot",
        "department": "IT FinOps", "project": "AI Tokenomics",
        "internal_order": "IO-7790012", "environment": "dev",
        "_user": "alfred",
    },
    # Untagged traffic: someone hitting the gateway directly with a coding agent.
    # This is the "unallocated" bucket the chargeback report has to deal with.
    None,
]

PROMPTS = [
    "Summarize the benefits of undergrounding power lines in two sentences.",
    "Draft a one-line customer notice about a planned outage.",
    "List three risks of tree contact with distribution lines.",
    "Explain token-based chargeback in one short paragraph.",
    "Say hello in one short sentence.",
]


def main(n: int) -> None:
    for i in range(n):
        persona = random.choice(PERSONAS)
        trace_id = f"sim-{uuid.uuid4()}"
        config = {"configurable": {"portkey_metadata": persona, "trace_id": trace_id}}
        prompt = random.choice(PROMPTS)

        result = graph.invoke({"messages": [{"role": "user", "content": prompt}]}, config=config)
        label = persona["app_name"] if persona else "(untagged)"
        print(f"[{i + 1}/{n}] {label:<28} {trace_id}  ->  {result['messages'][-1].content[:60]!r}")
        time.sleep(0.5)  # be gentle on rate limits


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)