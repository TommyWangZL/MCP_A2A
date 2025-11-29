"""Start A2A servers for Customer Data, Support, and Router agents."""

import asyncio
import threading
import time

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from config import CUSTOMER_DATA_PORT, SUPPORT_PORT, ROUTER_PORT
from agents import (
    customer_data_agent,
    support_agent,
    router_agent,
    customer_data_agent_card,
    support_agent_card,
    router_agent_card,
)


def create_agent_a2a_server(agent, agent_card):
    runner = Runner(
        app_name=agent.name,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
    )

    executor = A2aAgentExecutor(
        runner=runner,
        config=A2aAgentExecutorConfig(),
    )

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)


async def run_agent_server(agent, agent_card, port: int) -> None:
    app = create_agent_a2a_server(agent, agent_card)
    config = uvicorn.Config(
        app.build(),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="none",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def start_all_agent_servers() -> None:
    tasks = [
        asyncio.create_task(
            run_agent_server(customer_data_agent, customer_data_agent_card, CUSTOMER_DATA_PORT)
        ),
        asyncio.create_task(
            run_agent_server(support_agent, support_agent_card, SUPPORT_PORT)
        ),
        asyncio.create_task(
            run_agent_server(router_agent, router_agent_card, ROUTER_PORT)
        ),
    ]

    await asyncio.sleep(2)
    print("✅ All A2A agent servers started!")
    print(f"   - Customer Data Agent: http://127.0.0.1:{CUSTOMER_DATA_PORT}")
    print(f"   - Support Agent:       http://127.0.0.1:{SUPPORT_PORT}")
    print(f"   - Router Agent:        http://127.0.0.1:{ROUTER_PORT}")

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("Shutting down A2A servers...")


def _agents_main_loop() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_all_agent_servers())


def start_agents_in_background() -> threading.Thread:
    """Start all A2A agent servers in a background thread and return the thread."""
    thread = threading.Thread(target=_agents_main_loop, daemon=True)
    thread.start()
    time.sleep(2)
    print("A2A agent servers should now be running.")
    return thread
