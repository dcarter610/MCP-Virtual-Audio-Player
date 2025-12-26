import anyio

from mcp import Tool
from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, ToolsCapability

from .config import AudioPlaybackConfig, ConfigError
from .manager import AudioPlaybackManager

server = Server("audio-playback-server")


def _load_manager() -> AudioPlaybackManager:
    config = AudioPlaybackConfig.load()
    return AudioPlaybackManager(config)


manager = _load_manager()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="audio_playback",
            description=(
                "Control playback of local audio files for automated testing. Audio is "
                "played via a virtual audio output device that is routed into the Android "
                "emulator's microphone. Use this to simulate a human speaking into the mic "
                "by playing prerecorded files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play", "stop", "status"],
                        "description": "Playback action to perform.",
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Relative path of the audio file (under AUDIO_ROOT_DIR). "
                            "Required for 'play'."
                        ),
                    },
                    "loop": {
                        "type": "boolean",
                        "description": "If true, loop the file until 'stop' is called.",
                        "default": False,
                    },
                    "start_offset_ms": {
                        "type": "integer",
                        "description": (
                            "Start playback at this offset in milliseconds (0 = start of file). "
                            "Optional."
                        ),
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["action"],
            },
        )
    ]


@server.call_tool()
async def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """Handle tool calls."""
    if tool_name != "audio_playback":
        raise ValueError(f"Unknown tool: {tool_name}")

    # Parse arguments
    action = arguments.get("action")
    filename = arguments.get("filename")
    loop = arguments.get("loop", False)
    start_offset_ms = arguments.get("start_offset_ms", 0)

    # Validate action
    if action not in ["play", "stop", "status"]:
        raise ValueError(f"Invalid action: {action}")

    # Validate play action
    if action == "play" and (filename is None or not filename.strip()):
        return {
            "success": False,
            "message": "filename is required for 'play' action.",
            "state": manager.state,
        }

    if start_offset_ms < 0:
        return {
            "success": False,
            "message": "start_offset_ms must be non-negative.",
            "state": manager.state,
        }

    # Execute action
    try:
        if action == "play":
            success, message, state = await manager.play(
                filename=filename or "",
                loop=loop,
                start_offset_ms=start_offset_ms,
            )
        elif action == "stop":
            success, message, state = await manager.stop()
        else:  # status
            success, message, state = await manager.status()
    except ValueError as exc:
        success, message, state = False, str(exc), manager.state

    return {"success": success, "message": message, "state": state}


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="audio-playback-server",
            server_version="0.1.0",
            capabilities=ServerCapabilities(
                tools=ToolsCapability(),
            ),
        )
        await server.run(
            read_stream,
            write_stream,
            init_options,
        )


def run() -> None:
    try:
        anyio.run(main)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}")


if __name__ == "__main__":
    run()
