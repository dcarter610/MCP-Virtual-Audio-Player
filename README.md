# Audio Playback MCP Server

This repository provides an MCP server named `audio-playback-server` that exposes a single `audio_playback` tool. The tool lets an MCP client start, stop, and inspect playback of local audio files routed through a configurable virtual audio output device.

## Features
- Play audio files from a configurable root directory using `ffplay`.
- Stop current playback.
- Query current status with a position estimate.
- List audio files hosted locally under `AUDIO_ROOT_DIR`.
- Path safety enforcement to prevent leaving the configured root directory.
- Run as either a local stdio MCP server or a long-running HTTP MCP server.

## Configuration
The server reads configuration from environment variables and an optional JSON file. Environment variables take precedence over JSON values.

Required:
- `AUDIO_ROOT_DIR`: Root directory containing allowed audio files.
- `AUDIO_OUTPUT_DEVICE`: Identifier of the virtual output device.

Optional playback settings:
- `DEFAULT_FORMAT`: File extension to append when none is provided (default `wav`).
- `FFPLAY_PATH`: Path to the `ffplay` binary (default `ffplay`).
- `AUDIO_PLAYBACK_CONFIG`: Path to a JSON config file containing any of the above keys.

Optional MCP transport settings:
- `MCP_TRANSPORT`: `stdio` (default) or `http`.
- `MCP_HTTP_HOST`: HTTP bind host for `http` transport (default `0.0.0.0`).
- `MCP_HTTP_PORT`: HTTP bind port for `http` transport (default `8765`).
- `MCP_HTTP_PATH`: MCP endpoint path for `http` transport (default `/mcp`).
- `MCP_DNS_REBINDING_PROTECTION`: `true`/`false` (default `true`).
- `MCP_ALLOWED_HOSTS`: Comma-separated allow-list of host headers for HTTP mode.

An example config file is provided at `config/audio_playback_config.example.json`.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running the server (stdio)
```bash
AUDIO_ROOT_DIR=/path/to/audio \
AUDIO_OUTPUT_DEVICE="Virtual Cable" \
python -m audio_playback_server
```

## Running the server (HTTP, for remote clients)
```bash
AUDIO_ROOT_DIR=/path/to/audio \
AUDIO_OUTPUT_DEVICE="Virtual Cable" \
MCP_TRANSPORT=http \
MCP_HTTP_HOST=0.0.0.0 \
MCP_HTTP_PORT=8765 \
MCP_HTTP_PATH=/mcp \
python -m audio_playback_server
```

In HTTP mode, the server stays running and accepts MCP requests at `http://<host>:<port><path>` (for example `http://192.168.1.10:8765/mcp`).

### Remote access notes (Windows host + Raspberry Pi client)
1. Bind to `0.0.0.0` so the server listens on your LAN interface.
2. Allow inbound TCP on `MCP_HTTP_PORT` in Windows Defender Firewall.
3. If MCP host-header checks block requests, set `MCP_ALLOWED_HOSTS` to include the hostname/IP your client uses, or disable checks with `MCP_DNS_REBINDING_PROTECTION=false` for trusted networks only.
4. Configure your Raspberry Pi MCP client/Openclaw to call your Windows machine at `http://<windows-lan-ip>:8765/mcp`.

## Tool schema
The `audio_playback` tool accepts the following JSON input:
- `action`: `play`, `stop`, `status`, or `list_files` (required)
- `filename`: Relative path under `AUDIO_ROOT_DIR` (required for `play`)
- `loop`: Loop playback until stopped (default `false`)
- `start_offset_ms`: Start offset in milliseconds (default `0`)
- `list_limit`: Maximum number of files returned when `action=list_files` (default `200`)

Responses always include `success`, `message`, and a `state` object with `status`, `current_file`, `started_at_ms`, and `position_estimate_ms`. For `list_files`, responses also include a `files` payload containing `root_dir`, `count`, `limit`, and `files` entries (`filename`, `size_bytes`).
