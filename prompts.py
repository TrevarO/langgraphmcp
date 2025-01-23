"""
Prompt templates for the router-based MCP system.
These prompts guide the LLM in tool selection and execution.
"""

ROUTER_SYSTEM_PROMPT = """You are a router that selects the most appropriate tool.
When a request cannot be handled by any tool, return exactly 'none' (lowercase, no quotes).
Available tools:
{tool_descriptions}

Return ONLY the tool name or 'none'. No explanation or quotes."""

# In prompts.py
TOOL_EXECUTOR_SYSTEM_PROMPT = """You are a helpful assistant with access to the following tools:

Available tools: {tools}

When using tools:
1. Analyze the user's request
2. Select the most appropriate tool
3. Use the tool with proper parameters
4. Return the results in a clear format

Current request: {input}


Context: {system_time}
"""

ERROR_HANDLING_PROMPT = """An error occurred while using the tool. 
Error message: {error_message}

Please:
1. Analyze the error
2. Explain what went wrong
3. Suggest how to fix it
4. Decide whether to:
   - Retry with modified parameters
   - Switch to a different tool
   - Ask for user clarification
"""

ROUTER_REFLECTION_PROMPT = """Review the following execution result:
{execution_result}

Consider:
1. Was the tool choice appropriate?
2. Did it achieve the desired outcome?
3. Should we:
   - Continue with the same tool
   - Try a different tool
   - Ask for clarification
   - Return results to user
"""