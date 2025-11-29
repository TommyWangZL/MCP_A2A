"""Simple A2A JSON-RPC client used by the test harness."""

from typing import Dict, Any, Optional, List

import httpx
from a2a.types import AgentCard, TransportProtocol
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from a2a.client import ClientConfig, ClientFactory, create_text_message_object

from a2a_setup import patched_module as _patched  # ensure patch is applied


class A2ASimpleClient:
    def __init__(self, default_timeout: float = 240.0):
        self._agent_info_cache: Dict[str, Optional[Dict[str, Any]]] = {}
        self.default_timeout = default_timeout

    async def create_task(self, agent_url: str, message: str) -> str:
        timeout_config = httpx.Timeout(
            timeout=self.default_timeout,
            connect=10.0,
            read=self.default_timeout,
            write=10.0,
            pool=5.0,
        )

        async with httpx.AsyncClient(timeout=timeout_config) as httpx_client:
            # Cache AgentCard
            if agent_url in self._agent_info_cache and self._agent_info_cache[agent_url] is not None:
                agent_card_data = self._agent_info_cache[agent_url]
            else:
                agent_card_response = await httpx_client.get(f"{agent_url}{AGENT_CARD_WELL_KNOWN_PATH}")
                agent_card_data = agent_card_response.json()
                self._agent_info_cache[agent_url] = agent_card_data

            agent_card = AgentCard(**agent_card_data)

            config = ClientConfig(
                httpx_client=httpx_client,
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                use_client_preference=True,
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)

            message_obj = create_text_message_object(content=message)

            responses: List[Any] = []
            async for response in client.send_message(message_obj):
                responses.append(response)

            if responses and isinstance(responses[0], tuple):
                task = responses[0][0]
                try:
                    return task.artifacts[0].parts[0].root.text
                except Exception:
                    return str(task)

            return "No response received"
