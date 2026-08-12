"""Unsafe cut helpers must not be registered as MCP tools."""

from pathlib import Path

from adobe_mcp.premiere.unsafe_tools import (
    UNREGISTERED_SEQUENCE_TOOLS,
    UNREGISTERED_UNSAFE_TOOLS,
)

PREMIERE = Path(__file__).resolve().parents[1] / "adobe_mcp" / "premiere"
SERVER = PREMIERE / "server.py"
TOOLS = PREMIERE / "tools.py"


def test_unsafe_names_are_not_decorated():
    src = SERVER.read_text()
    for name in UNREGISTERED_UNSAFE_TOOLS:
        assert f"def {name}(" in src, f"{name} should still exist as a function"
        assert f"@mcp.tool()\ndef {name}(" not in src, f"{name} must not be an MCP tool"


def test_sequence_creators_are_not_registered():
    blob = SERVER.read_text() + TOOLS.read_text()
    assert "def create_sequence_from_media(" in blob
    assert "@mcp.tool()\ndef create_sequence_from_media(" not in blob
    assert "def premiere_create_sequence(" not in blob
    assert "def premiere_create_subsequence(" not in blob
    for name in UNREGISTERED_SEQUENCE_TOOLS:
        assert f"@mcp.tool()\ndef {name}(" not in blob


def test_canonical_list_is_complete():
    assert "set_clip_position" in UNREGISTERED_UNSAFE_TOOLS
    assert "send_keystroke" in UNREGISTERED_UNSAFE_TOOLS
    assert "remove_silence_segments" not in UNREGISTERED_UNSAFE_TOOLS
    assert len(UNREGISTERED_UNSAFE_TOOLS) == 16
    assert "create_sequence_from_media" in UNREGISTERED_SEQUENCE_TOOLS
    assert len(UNREGISTERED_SEQUENCE_TOOLS) == 3
