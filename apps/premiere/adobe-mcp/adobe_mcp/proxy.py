"""Premiere MCP proxy server launcher."""

import os
import subprocess
import sys


def main():
    """Launch the Node.js proxy server."""
    proxy_dir = os.path.join(os.path.dirname(__file__), "..", "proxy-server")

    node_modules = os.path.join(proxy_dir, "node_modules")
    if not os.path.exists(node_modules):
        print(
            "Proxy dependencies missing. From the repo root run:\n"
            "  cd apps/premiere/adobe-mcp/proxy-server && bun install",
            file=sys.stderr,
        )
        sys.exit(1)

    # Run the proxy server
    print("Starting Premiere MCP proxy server...")
    try:
        subprocess.run(["node", "proxy.js"], cwd=proxy_dir, check=True)
    except KeyboardInterrupt:
        print("\nProxy server stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
