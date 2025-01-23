"""LangGraph implementation for MCP routing."""
from typing import Annotated, Sequence, Dict, List, TypedDict, Any
from typing_extensions import NotRequired
from datetime import datetime, timezone
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, add_messages

from langgraph_mcp.configuration import Configuration
from langgraph_mcp import mcp_wrapper as mcp
from langgraph_mcp.utils import get_message_text, load_chat_model
from langgraph_mcp.prompts import ROUTER_SYSTEM_PROMPT, TOOL_EXECUTOR_SYSTEM_PROMPT

from typing import Annotated, Sequence, Dict, List, TypedDict, Any
from typing_extensions import NotRequired
from datetime import datetime, timezone
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, add_messages

class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_mcp_server: NotRequired[str]
    tool_outputs: List[str]

# ---------------------------------
# route_request Node
# ---------------------------------
async def route_request(state: GraphState, config: Dict) -> Dict[str, Any]:
    """Decide which MCP tool (server) to use."""
    # Load config and prepare prompt
    configuration = Configuration.from_runnable_config(config)
    tool_descriptions = "\n".join(
        f"- {name}: {details['description']}"
        for name, details in configuration.mcp_server_config["mcpServers"].items()
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    
    # Load the routing model and invoke it
    model = load_chat_model(configuration.routing_model)
    result = await model.ainvoke(
        prompt.format_messages(
            tool_descriptions=tool_descriptions,
            input=get_message_text(state["messages"][-1]),
            system_time=datetime.now(tz=timezone.utc).isoformat()
        )
    )

    tool_name = result.content.strip().lower()
    if tool_name == "none":
        return {
            "messages": [AIMessage(content="I need more information. Could you please clarify?")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
    
    return {
        "messages": [AIMessage(content=f"Using {tool_name} to help you...")],
        "current_mcp_server": tool_name,
        "tool_outputs": []
    }

    # Otherwise, prepare to use that tool
 #   return {
  #      "messages": [AIMessage(content=f"Using {tool_name} to help you...")],
   #     "current_mcp_server": tool_name,
    #    "tool_outputs": []
    #}


# ---------------------------------
# execute_tool Node
# ---------------------------------
async def execute_tool(state: GraphState, config: Dict) -> Dict[str, Any]:
    """Invoke the selected MCP server/tool with the user's request."""
    configuration = Configuration.from_runnable_config(config)
    server_name = state.get("current_mcp_server")

    # If no tool selected, return an error message
    if not server_name:
        return {
            "messages": [AIMessage(content="No tool selected")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

    try:
        # Fetch the server config and available tools
        server_config = configuration.mcp_server_config["mcpServers"][server_name]
        tools = await mcp.apply(server_name, server_config, mcp.GetTools())
        
        # Build the executor prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", TOOL_EXECUTOR_SYSTEM_PROMPT),
            ("human", "{input}")
        ])
        model = load_chat_model(configuration.execution_model)

        # Actually call the model (binding tools)
        result = await model.bind_tools(tools).ainvoke(
            prompt.format_messages(
                tool_description=server_config["description"],
                input=get_message_text(state["messages"][-1])
            )
        )
        
        # Return the new message with the tool's output
        return {
            "messages": [result],
            "current_mcp_server": None,  
            "tool_outputs": [str(result)]
        }
        
    except Exception as e:
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

async def end_node(state: GraphState, config: Dict) -> Dict[str, Any]:
   return {"messages": state["messages"]}
# ---------------------------------
# Routing Logic
# ---------------------------------
def should_continue(state: GraphState) -> str:
    return "execute_tool" if state.get("current_mcp_server") else "end"

def route_or_end(state: GraphState) -> Dict[str, str]:
    return "execute_tool" if state.get("current_mcp_server") else END

workflow = StateGraph(GraphState)
workflow.add_node("route_request", route_request)
workflow.add_node("execute_tool", execute_tool)

workflow.add_conditional_edges(
    "route_request",
    route_or_end,
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
workflow.add_edge("execute_tool", "route_request")
workflow.set_entry_point("route_request")
graph = workflow.compile()

__all__ = ["graph", "GraphState"]