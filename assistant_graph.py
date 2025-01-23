from datetime import datetime, timezone
from typing import Annotated, Sequence, Dict, List, TypedDict, Any
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, add_messages
from langgraph_mcp.configuration import Configuration
from langgraph_mcp import mcp_wrapper as mcp
from langgraph_mcp.utils import get_message_text, load_chat_model
from langgraph_mcp.prompts import ROUTER_SYSTEM_PROMPT, TOOL_EXECUTOR_SYSTEM_PROMPT

class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_mcp_server: NotRequired[str]
    tool_outputs: List[str]

async def route_request(state: GraphState, config: Dict) -> Dict[str, Any]:
    print("\n=== DEBUG: route_request start ===")
    print(f"Input state: {state}")
    
    configuration = Configuration.from_runnable_config(config)
    tool_descriptions = "\n".join(
        f"- {name}: {details['description']}"
        for name, details in configuration.mcp_server_config["mcpServers"].items()
    )
    
    print(f"Tool descriptions: {tool_descriptions}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    
    model = load_chat_model(configuration.routing_model)
    print("\nBefore model invoke")
    result = await model.ainvoke(
        prompt.format_messages(
            tool_descriptions=tool_descriptions,
            input=get_message_text(state["messages"][-1]),
            system_time=datetime.now(tz=timezone.utc).isoformat()
        )
    )
    print(f"Model result: {result}")
    
    tool_name = result.content.strip().lower()
    tool_name = tool_name.replace('"', '').replace("'", '')
    
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

async def execute_tool(state: GraphState, config: Dict) -> Dict[str, Any]:
    print("\n=== DEBUG: execute_tool start ===")
    print(f"Input state: {state}")
    
    configuration = Configuration.from_runnable_config(config)
    server_name = state.get("current_mcp_server")
    
    if not server_name:
        return {
            "messages": [AIMessage(content="No tool selected")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

    try:
        server_config = configuration.mcp_server_config["mcpServers"][server_name]
        print(f"Getting tools from {server_name}")
        tools = await mcp.apply(server_name, server_config, mcp.GetTools())
        print(f"Retrieved tools: {tools}")

        # Create LangChain tools from MCP tools
        langchain_tools = []
        for tool in tools:
            if isinstance(tool, dict) and 'function' in tool:
                func = tool['function']
                langchain_tools.append({
                    'name': func['name'],
                    'description': func.get('description', ''),
                    'parameters': func.get('parameters', {})
                })

        prompt = ChatPromptTemplate.from_messages([
            ("system", TOOL_EXECUTOR_SYSTEM_PROMPT),
            ("human", "{input}")
        ])
        model = load_chat_model(configuration.execution_model)

        # Use simplified tool format
        result = await model.invoke(
            prompt.format_messages(
                tool_description=server_config["description"],
                input=get_message_text(state["messages"][-1]),
                tools=langchain_tools
            ),
            config={"tools": langchain_tools}  # Pass tools in config
        )
        
        return {
            "messages": [result],
            "current_mcp_server": None,
            "tool_outputs": [str(result)]
        }
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
        
    except Exception as e:
        print(f"Error details: {str(e)}")  # Add more detailed error logging
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
        print(f"Error occurred: {e}")
        print(f"Returning: {return_state}")
        return return_state

def route_or_end(state: GraphState) -> str:
    """Decide where to go next based on whether a tool is selected."""
    print("\n=== DEBUG: should_continue ===")
    print(f"Input state: {state}")
    current_server = state.get("current_mcp_server")
    next_node = "execute_tool" if current_server and current_server != "none" else END
    print(f"Next node: {next_node}")
    print("=== DEBUG: should_continue end ===\n")
    return next_node

workflow = StateGraph(GraphState)
workflow.add_node("route_request", route_request)
workflow.add_node("execute_tool", execute_tool)

# Simplified edge definition for v0.2.65
workflow.add_conditional_edges(
    "route_request",
    route_or_end,  # This now returns string directly
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
workflow.add_edge("execute_tool", "route_request")
workflow.set_entry_point("route_request")

graph = workflow.compile()