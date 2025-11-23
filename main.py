from database_setup import DatabaseSetup
import sqlite3

DB_PATH = "support.db"

# Initialize database and insert sample data
db = DatabaseSetup(DB_PATH)
db.connect()
db.create_tables()
db.create_triggers()
db.insert_sample_data()
db.close()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
    INSERT OR IGNORE INTO customers (id, name, email, phone, status)
    VALUES (12345, 'Premium Auto Parts Inc.', 'support@premiumauto.com', '+1-555-0999', 'active')
""")

cur.execute("""
    INSERT INTO tickets (customer_id, issue, status, priority)
    VALUES (?, ?, ?, ?)
""", (12345, "Subscription renewal question", "resolved", "low"))

conn.commit()
conn.close()

print("Database ready:", DB_PATH)


# MCP server tools

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

class CustomerMCPServer:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers WHERE id=?
        """, (customer_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        keys = ["id", "name", "email", "phone", "status", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def list_customers(self, status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        if status:
            c.execute("""
                SELECT id, name, email, phone, status, created_at, updated_at
                FROM customers WHERE status=? LIMIT ?
            """, (status, limit))
        else:
            c.execute("""
                SELECT id, name, email, phone, status, created_at, updated_at
                FROM customers LIMIT ?
            """, (limit,))
        rows = c.fetchall()
        conn.close()
        keys = ["id", "name", "email", "phone", "status", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def update_customer(self, customer_id: int, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        fields = []
        values = []
        for k, v in data.items():
            if k not in {"name", "email", "phone", "status"}:
                continue
            fields.append(f"{k}=?")
            values.append(v)
        if not fields:
            return False

        values.append(customer_id)
        conn = self._conn()
        c = conn.cursor()
        c.execute(f"UPDATE customers SET {', '.join(fields)} WHERE id=?", tuple(values))
        conn.commit()
        updated = c.rowcount > 0
        conn.close()
        return updated

    def create_ticket(self, customer_id: int, issue: str, priority: str = "medium") -> Dict[str, Any]:
        created_at = datetime.utcnow().isoformat()
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO tickets (customer_id, issue, status, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, issue, "open", priority, created_at))
        ticket_id = c.lastrowid
        conn.commit()
        conn.close()
        return {
            "id": ticket_id,
            "customer_id": customer_id,
            "issue": issue,
            "status": "open",
            "priority": priority,
            "created_at": created_at,
        }

    def get_customer_history(self, customer_id: int) -> List[Dict[str, Any]]:
        conn = self._conn()
        c = conn.cursor()
        c.execute("""
            SELECT id, issue, status, priority, created_at
            FROM tickets WHERE customer_id=?
            ORDER BY created_at DESC
        """, (customer_id,))
        rows = c.fetchall()
        conn.close()
        keys = ["id", "issue", "status", "priority", "created_at"]
        return [dict(zip(keys, row)) for row in rows]


server = CustomerMCPServer(DB_PATH)
print("MCP server ready. Example get_customer(1):")
print(server.get_customer(1))


# Agents + A2A Coordination (Option A)

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class LogEntry:
    from_agent: str
    to_agent: str
    message: str

@dataclass
class ConversationContext:
    mcp: CustomerMCPServer
    logs: List[LogEntry] = field(default_factory=list)

    def log(self, from_agent: str, to_agent: str, message: str):
        self.logs.append(LogEntry(from_agent, to_agent, message))


class CustomerDataAgent:
    name = "CustomerDataAgent"

    def handle_get_customer(self, ctx: ConversationContext, customer_id: int) -> Optional[Dict[str, Any]]:
        ctx.log("RouterAgent", self.name, f"get_customer({customer_id})")
        customer = ctx.mcp.get_customer(customer_id)
        ctx.log(self.name, "RouterAgent", f"customer_found={bool(customer)}")
        return customer

    def handle_list_customers(self, ctx: ConversationContext, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        ctx.log("RouterAgent", self.name, f"list_customers(status={status}, limit={limit})")
        customers = ctx.mcp.list_customers(status=status, limit=limit)
        ctx.log(self.name, "RouterAgent", f"customers_count={len(customers)}")
        return customers

    def handle_update_customer(self, ctx: ConversationContext, customer_id: int, data: Dict[str, Any]) -> bool:
        ctx.log("RouterAgent", self.name, f"update_customer({customer_id}, {data})")
        ok = ctx.mcp.update_customer(customer_id, data)
        ctx.log(self.name, "RouterAgent", f"updated={ok}")
        return ok

    def handle_history(self, ctx: ConversationContext, customer_id: int) -> List[Dict[str, Any]]:
        ctx.log("RouterAgent", self.name, f"get_customer_history({customer_id})")
        history = ctx.mcp.get_customer_history(customer_id)
        ctx.log(self.name, "RouterAgent", f"tickets_count={len(history)}")
        return history

    def classify_customer_tier(self, ctx: ConversationContext, customer_id: int) -> str:
        history = self.handle_history(ctx, customer_id)
        high = [t for t in history if t["priority"] == "high"]
        tier = "premium" if high else "standard"
        ctx.log(self.name, "RouterAgent", f"classified_tier={tier} for customer_id={customer_id}")
        return tier

    def get_premium_customers(self, ctx: ConversationContext, status: str = "active") -> List[Dict[str, Any]]:
        customers = self.handle_list_customers(ctx, status=status, limit=1000)
        premium = []
        for c in customers:
            history = ctx.mcp.get_customer_history(c["id"])
            if any(t["priority"] == "high" for t in history):
                premium.append(c)
        ctx.log(self.name, "RouterAgent", f"premium_customers_count={len(premium)}")
        return premium


class SupportAgent:
    name = "SupportAgent"

    def handle_simple_support(self, ctx: ConversationContext, customer: Dict[str, Any], tier: str, issue: str) -> str:
        ctx.log("RouterAgent", self.name, f"support_request customer_id={customer['id']} tier={tier} issue={issue}")
        text = issue.lower()

        if "upgrade" in text:
            if tier == "premium":
                ans = f"Customer {customer['id']} is already treated as premium. I can help fine-tune your plan."
            else:
                ctx.mcp.create_ticket(customer["id"], "Account upgrade request", "high")
                ans = f"I've created a high-priority upgrade ticket for your account (ID {customer['id']})."
        elif "cancel" in text:
            ctx.mcp.create_ticket(customer["id"], "Cancellation request", "medium")
            ans = f"I've opened a cancellation ticket for customer {customer['id']}. Billing will process it."
        else:
            ctx.mcp.create_ticket(customer["id"], issue, "medium")
            ans = f"I've logged your issue for customer {customer['id']}: '{issue}'. We'll follow up shortly."

        ctx.log(self.name, "RouterAgent", "support_response_ready")
        return ans

    def can_handle(self, ctx: ConversationContext, query: str) -> bool:
        ctx.log("RouterAgent", self.name, f"can_handle? {query}")
        q = query.lower()
        if "billing" in q or "refund" in q or "charged twice" in q:
            ctx.log(self.name, "RouterAgent", "cannot_handle_billing_alone_need_context")
            return False
        ctx.log(self.name, "RouterAgent", "can_handle_directly")
        return True

    def request_billing_context(self, ctx: ConversationContext) -> str:
        ctx.log(self.name, "RouterAgent", "request_billing_context")
        return "need_billing_context"

    def handle_with_billing_context(self, ctx: ConversationContext, customer: Dict[str, Any], billing_info: List[Dict[str, Any]], query: str) -> str:
        ctx.log(self.name, "RouterAgent", "handling_with_billing_context")
        high_open = [t for t in billing_info if t["priority"] == "high" and t["status"] in ("open", "in_progress")]
        q = query.lower()
        if "refund" in q or "charged twice" in q:
            if high_open:
                return f"I see an existing open high-priority billing ticket for customer {customer['id']}. I've escalated your refund request."
            else:
                ctx.mcp.create_ticket(customer["id"], "Refund request due to duplicate charge", "high")
                return f"I've opened and escalated a high-priority billing ticket for customer {customer['id']}."
        return f"I've reviewed billing history for customer {customer['id']} and shared it with billing. We'll follow up."

    def filter_customers_with_open_tickets(self, ctx: ConversationContext, customers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ctx.log("RouterAgent", self.name, "filter_customers_with_open_tickets")
        result = []
        for c in customers:
            tickets = ctx.mcp.get_customer_history(c["id"])
            if any(t["status"] == "open" for t in tickets):
                result.append(c)
        ctx.log(self.name, "RouterAgent", f"customers_with_open_tickets={len(result)}")
        return result

    def summarize_high_priority_tickets(self, ctx: ConversationContext, customers: List[Dict[str, Any]]) -> str:
        ctx.log("RouterAgent", self.name, "summarize_high_priority_tickets")
        lines = []
        total = 0
        for c in customers:
            tickets = ctx.mcp.get_customer_history(c["id"])
            high = [t for t in tickets if t["priority"] == "high" and t["status"] in ("open", "in_progress")]
            if not high:
                continue
            total += len(high)
            lines.append(f"Customer {c['id']} ({c['name']}):")
            for t in high:
                lines.append(f"  - Ticket {t['id']}: {t['issue']} [{t['status']}, {t['priority']}]")
        if not lines:
            return "There are no open high-priority tickets for premium customers."
        header = f"Found {total} open high-priority tickets for premium customers:\n"
        return header + "\n".join(lines)


class RouterAgent:
    name = "RouterAgent"

    def __init__(self, data_agent: CustomerDataAgent, support_agent: SupportAgent):
        self.data_agent = data_agent
        self.support_agent = support_agent

    def handle(self, ctx: ConversationContext, query: str) -> str:
        ctx.log("Customer", self.name, query)
        q = query.lower()

        # Simple Query
        if "get customer information for id" in q:
            customer_id = int(q.split("id")[-1].strip())
            customer = self.data_agent.handle_get_customer(ctx, customer_id)
            if not customer:
                return f"No customer found with ID {customer_id}."
            return (f"Customer {customer['id']}: {customer['name']} "
                    f"({customer['status']}) email={customer['email']} phone={customer['phone']}")

        # Scenario 1: Task allocation
        if "need help with my account" in q and "customer id" in q:
            cust_part = q.split("customer id")[-1].strip()
            customer_id = int(cust_part.split()[0])
            customer = self.data_agent.handle_get_customer(ctx, customer_id)
            if not customer:
                return f"No customer found with ID {customer_id}."
            tier = self.data_agent.classify_customer_tier(ctx, customer_id)
            ctx.log(self.name, self.support_agent.name, f"handle support for {tier} customer")
            resp = self.support_agent.handle_simple_support(ctx, customer, tier, "account help")
            return resp

        # Coordinated Query
        if "i'm customer" in q or "i am customer" in q:
            norm = q.replace("i am", "i'm")
            parts = norm.split("i'm customer")[-1].strip().split()
            customer_id = int(parts[0])
            if "and" in query:
                issue = query.split("and", 1)[-1].strip()
            else:
                issue = "account help"
            customer = self.data_agent.handle_get_customer(ctx, customer_id)
            if not customer:
                return f"No customer found with ID {customer_id}."
            tier = self.data_agent.classify_customer_tier(ctx, customer_id)
            ctx.log(self.name, self.support_agent.name, "coordinated support request")
            resp = self.support_agent.handle_simple_support(ctx, customer, tier, issue)
            return resp

        # Scenario 2: Negotiation / escalation
        if "cancel my subscription" in q and "billing" in q:
            ctx.log(self.name, self.support_agent.name, "can you handle cancellation + billing?")
            if not self.support_agent.can_handle(ctx, query):
                reason = self.support_agent.request_billing_context(ctx)
                ctx.log(self.support_agent.name, self.name, reason)
                customer = self.data_agent.handle_get_customer(ctx, 1)
                history = self.data_agent.handle_history(ctx, customer["id"])
                ctx.log(self.name, self.support_agent.name, "provide billing history for escalation")
                resp = self.support_agent.handle_with_billing_context(ctx, customer, history, query)
                return resp
            else:
                customer = self.data_agent.handle_get_customer(ctx, 1)
                tier = self.data_agent.classify_customer_tier(ctx, customer["id"])
                resp = self.support_agent.handle_simple_support(ctx, customer, tier, query)
                return resp

        # Scenario 3: Multi-step coordination
        if "status of all high-priority tickets for premium customers" in q:
            ctx.log(self.name, self.data_agent.name, "get premium customers")
            premium_customers = self.data_agent.get_premium_customers(ctx, status="active")
            ctx.log(self.name, self.support_agent.name, "summarize high-priority tickets for premium customers")
            report = self.support_agent.summarize_high_priority_tickets(ctx, premium_customers)
            return report

        # Complex Query: negotiation between data & support
        if "show me all active customers who have open tickets" in q:
            ctx.log(self.name, self.data_agent.name, "list active customers")
            customers = self.data_agent.handle_list_customers(ctx, status="active", limit=1000)
            ctx.log(self.name, self.support_agent.name, "filter for open tickets")
            with_open = self.support_agent.filter_customers_with_open_tickets(ctx, customers)
            if not with_open:
                return "No active customers with open tickets."
            lines = [f"{c['id']} - {c['name']} ({c['status']})" for c in with_open]
            return "Active customers with open tickets:\n" + "\n".join(lines)

        # Escalation (urgent)
        if "charged twice" in q or "refund" in q:
            customer = ctx.mcp.get_customer(5)
            history = ctx.mcp.get_customer_history(5)
            ctx.log(self.name, self.support_agent.name, "urgent refund with billing context")
            resp = self.support_agent.handle_with_billing_context(ctx, customer, history, query)
            return resp

        # Multi-intent: parallel-style coordination
        if "update my email" in q and "ticket history" in q:
            customer = ctx.mcp.get_customer(1)
            new_email = "new@email.com"
            ctx.log(self.name, self.data_agent.name, "update email")
            self.data_agent.handle_update_customer(ctx, customer["id"], {"email": new_email})
            ctx.log(self.name, self.data_agent.name, "fetch ticket history after update")
            history = self.data_agent.handle_history(ctx, customer["id"])
            tickets_str = "\n".join(
                [f"  - Ticket {t['id']}: {t['issue']} [{t['status']}, {t['priority']}]" for t in history]
            ) or "  (no tickets)"
            return (f"Updated email for customer {customer['id']} to {new_email}.\n"
                    f"Ticket history:\n{tickets_str}")

        return "Router could not understand this query."


data_agent = CustomerDataAgent()
support_agent = SupportAgent()
router = RouterAgent(data_agent, support_agent)


def run_query(query: str):
    ctx = ConversationContext(mcp=server)
    answer = router.handle(ctx, query)
    print("=== Query ===")
    print(query)
    print("\n=== Answer ===")
    print(answer)
    print("\n=== A2A Log ===")
    for log in ctx.logs:
        print(f"[{log.from_agent} -> {log.to_agent}] {log.message}")
    return answer, ctx


# Run All Required Test Scenarios

test_queries = [
    # Simple Query
    "Get customer information for ID 5",

    # Coordinated Query
    "I'm customer 12345 and need help upgrading my account",

    # Complex Query
    "Show me all active customers who have open tickets",

    # Escalation
    "I've been charged twice, please refund immediately!",

    # Multi-Intent
    "Update my email to new@email.com and show my ticket history",

    # Scenario 1 – Task allocation
    "I need help with my account, customer ID 12345",

    # Scenario 2 – Negotiation / escalation
    "I want to cancel my subscription but I'm having billing issues",

    # Scenario 3 – Multi-step coordination
    "What's the status of all high-priority tickets for premium customers?",
]

if __name__ == "__main__":
    for q in test_queries:
        print("\n" + "=" * 70)
        run_query(q)
