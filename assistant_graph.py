from datetime import datetime, timezone
from typing import Annotated, Sequence, Dict, List, TypedDict, Any
from typing_extensions import NotRequired
import json
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
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

# Initialize prompt template at module level
prompt = ChatPromptTemplate.from_messages([
    ("system", ROUTER_SYSTEM_PROMPT),
    ("human", "{input}")
])

def convert_to_langchain_tools(mcp_tools):
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

def process_tool_result(result):
    if isinstance(result, dict):
        if 'text' in result:
            return result['text']
        if 'type' in result and result['type'] == 'text':
            return result.get('text', str(result))
    return str(result)

async def route_request(state: GraphState, config: Dict) -> Dict[str, Any]:
    try:
        print("\nDEBUG [route_request] Starting...")
        configuration = Configuration.from_runnable_config(config)
        tool_descriptions = "\n".join(
            f"- {name}: {details['description']}"
            for name, details in configuration.mcp_server_config["mcpServers"].items()
        )
        print(f"DEBUG [route_request] Available tools:\n{tool_descriptions}")
        
        model = load_chat_model(configuration.routing_model)
        messages = prompt.format_messages(
            tool_descriptions=tool_descriptions,
            input=get_message_text(state["messages"][-1]),
            system_time=datetime.now(tz=timezone.utc).isoformat()
        )
        print(f"\nDEBUG [route_request] Formatted messages: {messages}")
        
        result = await model.ainvoke(messages)
        print(f"DEBUG [route_request] Model result: {result}")
        
        tool_name = result.content.strip().lower()
        print(f"DEBUG [route_request] Selected tool: {tool_name}")
        
        return {
            "messages": [AIMessage(content=f"Using {tool_name}...")],
            "current_mcp_server": None if tool_name == "none" else tool_name,
            "tool_outputs": []
        }
    except Exception as e:
        import traceback
        print(f"DEBUG [route_request] Error: {str(e)}")
        print(f"DEBUG [route_request] Traceback: {traceback.format_exc()}")
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")], 
            "current_mcp_server": None, 
            "tool_outputs": []
        }

async def execute_tool(state: GraphState, config: Dict) -> Dict[str, Any]:
    try:
        server_name = state.get("current_mcp_server")
        original_query = next((msg.content for msg in state["messages"] 
                             if isinstance(msg, HumanMessage)), None)
        
        if not original_query:
            return {"messages": [AIMessage(content="No query found")], 
                   "current_mcp_server": None, "tool_outputs": []}

        configuration = Configuration.from_runnable_config(config)
        server_config = configuration.mcp_server_config["mcpServers"].get(server_name)
        
        if not server_config:
            return {
                "messages": [AIMessage(content=f"Tool {server_name} not found")],
                "current_mcp_server": None,
                "tool_outputs": []
            }

        # Get tools and execute query
        tools = await mcp.apply(server_name, server_config, mcp.GetTools())
        model = load_chat_model(configuration.execution_model)
        result = await model.bind_tools(convert_to_langchain_tools(tools)).ainvoke(original_query)
        
        if not result.additional_kwargs.get('tool_calls'):
            return {
                "messages": [AIMessage(content="No tool calls generated")],
                "current_mcp_server": None,
                "tool_outputs": []
            }

        # Execute tool and format response
        tool_results = []
        for tool_call in result.additional_kwargs['tool_calls']:
            tool_name = tool_call['function']['name']
            tool_args = json.loads(tool_call['function']['arguments'])
            
            tool_result = await mcp.apply(
                server_name, 
                server_config,
                mcp.RunTool(tool_name, **tool_args)
            )
            
            if isinstance(tool_result, str):
                try:
                    parsed = json.loads(tool_result)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and 'text' in item:
                                text = item['text'].replace('<strong>', '').replace('</strong>', '')
                                text = text.replace('&amp;', '&')
                                tool_results.append(text)
                except json.JSONDecodeError:
                    tool_results.append(tool_result)
            else:
                tool_results.append(str(tool_result))

        formatted_output = "\n\n".join(tool_results)
        return {
            "messages": [AIMessage(content=formatted_output)],
            "current_mcp_server": None,
            "tool_outputs": tool_results
        }

    except Exception as e:
        print(f"Error in execute_tool: {str(e)}")
        return {
            "messages": [AIMessage(content=f"Error: {str(e)}")],
            "current_mcp_server": None,
            "tool_outputs": []
        }

def should_continue(state: GraphState) -> str:
    return "execute_tool" if state.get("current_mcp_server") else END

# Modify the graph structure
workflow = StateGraph(GraphState)
workflow.add_node("route_request", route_request)
workflow.add_node("execute_tool", execute_tool)

# Simplify the edges
workflow.add_conditional_edges(
    "route_request",
    should_continue,
    {
        "execute_tool": "execute_tool",
        END: END
    }
)
# Remove the loop back - we don't want to route again
# workflow.add_edge("execute_tool", "route_request")  # Remove this line
workflow.add_edge("execute_tool", END)  # Add this instead
workflow.set_entry_point("route_request")

graph = workflow.compile()