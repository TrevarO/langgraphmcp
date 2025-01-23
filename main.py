"""Main entry point for MCP system."""
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph_mcp.assistant_graph import graph, GraphState
import json

# Load environment variables
load_dotenv()

if not os.getenv("BRAVE_API_KEY"):
    raise ValueError("BRAVE_API_KEY not found in environment variables")

# MCP server configurations
MCP_SERVER_CONFIG = {
    "mcpServers": {
        "filesystem": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-filesystem", "--", "."],
            "description": "File system operations: read, write, list, create directories, search files, and get file info",
            "env": {}
        },
        "puppeteer": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-puppeteer", "--"],
            "description": "Web browser automation: navigate pages, click elements, fill forms, take screenshots",
            "env": {}
        },
        "brave-search": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-brave-search", "--"],
            "description": "Web search operations: general queries, local business search, news search",
            "env": {
                # Use actual environment variable instead of placeholder
                "BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")
            }
        },
        "mcp-reasoner": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-mcp-reasoner", "--"],
            "description": "Advanced reasoning: step-by-step analysis, Beam Search, Monte Carlo Tree Search",
            "env": {}
        }
    }
}

async def debug_graph_invoke(state, config):
    print("\n=== DEBUG: graph.ainvoke start ===")
    print(f"Initial state: {state}")
    print(f"Config: {config}")
    
    # NEW: Log server configurations
    print("\nMCP Server Configurations:")
    for server, details in config['configurable']['mcp_server_config']['mcpServers'].items():
        print(f"- {server}: {details['description']}")
    
    try:
        result = await graph.ainvoke(state, config)
        print(f"Result: {result}")
        print("=== DEBUG: graph.ainvoke end ===\n")
        return result
    except Exception as e:
        print(f"Error in graph.ainvoke: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # NEW: Log additional context
        print("\nFull State Dump:")
        print(json.dumps(state, indent=2, default=str))
        
        raise

async def main():
    """Main execution loop"""
    print("Starting LangGraph MCP system with router agent...")
    
    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # Initialize configuration
        config = {
            "configurable": {
                "routing_model": "openai/gpt-4-0125-preview",
                "execution_model": "openai/gpt-4-0125-preview",
                "mcp_server_config": MCP_SERVER_CONFIG
            }
        }
        
        print("\nInitialized with available tools:")
        for server, details in MCP_SERVER_CONFIG["mcpServers"].items():
            print(f"- {server}: {details['description']}")
        
        # Main interaction loop
        while True:
            try:
                # Get user input
                user_input = input("\nEnter your request (or 'exit' to quit): ")
                if user_input.lower() in ['exit', 'quit', 'q']:
                    break
                
                # Create state
                state = {
                    "messages": [HumanMessage(content=user_input)],
                    "current_mcp_server": None,
                    "tool_outputs": [],
                }
                
                # Execute graph
                print("\nProcessing request...")
                start_time = datetime.now()
                final_state = await debug_graph_invoke(state, config)
                end_time = datetime.now()
                
                # Display results
                for msg in final_state["messages"][1:]:  # Skip the initial human message
                    content = msg.content if hasattr(msg, 'content') else str(msg)
                    print(f"\n{msg.__class__.__name__}: {content}")
                
                if final_state.get("error_messages"):
                    print("\nErrors encountered:")
                    for error in final_state["error_messages"]:
                        print(f"- {error}")
                
                print(f"\nProcessing time: {(end_time - start_time).total_seconds():.2f} seconds")
                
            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
                break
            except Exception as e:
                print(f"\nError processing request: {str(e)}")
                print("Try another request or type 'exit' to quit")
    
    except Exception as e:
        print(f"\nFatal error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())