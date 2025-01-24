import asyncio
from typing import Dict, Any, List
from langchain_core.messages import AIMessage
import json
import logging
from src.langgraph_mcp import mcp_wrapper as mcp
from src.langgraph_mcp.utils import get_message_text, load_chat_model
from src.langgraph_mcp.state import GraphState

logger = logging.getLogger(__name__)

async def execute_brave_search(config: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Execute Brave Search directly"""
    try:
        server_config = config["mcpServers"]["brave-search"]
        tools = await mcp.apply("brave-search", server_config, mcp.GetTools())
        
        result = await mcp.apply(
            "brave-search",
            server_config,
            mcp.RunTool("brave_web_search", query=query)
        )
        
        return {
            "messages": [AIMessage(content=str(result))],
            "tool_outputs": [str(result)]
        }
    except Exception as e:
        logger.error(f"Brave Search error: {e}")
        return {
            "messages": [AIMessage(content=f"Search error: {str(e)}")],
            "tool_outputs": []
        }

async def execute_filesystem(config: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Execute filesystem operations"""
    try:
        server_config = config["mcpServers"]["filesystem"]
        tools = await mcp.apply("filesystem", server_config, mcp.GetTools())
        
        # Handle list directory request
        if "list" in query.lower():
            result = await mcp.apply(
                "filesystem",
                server_config,
                mcp.RunTool("list_directory", path=".")
            )
        else:
            result = await mcp.apply(
                "filesystem",
                server_config,
                mcp.RunTool("list_allowed_directories")
            )
            
        return {
            "messages": [AIMessage(content=str(result))],
            "tool_outputs": [str(result)]
        }
    except Exception as e:
        logger.error(f"Filesystem error: {e}")
        return {
            "messages": [AIMessage(content=f"Filesystem error: {str(e)}")],
            "tool_outputs": []
        }

async def route_request(state: GraphState, config: Dict) -> Dict[str, Any]:
    """Simplified routing logic"""
    try:
        query = get_message_text(state["messages"][-1])
        
        # Simple routing based on keywords
        if any(word in query.lower() for word in ["weather", "temperature"]):
            return {
                "messages": [AIMessage(content="Using brave-search...")],
                "current_mcp_server": "brave-search",
                "tool_outputs": [],
                "query": query
            }
        elif any(word in query.lower() for word in ["list", "files", "directory"]):
            return {
                "messages": [AIMessage(content="Using filesystem...")],
                "current_mcp_server": "filesystem",
                "tool_outputs": [],
                "query": query
            }
        else:
            return {
                "messages": [AIMessage(content="Using none...")],
                "current_mcp_server": None,
                "tool_outputs": []
            }
    except Exception as e:
        logger.error(f"Routing error: {e}")
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

async def execute_tool(state: GraphState, config: Dict) -> Dict[str, Any]:
    """Simplified tool execution"""
    try:
        tool_type = state.get("current_mcp_server")
        query = state.get("query", "")
        
        if not tool_type:
            return {
                "messages": state["messages"],
                "tool_outputs": []
            }
            
        if tool_type == "brave-search":
            return await execute_brave_search(
                config["configurable"]["mcp_server_config"],
                query
            )
        elif tool_type == "filesystem":
            return await execute_filesystem(
                config["configurable"]["mcp_server_config"],
                query
            )
        else:
            return {
                "messages": [AIMessage(content=f"Unknown tool: {tool_type}")],
                "tool_outputs": []
            }
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "tool_outputs": []
        }