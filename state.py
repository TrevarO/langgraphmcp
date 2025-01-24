from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_core.messages import BaseMessage

class GraphState(BaseModel):
    messages: List[BaseMessage] = Field(default_factory=list)
    current_mcp_server: Optional[str] = None
    tool_outputs: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def validate_state(self) -> bool:
        """Validate the current state"""
        if not self.messages:
            raise ValueError("State must contain at least one message")
        if self.current_mcp_server and not isinstance(self.current_mcp_server, str):
            raise ValueError("current_mcp_server must be a string or None")
        return True