import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from src.langgraph_mcp.assistant_graph import graph, GraphState
import signal
from langchain_core.messages import AIMessage

load_dotenv()

MCP_SERVER_CONFIG = {
    "mcpServers": {
        "filesystem": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-filesystem", "--", "."],
            "description": "File system operations",
            "env": {}
        },
        "puppeteer": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-puppeteer", "--"],
            "description": "Web browser automation",
            "env": {}
        },
        "brave-search": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-brave-search", "--"],
            "description": "Web search operations",
            "env": {"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")}
        },
        "mcp-reasoner": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-mcp-reasoner", "--"],
            "description": "Advanced reasoning",
            "env": {}
        }
    }
}

async def cleanup_servers():
    """Cleanup function for graceful shutdown"""
    print("\nCleaning up servers...")
    try:
        # Get all tasks except the current one
        tasks = [t for t in asyncio.all_tasks() 
                if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"Cleanup error: {e}")

async def main():
    try:
        if not all([os.getenv("BRAVE_API_KEY"), os.getenv("OPENAI_API_KEY")]):
            raise ValueError("Missing required environment variables")
        
        config = {
            "configurable": {
                "routing_model": "openai/gpt-4-0125-preview",
                "execution_model": "openai/gpt-4-0125-preview",
                "mcp_server_config": MCP_SERVER_CONFIG
            }
        }

        while True:
            try:
                user_input = input("\nEnter request (or 'exit' to quit): ")
                if user_input.lower() in ['exit', 'quit', 'q']:
                    break

                state = {
                    "messages": [HumanMessage(content=user_input)],
                    "current_mcp_server": None,
                    "tool_outputs": [],
                }

                start_time = datetime.now()
                result = await graph.ainvoke(state, config)
                
                # Print only the last response
                last_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                if last_messages:
                    print(f"\nAIMessage: {last_messages[-1].content}")
                
                print(f"\nTime: {(datetime.now() - start_time).total_seconds():.2f}s")

            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
                break
            except Exception as e:
                print(f"Error: {e}")

    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await cleanup_servers()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")