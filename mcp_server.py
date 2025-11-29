"""MCP server definition using FastMCP and SQLite-backed tools."""

from typing import Any, Dict, Optional
import sqlite3
from datetime import datetime
import threading
import time

from mcp.server.fastmcp import FastMCP

from config import DB_PATH, MCP_URL


mcp = FastMCP(
    name="CustomerSupportMCP",
    instructions="""
Customer support database MCP server.

Tools:
- get_customer(customer_id)
- list_customers(status, limit)
- update_customer(customer_id, data)
- create_ticket(customer_id, issue, priority)
- get_customer_history(customer_id)

Use these tools to read and update customer & ticket data.
""",
)


def get_conn():
    return sqlite3.connect(DB_PATH)


@mcp.tool()
def get_customer(customer_id: int) -> Dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, name, email, phone, status, created_at, updated_at
        FROM customers WHERE id = ?
        """,
        (customer_id,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return {"status": "error", "message": f"No customer with id={customer_id}"}
    keys = ["id", "name", "email", "phone", "status", "created_at", "updated_at"]
    return {"status": "success", "customer": dict(zip(keys, row))}


@mcp.tool()
def list_customers(status: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()
    if status:
        c.execute(
            """
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers WHERE status = ? LIMIT ?
            """,
            (status, limit),
        )
    else:
        c.execute(
            """
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers LIMIT ?
            """,
            (limit,),
        )
    rows = c.fetchall()
    conn.close()
    keys = ["id", "name", "email", "phone", "status", "created_at", "updated_at"]
    customers = [dict(zip(keys, row)) for row in rows]
    return {"status": "success", "customers": customers}


@mcp.tool()
def update_customer(customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"name", "email", "phone", "status"}
    fields = []
    values = []
    for k, v in data.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return {"status": "error", "message": "No valid fields to update"}

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        f"UPDATE customers SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
        (*values, datetime.utcnow().isoformat(), customer_id),
    )
    conn.commit()
    updated = c.rowcount > 0
    conn.close()
    if not updated:
        return {"status": "error", "message": f"No customer with id={customer_id}"}
    return {"status": "success", "customer_id": customer_id}


@mcp.tool()
def create_ticket(customer_id: int, issue: str, priority: str = "medium") -> Dict[str, Any]:
    created_at = datetime.utcnow().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO tickets (customer_id, issue, status, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (customer_id, issue, "open", priority, created_at),
    )
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    return {
        "status": "success",
        "ticket": {
            "id": ticket_id,
            "customer_id": customer_id,
            "issue": issue,
            "status": "open",
            "priority": priority,
            "created_at": created_at,
        },
    }


@mcp.tool()
def get_customer_history(customer_id: int) -> Dict[str, Any]:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT id, issue, status, priority, created_at
        FROM tickets WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (customer_id,),
    )
    rows = c.fetchall()
    conn.close()
    keys = ["id", "issue", "status", "priority", "created_at"]
    tickets = [dict(zip(keys, row)) for row in rows]
    return {"status": "success", "tickets": tickets}


def run_mcp_server_blocking() -> None:
    """Run the MCP server using FastMCP's streamable-http transport."""
    print(f"Starting MCP server at {MCP_URL}")
    mcp.run(transport="streamable-http")


def start_mcp_server_in_background() -> threading.Thread:
    """Start the MCP server in a background thread and return the thread."""
    thread = threading.Thread(target=run_mcp_server_blocking, daemon=True)
    thread.start()
    # Give the server a moment to start
    time.sleep(2)
    print("✅ MCP server should now be running (streamable-http).")
    return thread
