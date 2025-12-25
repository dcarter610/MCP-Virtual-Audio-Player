# Audio Playback MCP Server

This repository provides an MCP server named `audio-playback-server` that exposes a single `audio_playback` tool. The tool lets an MCP client start, stop, and inspect playback of local audio files routed through a configurable virtual audio output device.

## Features
- Play audio files from a configurable root directory using `ffplay`.
- Stop current playback.
- Query current status with a position estimate.
- Path safety enforcement to prevent leaving the configured root directory.

## Configuration
The server reads configuration from environment variables and an optional JSON file. Environment variables take precedence over JSON values.

Required:
- `AUDIO_ROOT_DIR`: Root directory containing allowed audio files.
- `AUDIO_OUTPUT_DEVICE`: Identifier of the virtual output device.

Optional:
- `DEFAULT_FORMAT`: File extension to append when none is provided (default `wav`).
- `FFPLAY_PATH`: Path to the `ffplay` binary (default `ffplay`).
- `AUDIO_PLAYBACK_CONFIG`: Path to a JSON config file containing any of the above keys.

An example config file is provided at `config/audio_playback_config.example.json`.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running the server (stdio)
```bash
AUDIO_ROOT_DIR=/path/to/audio \\
AUDIO_OUTPUT_DEVICE="Virtual Cable" \\
python -m audio_playback_server
```

The server listens on stdio following the MCP specification. Register the `audio_playback` tool with your MCP host using the tool schema defined in `audio_playback_server/server.py`.

## Tool schema
The `audio_playback` tool accepts the following JSON input:
- `action`: `play`, `stop`, or `status` (required)
- `filename`: Relative path under `AUDIO_ROOT_DIR` (required for `play`)
- `loop`: Loop playback until stopped (default `false`)
- `start_offset_ms`: Start offset in milliseconds (default `0`)

Responses always include `success`, `message`, and a `state` object with `status`, `current_file`, `started_at_ms`, and `position_estimate_ms`.
