import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Required flags for Google ADK / A2A
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))

# Shared configuration
DB_PATH = os.getenv("DB_PATH", "support.db")

MCP_HOST = "127.0.0.1"
MCP_PORT = 8000
MCP_PATH = "/mcp"
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}"

# A2A agent ports
CUSTOMER_DATA_PORT = 11020
SUPPORT_PORT = 11021
ROUTER_PORT = 11022
