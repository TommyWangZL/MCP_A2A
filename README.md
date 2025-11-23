# Multi-Agent Customer Service System

This project implements a multi-agent customer service system using agent-to-agent coordination and MCP-style database tools. It includes three agents that work together to process customer queries:

- Router Agent  
- Customer Data Agent  
- Support Agent  

The system uses a SQLite database that is automatically created and populated when the program runs. It supports retrieving and updating customer information, creating tickets, handling support issues, and performing multi-step coordination across agents.

## What the System Does

- Creates and initializes a SQLite database (`support.db`)
- Provides MCP-style tools:
  - get customer information
  - list customers by status
  - update customer information
  - create tickets
  - get customer ticket history
- Routes queries through the Router Agent
- Retrieves customer data through the Customer Data Agent
- Handles support logic through the Support Agent
- Supports task allocation, negotiation, escalation, multi-step coordination, and multi-intent queries
- Prints detailed agent-to-agent communication logs for every query

## How to Use

1. Make sure `database_setup.py` is placed in the same directory as `main.py`.

2. Install Python 3.9 or above.

3. (Optional) Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the system:

```bash
python main.py
```

6. The program will:
   - Create the database
   - Insert sample customers
   - Run all test scenarios
   - Show each query, response, and agent-to-agent communication log

## File Structure

```
main.py
database_setup.py
requirements.txt
support.db (created automatically)
```

## Notes

- Queries without an explicit customer ID use a default demo user.
- The MCP server is implemented as a simple Python class for local testing.
****
