from fastmcp import Client
import asyncio
import json

async def main():
    # Connect via HTTP to the running MCP server
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
        print(f"Available tools: {tools}")

        # Example calling a tool with parameters
        result = await client.call_tool(
            "get_historical_stock_prices",
            {
                "ticker": "AAPL.US",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            }
        )
        print(f"Result:\n{result}")

if __name__ == "__main__":
    asyncio.run(main())