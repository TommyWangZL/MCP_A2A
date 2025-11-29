"""Test harness: runs the 8 required scenarios using MCP + A2A."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Dict, Any, Optional, List

from config import ROUTER_PORT
from mcp_client import mcp_call_tool
from a2a_client import A2ASimpleClient


# Helper: extract a customer id from the user query
def extract_customer_id(q: str) -> Optional[int]:
    """Tries patterns like:
      - "ID 5"
      - "customer 12345"
    """
    m = re.search(r"\bID\s+(\d+)\b", q, re.IGNORECASE)
    if not m:
        m = re.search(r"\bcustomer\s+(\d+)\b", q, re.IGNORECASE)
    return int(m.group(1)) if m else None


# Required test scenarios
TEST_QUERIES: List[str] = [
    # 1) Simple Query
    "Get customer information for ID 5",
    # 2) Coordinated Query
    "I'm customer 12345 and need help upgrading my account",
    # 3) Complex Query
    "Show me all active customers who have open tickets",
    # 4) Escalation
    "I've been charged twice, please refund immediately!",
    # 5) Multi-Intent
    "Update my email to new@email.com and show my ticket history",
    # 6) Scenario 1 – Task allocation
    "I need help with my account, customer ID 12345",
    # 7) Scenario 2 – Negotiation / escalation
    "I want to cancel my subscription but I'm having billing issues",
    # 8) Scenario 3 – Multi-step coordination
    "What's the status of all high-priority tickets for premium customers?",
]


async def run_single_test(query_index: int = 0) -> None:
    """Run exactly ONE of the test scenarios.

    Example:
        await run_single_test(0)  # simple query
        await run_single_test(1)  # coordinated query
    """
    if query_index < 0 or query_index >= len(TEST_QUERIES):
        raise ValueError(f"query_index must be between 0 and {len(TEST_QUERIES) - 1}")

    q = TEST_QUERIES[query_index]
    router_url = f"http://localhost:{ROUTER_PORT}"

    print("\n" + "=" * 80)
    print(f"Running scenario #{query_index}:")
    print("Original Query:", q)
    print("-" * 80)

    customer_id = extract_customer_id(q)
    customer_json: Optional[Dict[str, Any]] = None
    history_json: Optional[Dict[str, Any]] = None
    active_customers_json: Optional[Dict[str, Any]] = None

    # 1) Per-customer data via MCP tools/call
    if customer_id is not None:
        try:
            customer_result = await mcp_call_tool("get_customer", {"customer_id": customer_id})
            customer_json = customer_result
        except Exception as e:
            print(f"⚠️ MCP call failed for get_customer: {e}")
            customer_json = {"status": "error", "message": str(e)}

        try:
            history_result = await mcp_call_tool("get_customer_history", {"customer_id": customer_id})
            history_json = history_result
        except Exception as e:
            print(f"⚠️ MCP call failed for get_customer_history: {e}")
            history_json = {"status": "error", "message": str(e)}

        print(f"Fetched MCP customer data for id={customer_id} via tools/call:")
        print(json.dumps(customer_json, indent=2))
        print(f"\nFetched MCP ticket history for id={customer_id}:")
        print(json.dumps(history_json, indent=2))
    else:
        print("No specific customer ID found in query.")

    # 2) Complex / aggregate cases: list active customers via MCP
    if "active customers" in q.lower():
        try:
            active_result = await mcp_call_tool("list_customers", {"status": "active", "limit": 20})
            active_customers_json = active_result
        except Exception as e:
            print(f"⚠️ MCP call failed for list_customers: {e}")
            active_customers_json = {"status": "error", "message": str(e)}

        print("\nFetched MCP list of active customers via tools/call:")
        print(json.dumps(active_customers_json, indent=2))

    # Build the message for the Router Agent with ONLY MCP-backed JSON
    context_sections: List[str] = []

    if customer_json is not None:
        context_sections.append(
            "MCP get_customer result:\n```json\n"
            + json.dumps(customer_json, indent=2)
            + "\n```"
        )

    if history_json is not None:
        context_sections.append(
            "MCP get_customer_history result:\n```json\n"
            + json.dumps(history_json, indent=2)
            + "\n```"
        )

    if active_customers_json is not None:
        context_sections.append(
            "MCP list_customers(status='active') result:\n```json\n"
            + json.dumps(active_customers_json, indent=2)
            + "\n```"
        )

    if context_sections:
        mcp_block = "\n\n".join(context_sections)
        router_message = (
            "You are the Router/Orchestrator Agent in the customer service system.\n\n"
            f"User query:\n{q}\n\n"
            "Below is the REAL MCP database data, fetched over the MCP HTTP "
            "'tools/call' protocol (do not invent extra fields):\n\n"
            f"{mcp_block}\n\n"
            "Your job:\n"
            "- Use ONLY the data above for customer and ticket information.\n"
            "- If aggregate info (like 'all active customers who have open tickets' or "
            " 'high-priority tickets for premium customers') is requested but not directly "
            "computable from the provided JSON, explain the limitation and describe which "
            "MCP queries would be needed.\n"
            "- Produce a final customer-support style answer.\n"
            "- At the end, include a short bullet list of steps taken.\n"
        )
    else:
        router_message = (
            "You are the Router/Orchestrator Agent in the customer service system.\n\n"
            f"User query:\n{q}\n\n"
            "There is currently NO MCP JSON data available for this query.\n"
            "Your job:\n"
            "- Explain what information is missing (e.g., customer_id, account email).\n"
            "- Describe which MCP tools should be called next "
            "(get_customer, get_customer_history, list_customers, create_ticket, update_customer).\n"
            "- Produce a polite, customer-support style answer that explains what the agent "
            "would do once the missing info is provided.\n"
            "- Finish with a short bullet list of steps that *would* be taken.\n"
        )

    # Call Router Agent via A2A
    client = A2ASimpleClient()
    resp = await client.create_task(router_url, router_message)

    print("\nRouter response:\n")
    print(resp)

    time.sleep(2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run A2A + MCP customer service scenarios.")
    parser.add_argument(
        "--scenario",
        type=int,
        default=0,
        help="Scenario index to run (0-7).",
    )
    args = parser.parse_args()

    asyncio.run(run_single_test(args.scenario))


if __name__ == "__main__":
    main()
