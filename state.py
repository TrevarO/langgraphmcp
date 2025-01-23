"""Basic state management for the MCP system."""
from typing import Annotated, Sequence, List, TypedDict, NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

def add_mcp_outputs(existing: List[str], new: List[str]) -> List[str]:
    """Combines existing and new MCP outputs."""
    return existing + new

class GraphState(TypedDict):
    """State type for the graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]  
    current_mcp_server: NotRequired[str]
    tool_outputs: Annotated[List[str], add_mcp_outputs] = []  # Notice the annotation
    error_messages: Annotated[List[str], add_mcp_outputs] = []