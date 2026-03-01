from typing import Literal, Optional

from mcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import AudioPlaybackConfig, ConfigError
from .manager import AudioPlaybackManager


def _build_server(config: AudioPlaybackConfig, manager: AudioPlaybackManager) -> FastMCP:
    server = FastMCP(
        "audio-playback-server",
        host=config.http_host,
        port=config.http_port,
        streamable_http_path=config.http_path,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=config.dns_rebinding_protection,
            allowed_hosts=list(config.allowed_hosts),
        ),
    )

    @server.tool(
        name="audio_playback",
        description=(
            "Control playback of local audio files for automated testing. Audio is "
            "played via a virtual audio output device that is routed into the Android "
            "emulator's microphone. Use this to simulate a human speaking into the mic "
            "by playing prerecorded files."
        ),
    )
    async def audio_playback(
        action: Literal["play", "stop", "status", "list_files"],
        filename: Optional[str] = None,
        loop: bool = False,
        start_offset_ms: int = 0,
        list_limit: int = 200,
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
                return {"success": success, "message": message, "state": state}

            if action == "stop":
                success, message, state = await manager.stop()
                return {"success": success, "message": message, "state": state}

            if action == "status":
                success, message, state = await manager.status()
                return {"success": success, "message": message, "state": state}

            files_payload = manager.list_local_files(limit=list_limit)
            return {
                "success": True,
                "message": "Listed files available under AUDIO_ROOT_DIR.",
                "state": manager.state,
                "files": files_payload,
            }
        except ValueError as exc:
            return {"success": False, "message": str(exc), "state": manager.state}

    return server


def run() -> None:
    try:
        config = AudioPlaybackConfig.load()
        manager = AudioPlaybackManager(config)
        server = _build_server(config, manager)

        if config.transport == "http":
            server.run(transport="streamable-http")
        else:
            server.run(transport="stdio")
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}")


if __name__ == "__main__":
    run()
