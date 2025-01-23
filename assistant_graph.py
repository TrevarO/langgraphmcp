from datetime import datetime, timezone
from typing import Annotated, Sequence, Dict, List, TypedDict, Any
from typing_extensions import NotRequired
import json
import re
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, add_messages
from langgraph_mcp.configuration import Configuration
from langgraph_mcp import mcp_wrapper as mcp
from langgraph_mcp.utils import get_message_text, load_chat_model
from langgraph_mcp.prompts import ROUTER_SYSTEM_PROMPT, TOOL_EXECUTOR_SYSTEM_PROMPT

class GraphState(TypedDict):
    """State type for the graph."""
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
    
    # NEW: Add query parsing
    user_query = get_message_text(state["messages"][-1])
    query_actions = re.split(r'\band\b', user_query, flags=re.IGNORECASE)
    
    # Log parsed actions for debugging
    print("Parsed Query Actions:")
    for action in query_actions:
        print(f"- {action.strip()}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ROUTER_SYSTEM_PROMPT),
        ("human", "{input}")
    ])
    
    model = load_chat_model(configuration.routing_model)
    print("\nBefore model invoke")
    result = await model.ainvoke(
        prompt.format_messages(
            tool_descriptions=tool_descriptions,
            input=user_query,  # Use original query
            system_time=datetime.now(tz=timezone.utc).isoformat()
        )
    )
    
    tool_name = result.content.strip().lower()
    print(f"Selected tool: {tool_name}")
    
    return {
        "messages": [AIMessage(content=f"Using {tool_name} to help you...")],
        "current_mcp_server": None if tool_name == "none" else tool_name,
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
        mcp_tools = await mcp.apply(server_name, server_config, mcp.GetTools())
        print(f"MCP Tools received: {json.dumps(mcp_tools, indent=2)}")

        # Convert MCP tools to LangChain format
        langchain_tools = []
        for tool in mcp_tools:
            try:
                if isinstance(tool, dict) and 'function' in tool:
                    func = tool['function']
                    langchain_tool = {
                        'type': 'function',
                        'function': {
                            'name': func.get('name', ''),
                            'description': func.get('description', ''),
                            'parameters': func.get('parameters', {'type': 'object', 'properties': {}})
                        }
                    }
                    langchain_tools.append(langchain_tool)
                    print(f"Converted tool: {json.dumps(langchain_tool, indent=2)}")
            except Exception as tool_error:
                print(f"Error converting tool: {str(tool_error)}")
                continue

        # Get original user query
        user_query = next(msg.content for msg in reversed(state["messages"]) 
                         if isinstance(msg, HumanMessage))
        print(f"Using original user query: {user_query}")

        # NEW: Support for multiple tool calls
        model = load_chat_model(configuration.execution_model)
        result = await model.bind_tools(
            tools=langchain_tools,
            tool_choice="auto"
        ).ainvoke(user_query)
        
        tool_results = []
        for tool_call in result.additional_kwargs.get('tool_calls', []):
            tool_name = tool_call['function']['name']
            tool_args = json.loads(tool_call['function']['arguments'])
            
            print(f"Executing tool call: {tool_name} with args: {tool_args}")
            
            tool_result = await mcp.apply(
                server_name, 
                server_config, 
                mcp.RunTool(tool_name, **tool_args)
            )
            tool_results.append(tool_result)
        
        if tool_results:
            return {
                "messages": [AIMessage(content="Multiple tools executed successfully")],
                "current_mcp_server": None,
                "tool_outputs": [str(result) for result in tool_results]
            }
        
        return {
            "messages": [AIMessage(content="No tool call was generated.")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "messages": [AIMessage(content=f"Error executing tool: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
        
        return {
            "messages": [AIMessage(content="No tool call was generated.")],
            "current_mcp_server": None,
            "tool_outputs": []
        }
        
    except Exception as e:
        print(f"Error details: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {
            "messages": [AIMessage(content=f"Error executing tool: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

def should_continue(state: GraphState) -> str:
    print("\n=== DEBUG: should_continue ===")
    print(f"Input state: {state}")
    next_node = "execute_tool" if state.get("current_mcp_server") else END
    print(f"Next node: {next_node}")
    print("=== DEBUG: should_continue end ===\n")
    return next_node

# Build and compile graph
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
workflow.add_edge("execute_tool", "route_request")
workflow.set_entry_point("route_request")

graph = workflow.compile()