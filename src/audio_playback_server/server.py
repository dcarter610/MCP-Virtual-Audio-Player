import asyncio
from typing import Literal, Optional

from mcp import Server
from mcp.server import NotificationOptions, ServerOptions
from mcp.server.models import Tool
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, Field

from .config import AudioPlaybackConfig, ConfigError
from .manager import AudioPlaybackManager

server = Server("audio-playback-server")


def _build_tool_schema() -> Tool:
    class AudioPlaybackArgs(BaseModel):
        action: Literal["play", "stop", "status"] = Field(
            description="Playback action to perform."
        )
        filename: Optional[str] = Field(
            default=None,
            description=(
                "Relative path of the audio file (under AUDIO_ROOT_DIR). Required for 'play'."
            ),
        )
        loop: bool = Field(
            default=False,
            description="If true, loop the file until 'stop' is called.",
        )
        start_offset_ms: int = Field(
            default=0,
            description=(
                "Start playback at this offset in milliseconds (0 = start of file). Optional."
            ),
            ge=0,
        )

    @server.tool(
        "audio_playback",
        description=(
            "Control playback of local audio files for automated testing. Audio is "
            "played via a virtual audio output device that is routed into the Android "
            "emulator’s microphone. Use this to simulate a human speaking into the mic "
            "by playing prerecorded files."
        ),
        args_schema=AudioPlaybackArgs,
    )
    async def audio_playback(  # type: ignore[unused-ignore]
        action: Literal["play", "stop", "status"],
        filename: Optional[str] = None,
        loop: bool = False,
        start_offset_ms: int = 0,
    ) -> dict:
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

        try:
            if action == "play":
                success, message, state = await manager.play(
                    filename=filename or "",
                    loop=loop,
                    start_offset_ms=start_offset_ms,
                )
            elif action == "stop":
                success, message, state = await manager.stop()
            else:
                success, message, state = await manager.status()
        except ValueError as exc:
            success, message, state = False, str(exc), manager.state

        return {"success": success, "message": message, "state": state}

    return audio_playback  # type: ignore[return-value]


def _load_manager() -> AudioPlaybackManager:
    config = AudioPlaybackConfig.load()
    return AudioPlaybackManager(config)


manager = _load_manager()
_build_tool_schema()


async def main() -> None:
    await server.connect(
        stdio_server(),
        options=ServerOptions(notification_options=NotificationOptions()),
    )


def run() -> None:
    try:
        asyncio.run(main())
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}")


if __name__ == "__main__":
    run()
