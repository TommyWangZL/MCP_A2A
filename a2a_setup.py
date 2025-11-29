"""One-time A2A compatibility patch for google-adk 1.9.0 + a2a-sdk 0.3.0.

This mirrors the Colab cell that patched `a2a.client.client` so that
`A2ACardResolver` is available where ADK expects it.
"""

import sys
from a2a.client import client as real_client_module
from a2a.client.card_resolver import A2ACardResolver


class PatchedClientModule:
    def __init__(self, real_module) -> None:
        for attr in dir(real_module):
            if not attr.startswith("_"):
                setattr(self, attr, getattr(real_module, attr))
        # Inject A2ACardResolver
        self.A2ACardResolver = A2ACardResolver


# Apply patch at import time
patched_module = PatchedClientModule(real_client_module)
sys.modules["a2a.client.client"] = patched_module  # type: ignore
