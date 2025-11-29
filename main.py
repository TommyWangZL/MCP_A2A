"""Entry point: init DB, start MCP + A2A servers, optionally run a scenario."""

import argparse
import time

from db_init import init_db_with_professor_script
from mcp_server import start_mcp_server_in_background
from a2a_servers import start_agents_in_background
from test_scenarios import run_single_test
import asyncio


def main():
    parser = argparse.ArgumentParser(description="Start MCP + A2A servers and optionally run a scenario.")
    parser.add_argument(
        "--scenario",
        type=int,
        default=None,
        help="Optional scenario index to run after servers are up (0-7).",
    )
    args = parser.parse_args()

    # 1) Initialize DB
    init_db_with_professor_script()

    # 2) Start MCP + A2A servers
    start_mcp_server_in_background()
    start_agents_in_background()

    print("System is up.")

    if args.scenario is not None:
        print(f"Running scenario {args.scenario}...")
        asyncio.run(run_single_test(args.scenario))
    else:
        print("No scenario specified. Servers will keep running until process is stopped.")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            print("Shutting down...")


if __name__ == "__main__":
    main()
