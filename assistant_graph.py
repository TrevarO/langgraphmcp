"""LangGraph implementation for MCP routing."""
from datetime import datetime, timezone
from typing import Annotated, Sequence, Dict, List, TypeVar, TypedDict
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, add_messages

from langgraph_mcp.configuration import Configuration
from langgraph_mcp import mcp_wrapper as mcp
from langgraph_mcp.utils import get_message_text, load_chat_model
from langgraph_mcp.prompts import (
    ROUTER_SYSTEM_PROMPT,
    TOOL_EXECUTOR_SYSTEM_PROMPT,
    ERROR_HANDLING_PROMPT
)

class GraphState(TypedDict):
    """State type for the graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_mcp_server: NotRequired[str]
    tool_outputs: NotRequired[List[str]]
    error_messages: NotRequired[List[str]]

async def route_request(state: GraphState, config: Dict) -> GraphState:
    """Route the request to appropriate MCP tool."""
    configuration = Configuration.from_runnable_config(config)
    messages = state["messages"]
    
    # Format tool descriptions
    tool_descriptions = "\n".join(
        f"- {name}: {details['description']}"
        for name, details in configuration.mcp_server_config["mcpServers"].items()
    )
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    
    # Get decision
    model = load_chat_model(configuration.routing_model)
    result = await model.ainvoke(
        prompt.format_messages(
            tool_descriptions=tool_descriptions,
            input=get_message_text(messages[-1]),
            system_time=datetime.now(tz=timezone.utc).isoformat()
        )
    )
    
    tool_name = result.content.strip().lower()
    
    if tool_name == "none":
        return {
            **state,
            "messages": [AIMessage(content="I need more information. Could you please clarify?")],
            "current_mcp_server": None
        }
    
    return {
        **state,
        "messages": [AIMessage(content=f"Using {tool_name} to help you...")],
        "current_mcp_server": tool_name
    }

async def execute_tool(state: GraphState, config: Dict) -> GraphState:
    """Execute the selected tool."""
    configuration = Configuration.from_runnable_config(config)
    messages = state["messages"]
    server_name = state.get("current_mcp_server")
    
    if not server_name:
        return {
            **state,
            "messages": [AIMessage(content="No tool selected. Please try again.")],
            "error_messages": state.get("error_messages", []) + ["No tool selected"],
            "current_mcp_server": None
        }
    
    try:
        server_config = configuration.mcp_server_config["mcpServers"][server_name]
        tools = await mcp.apply(server_name, server_config, mcp.GetTools())
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", TOOL_EXECUTOR_SYSTEM_PROMPT),
            ("human", "{input}")
        ])
        
        model = load_chat_model(configuration.execution_model)
        result = await model.bind_tools(tools).ainvoke(
            prompt.format_messages(
                tool_description=server_config["description"],
                tool_functions=str(tools),
                input=get_message_text(messages[-1]),
                system_time=datetime.now(tz=timezone.utc).isoformat()
            )
        )
        
        return {
            **state,
            "messages": [result],
            "tool_outputs": state.get("tool_outputs", []) + [str(result)],
            "current_mcp_server": None
        }
        
    except Exception as e:
        error_msg = f"Error executing tool: {str(e)}"
        return {
            **state,
            "messages": [AIMessage(content=error_msg)],
            "error_messages": state.get("error_messages", []) + [error_msg],
            "current_mcp_server": None
        }

def should_continue(state: GraphState) -> str:
    """Determine next step in the workflow."""
    return "execute_tool" if state.get("current_mcp_server") else END

# Create graph with proper state handling
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("route_request", route_request)
workflow.add_node("execute_tool", execute_tool)

# Add edges
workflow.add_conditional_edges(
    "route_request",
    should_continue,
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
workflow.add_edge("execute_tool", "route_request")

# Set entry point and compile
workflow.set_entry_point("route_request")
graph = workflow.compile()