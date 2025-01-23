from typing import Annotated, Sequence, List, TypedDict, NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

def add_tool_outputs(old: List[str], new: List[str]) -> List[str]:
    return old + new

class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_mcp_server: NotRequired[str]
    tool_outputs: Annotated[List[str], add_tool_outputs]