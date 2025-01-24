from datetime import datetime, timezone
from typing import Dict, List, TypedDict, Any
from typing_extensions import NotRequired
import json
import logging
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from src.langgraph_mcp.tool_execution import execute_tool, route_request
from src.langgraph_mcp.transport_manager import transport_manager
from src.langgraph_mcp.configuration import Configuration
from src.langgraph_mcp import mcp_wrapper as mcp
from src.langgraph_mcp.utils import get_message_text, load_chat_model
from src.langgraph_mcp.cleanup_manager import cleanup_manager

logger = logging.getLogger(__name__)

TOOL_INSTRUCTIONS = """You are an AI assistant with access to various tools. When using tools:
1. For search queries, use the provided tools directly without asking for clarification
2. For file operations, execute the requested operation directly
3. Return the results in a clear, concise format

Current tools available:
1. brave_web_search: Use for general web searches and current information
2. brave_local_search: Use for location-specific queries
3. filesystem: Use for file operations
4. mcp-reasoner: Use for complex reasoning tasks

DO NOT ask the user for clarification unless the request is completely unclear.
When using search tools, formulate and execute the search directly."""

class GraphState(TypedDict):
    messages: List[BaseMessage]
    current_mcp_server: NotRequired[str]
    tool_outputs: List[str]

# Initialize prompt templates
router_prompt = ChatPromptTemplate.from_messages([
    ("system", TOOL_INSTRUCTIONS),
    ("human", "{input}")
])

def convert_to_langchain_tools(mcp_tools: List[Dict]) -> List[Dict]:
    """Convert MCP tools to LangChain format"""
    langchain_tools = []
    for tool in mcp_tools:
        if isinstance(tool, dict) and 'function' in tool:
            func = tool['function']
            langchain_tools.append({
                'type': 'function',
                'function': {
                    'name': func.get('name', ''),
                    'description': func.get('description', ''),
                    'parameters': func.get('parameters', {'type': 'object', 'properties': {}})
                }
            })
    return langchain_tools

async def execute_tool_with_cleanup(name: str, tool_type: str, config: Dict, query: str) -> Dict:
    """Execute tool and ensure proper cleanup"""
    try:
        server_config = config["mcpServers"].get(tool_type)
        if not server_config:
            raise ValueError(f"Tool configuration not found: {tool_type}")

        # Get tools
        tools = await mcp.apply(tool_type, server_config, mcp.GetTools())
        
        # Execute search directly without asking for clarification
        if tool_type == "brave-search":
            tool_name = "brave_web_search"
            tool_args = {"query": query}
        else:
            model = load_chat_model(config.get("execution_model"))
            result = await model.bind_tools(convert_to_langchain_tools(tools)).ainvoke(query)
            
            if not result.additional_kwargs.get('tool_calls'):
                return {"content": result.content}
                
            tool_call = result.additional_kwargs['tool_calls'][0]
            tool_name = tool_call['function']['name']
            tool_args = json.loads(tool_call['function']['arguments'])

        # Execute tool
        result = await mcp.apply(tool_type, server_config, mcp.RunTool(tool_name, **tool_args))
        
        # Process result
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass
                
        return {"content": str(result)}

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return {"error": str(e)}

# Replace your existing route_request and execute_tool functions with these imports
from src.langgraph_mcp.tool_execution import route_request, execute_tool

def should_continue(state: GraphState) -> str:
    logger.debug(f"GraphState: {state}")
    return "execute_tool" if state.get("current_mcp_server") else END

# Create and configure the graph
workflow = StateGraph(GraphState)
workflow.add_node("route_request", route_request)
workflow.add_node("execute_tool", execute_tool)

workflow.add_conditional_edges(
    "route_request",
    should_continue,
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
workflow.add_edge("execute_tool", END)
workflow.set_entry_point("route_request")

graph = workflow.compile()