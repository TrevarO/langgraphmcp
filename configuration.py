"""Configuration for the router-based MCP system."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated, Any, Optional, Type, TypeVar
from langchain_core.runnables import RunnableConfig, ensure_config

from langgraph_mcp import prompts

@dataclass(kw_only=True)
class Configuration:
    """Configuration class for MCP routing operations."""

    mcp_server_config: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "MCP server configurations."},
    )

    routing_model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="gpt-4-0125-preview",
        metadata={
            "description": "The language model used for router decisions."
        },
    )

    execution_model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="gpt-4-0125-preview",
        metadata={
            "description": "The language model used for tool execution."
        },
    )

    router_system_prompt: str = field(
        default=prompts.ROUTER_SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt used for routing decisions."
        },
    )

    executor_system_prompt: str = field(
        default=prompts.TOOL_EXECUTOR_SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt used for tool execution."
        },
    )

    error_handling_prompt: str = field(
        default=prompts.ERROR_HANDLING_PROMPT,
        metadata={
            "description": "The prompt used for handling tool execution errors."
        },
    )

    reflection_prompt: str = field(
        default=prompts.ROUTER_REFLECTION_PROMPT,
        metadata={
            "description": "The prompt used for post-execution reflection."
        },
    )

    @classmethod
    def from_runnable_config(
        cls: Type[T], config: Optional[RunnableConfig] = None
    ) -> T:
        """Create a Configuration instance from a RunnableConfig object."""
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})
    
    def get_mcp_server_descriptions(self) -> list[tuple[str, str]]:
        """Get a list of descriptions of the MCP servers."""
        return [
            (server_name, server_config['description']) 
            for server_name, server_config in self.mcp_server_config["mcpServers"].items()
        ]

T = TypeVar("T", bound=Configuration)