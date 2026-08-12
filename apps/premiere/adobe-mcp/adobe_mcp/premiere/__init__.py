"""Adobe Premiere Pro MCP Server."""


def main():
    """Entry point for Premiere MCP server."""
    from .server import mcp

    mcp.run(transport="stdio")


__all__ = ["main"]
