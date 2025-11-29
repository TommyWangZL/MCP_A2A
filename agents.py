"""Definition of Customer Data Agent, Support Agent, and Router Agent."""

from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, TransportProtocol
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

from a2a_setup import patched_module as _patched  # ensures A2A patch is applied
from config import CUSTOMER_DATA_PORT, SUPPORT_PORT, ROUTER_PORT


# 1) Customer Data Agent
customer_data_agent = Agent(
    model="gemini-2.5-pro",  # you can switch to gemini-1.5-flash if needed
    name="customer_data_agent",
    description="Customer Data Agent that accesses customer database via MCP",
    instruction="""
You are the Customer Data Agent.

You conceptually use these MCP tools (implemented outside the LLM):
- get_customer(customer_id)
- list_customers(status, limit)
- update_customer(customer_id, data)
- create_ticket(customer_id, issue, priority)
- get_customer_history(customer_id)

In your responses, you should:
- Assume the Router has already called MCP tools and passed you JSON data.
- Summarize or transform that data cleanly.
- Keep responses concise and structured (JSON-like if appropriate).
""",)

# 2) Support Agent
support_agent = Agent(
    model="gemini-2.5-pro",
    name="support_agent",
    description="Support Agent that handles general customer support queries",
    instruction="""
You are the Support Agent.

You receive:
- customer information
- ticket histories
- the original user query

Your job:
- Provide clear customer support responses:
  * account upgrades
  * cancellations
  * billing issues / refunds
  * escalation, etc.
- Use the context provided.
- Respond as if MCP-based tickets have been created/updated as needed,
  but do not invent extra DB operations beyond what the Router tells you.

Your answer should:
- Explain what action was (or will be) taken.
- Be polite, concise, and actionable.
""",)

# AgentCards
customer_data_agent_card = AgentCard(
    name="Customer Data Agent",
    url=f"http://localhost:{CUSTOMER_DATA_PORT}",
    description="Accesses customer database via MCP tools",
    version="1.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["application/json"],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id="customer_data",
            name="Customer Data Operations",
            description="Summarizes customer and ticket data fetched via MCP.",
            tags=["mcp", "customers", "tickets"],
            examples=[
                "Summarize this customer JSON",
                "Summarize this ticket history",
            ],
        )
    ],
)

support_agent_card = AgentCard(
    name="Support Agent",
    url=f"http://localhost:{SUPPORT_PORT}",
    description="Handles customer support flows using provided context.",
    version="1.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id="support",
            name="Customer Support",
            description="Upgrades, cancellations, refunds, and general support.",
            tags=["support", "billing", "escalation"],
            examples=[
                "Help this customer upgrade based on their history",
                "Handle this refund request with given billing history",
            ],
        )
    ],
)

# Remote references for router (A2A)
remote_customer_data_agent = RemoteA2aAgent(
    name="remote_customer_data_agent",
    description="Remote customer data agent exposed via A2A",
    agent_card=f"http://localhost:{CUSTOMER_DATA_PORT}{AGENT_CARD_WELL_KNOWN_PATH}",
)

remote_support_agent = RemoteA2aAgent(
    name="remote_support_agent",
    description="Remote support agent exposed via A2A",
    agent_card=f"http://localhost:{SUPPORT_PORT}{AGENT_CARD_WELL_KNOWN_PATH}",
)

# 3) Router Agent (Sequential host over the two remote agents)
router_agent = SequentialAgent(
    name="router_agent_host",
    sub_agents=[remote_customer_data_agent, remote_support_agent],
)

router_agent_card = AgentCard(
    name="Router Agent Host",
    url=f"http://localhost:{ROUTER_PORT}",
    description=(
        "Router/Orchestrator for the customer service system. "
        "It coordinates the Customer Data Agent (MCP-backed) and the Support Agent "
        "to handle: simple account queries, coordinated upgrades, escalation, "
        "multi-intent updates, and premium ticket status reporting."
    ),
    version="1.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    preferred_transport=TransportProtocol.jsonrpc,
    skills=[
        AgentSkill(
            id="router",
            name="Customer Service Router",
            description=(
                "Analyzes user queries, delegates sub-tasks to data & support agents "
                "via A2A, and synthesizes final responses. Handles scenarios: "
                "simple query, task allocation, negotiation/escalation, and "
                "multi-step coordination for premium customers."
            ),
            tags=["router", "orchestration", "multi-step"],
            examples=[
                "Get customer information for ID 5",
                "I'm customer 12345 and need help upgrading my account",
                "Show me all active customers who have open tickets",
                "I've been charged twice, please refund immediately!",
                "Update my email to new@email.com and show my ticket history",
                "I need help with my account, customer ID 12345",
                "I want to cancel my subscription but I'm having billing issues",
                "What's the status of all high-priority tickets for premium customers?",
            ],
        )
    ],
)
