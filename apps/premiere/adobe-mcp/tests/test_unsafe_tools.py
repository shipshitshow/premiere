"""Unsafe cut helpers must not be registered as MCP tools."""

from pathlib import Path

from adobe_mcp.premiere.unsafe_tools import UNREGISTERED_UNSAFE_TOOLS

SERVER = Path(__file__).resolve().parents[1] / "adobe_mcp" / "premiere" / "server.py"


def test_unsafe_names_are_not_decorated():
    src = SERVER.read_text()
    for name in UNREGISTERED_UNSAFE_TOOLS:
        assert f"def {name}(" in src, f"{name} should still exist as a function"
        assert f"@mcp.tool()\ndef {name}(" not in src, f"{name} must not be an MCP tool"


def test_canonical_list_is_complete():
    assert "set_clip_position" in UNREGISTERED_UNSAFE_TOOLS
    assert "send_keystroke" in UNREGISTERED_UNSAFE_TOOLS
    assert "remove_silence_segments" not in UNREGISTERED_UNSAFE_TOOLS
    assert len(UNREGISTERED_UNSAFE_TOOLS) == 16
