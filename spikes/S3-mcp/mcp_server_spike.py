"""
S3 spike: MCP server exposing get_time() tool, to verify opencode can load
and call custom MCP tools via stdio transport.
"""
import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WeAt-spike-S3")


@mcp.tool()
def get_time() -> str:
    """Return current date and time in ISO 8601 format."""
    return datetime.datetime.now().isoformat()


if __name__ == "__main__":
    mcp.run(transport="stdio")
