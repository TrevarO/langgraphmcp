"""
Retriever implementation for MCP server selection.
"""
from contextlib import contextmanager
from typing import Generator, Optional

from langchain_community.vectorstores import Milvus
from langchain_core.runnables import RunnableConfig
from langchain_openai import OpenAIEmbeddings

from langgraph_mcp.configuration import Configuration

@contextmanager
def make_retriever(config: Optional[RunnableConfig] = None) -> Generator:
    """Create a retriever instance based on configuration.
    
    Args:
        config: Optional configuration object
        
    Returns:
        A retriever instance
    """
    configuration = Configuration.from_runnable_config(config)
    
    if configuration.retriever_provider == "milvus":
        connection_args = {"host": "localhost", "port": "19530"}
        embeddings = OpenAIEmbeddings()
        
        db = Milvus(
            embedding_function=embeddings,
            collection_name="mcp_servers",
            connection_args=connection_args,
        )
        
        yield db.as_retriever(
            search_kwargs={"k": 3}  # Return top 3 most relevant servers
        )
    else:
        raise ValueError(f"Unsupported retriever provider: {configuration.retriever_provider}")