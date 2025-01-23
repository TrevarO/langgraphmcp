"""
Utility functions for the LangGraph MCP system.
"""
import os
from typing import List, Sequence

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

def get_message_text(message: BaseMessage) -> str:
    """Extract text content from a message.
    
    Args:
        message: The message to extract text from
        
    Returns:
        The text content of the message
    """
    if isinstance(message, HumanMessage):
        return message.content
    return str(message.content)

def format_docs(docs: Sequence[Document]) -> str:
    """Format a sequence of documents into a string.
    
    Args:
        docs: Sequence of documents to format
        
    Returns:
        Formatted string representation
    """
    return "\n\n".join(doc.page_content for doc in docs)

def load_chat_model(model_string: str) -> ChatOpenAI:
    """Load a chat model based on a model string.
    
    Args:
        model_string: String identifying the model (e.g., "openai/gpt-4")
        
    Returns:
        Configured chat model instance
    """
    provider, model = model_string.split("/")
    
    if provider == "openai":
        return ChatOpenAI(
            model=model,
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    else:
        raise ValueError(f"Unsupported model provider: {provider}")