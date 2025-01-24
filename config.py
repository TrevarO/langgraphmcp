import os

MCP_SERVER_CONFIG = {
    "mcpServers": {
        "filesystem": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-filesystem", "--", "."],
            "description": "File system operations",
            "env": {}
        },
        "puppeteer": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-puppeteer", "--"],
            "description": "Web browser automation",
            "env": {}
        },
        "brave-search": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-brave-search", "--"],
            "description": "Web search operations",
            "env": {"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")}
        },
        "mcp-reasoner": {
            "command": "npm.cmd" if os.name == "nt" else "npm",
            "args": ["exec", "@modelcontextprotocol/server-mcp-reasoner", "--"],
            "description": "Advanced reasoning",
            "env": {}
        }
    }
}