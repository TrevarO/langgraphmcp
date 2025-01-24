import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from src.langgraph_mcp.assistant_graph import graph
from src.langgraph_mcp.server_manager import server_manager, manage_event_loop
from src.langgraph_mcp.config import MCP_SERVER_CONFIG
from src.langgraph_mcp.logging_config import setup_logging

logger = setup_logging()

async def start_mcp_server(name: str, config: Dict[str, Any]) -> asyncio.Task:
    """Start and manage an MCP server process"""
    try:
        # Prepare command and environment
        cmd = [config["command"]] + config["args"]
        env = {**os.environ, **config.get("env", {})}
        
        # Create and register the process
        process = await server_manager.create_server_process(name, cmd, env)
        
        # Create and register server task
        async def run_server():
            try:
                await process.wait()
            finally:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                    
        return await server_manager.add_server(name, run_server())
        
    except Exception as e:
        logger.error(f"Failed to start MCP server {name}: {e}")
        raise

async def main():
    async with manage_event_loop() as loop:
        try:
            # Start MCP servers
            servers = []
            for name, config in MCP_SERVER_CONFIG["mcpServers"].items():
                try:
                    server = await start_mcp_server(name, config)
                    servers.append(server)
                except Exception as e:
                    logger.error(f"Failed to start {name}: {e}")
                    raise
            
            while True:
                try:
                    user_input = input("\nEnter request (or 'exit' to quit): ").strip()
                    if user_input.lower() in ['exit', 'quit', 'q', '']:
                        break
                        
                    state = {
                        "messages": [HumanMessage(content=user_input)],
                        "current_mcp_server": None,
                        "tool_outputs": []
                    }
                    
                    start_time = datetime.now()
                    try:
                        result = await graph.ainvoke(state, {
                            "configurable": {
                                "routing_model": "openai/gpt-4-0125-preview",
                                "execution_model": "openai/gpt-4-0125-preview",
                                "mcp_server_config": MCP_SERVER_CONFIG
                            }
                        })
                        
                        ai_messages = [msg for msg in result["messages"] 
                                     if isinstance(msg, AIMessage)]
                        if ai_messages:
                            print(f"\nAssistant: {ai_messages[-1].content}")
                    except Exception as e:
                        logger.error(f"Error processing request: {e}")
                        print(f"Error: {str(e)}")
                        
                    print(f"\nTime: {(datetime.now() - start_time).total_seconds():.2f}s")
                    
                except KeyboardInterrupt:
                    if sys.platform == "win32":
                        await server_manager.shutdown()
                    logger.info("Operation cancelled by user")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)