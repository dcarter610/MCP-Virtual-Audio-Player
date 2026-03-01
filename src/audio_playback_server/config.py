from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Any, Dict, Optional


CONFIG_ENV_VAR = "AUDIO_PLAYBACK_CONFIG"


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class AudioPlaybackConfig:
    root_dir: Path
    output_device: str
    default_format: str = "wav"
    ffplay_path: str = "ffplay"
    transport: str = "stdio"
    http_host: str = "0.0.0.0"
    http_port: int = 8765
    http_path: str = "/mcp"
    dns_rebinding_protection: bool = True
    allowed_hosts: tuple[str, ...] = ()

    @classmethod
    def load(cls, base_dir: Optional[Path] = None) -> "AudioPlaybackConfig":
        """Load configuration from environment variables and optional JSON.

        Environment variables take precedence. If ``AUDIO_PLAYBACK_CONFIG`` points to a
        JSON file, the file is read for defaults. If the variable is not set, a
        ``audio_playback_config.json`` file alongside the project root is used when
        present.
        """

        base = base_dir or Path(__file__).resolve().parent.parent
        json_data: Dict[str, Any] = {}

        config_path_env = os.environ.get(CONFIG_ENV_VAR)
        candidate_paths = []
        if config_path_env:
            candidate_paths.append(Path(config_path_env))

        default_json = base / "config" / "audio_playback_config.json"
        if default_json.exists():
            candidate_paths.append(default_json)

        for candidate in candidate_paths:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as config_file:
                    json_data = json.load(config_file)
                break

        def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
            env_value = os.environ.get(key)
            if env_value:
                return env_value
            json_value = json_data.get(key)
            if isinstance(json_value, str) and json_value.strip():
                return json_value
            return default

        def get_bool_value(key: str, default: bool) -> bool:
            env_value = os.environ.get(key)
            if env_value is not None:
                normalized = env_value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
                raise ConfigError(f"{key} must be a boolean value.")

            json_value = json_data.get(key)
            if isinstance(json_value, bool):
                return json_value
            if isinstance(json_value, str):
                normalized = json_value.strip().lower()
                if normalized in {"1", "true", "yes", "on"}:
                    return True
                if normalized in {"0", "false", "no", "off"}:
                    return False
            return default

        root_dir_value = get_value("AUDIO_ROOT_DIR")
        if not root_dir_value:
            raise ConfigError("AUDIO_ROOT_DIR is required.")

        output_device = get_value("AUDIO_OUTPUT_DEVICE")
        if not output_device:
            raise ConfigError("AUDIO_OUTPUT_DEVICE is required.")

        default_format = get_value("DEFAULT_FORMAT", "wav") or "wav"
        ffplay_path = get_value("FFPLAY_PATH", "ffplay") or "ffplay"

        transport = (get_value("MCP_TRANSPORT", "stdio") or "stdio").strip().lower()
        if transport not in {"stdio", "http"}:
            raise ConfigError("MCP_TRANSPORT must be either 'stdio' or 'http'.")

        http_host = get_value("MCP_HTTP_HOST", "0.0.0.0") or "0.0.0.0"

        http_port_raw = get_value("MCP_HTTP_PORT", "8765") or "8765"
        try:
            http_port = int(http_port_raw)
        except ValueError as exc:
            raise ConfigError("MCP_HTTP_PORT must be an integer.") from exc
        if not (1 <= http_port <= 65535):
            raise ConfigError("MCP_HTTP_PORT must be between 1 and 65535.")

        http_path = get_value("MCP_HTTP_PATH", "/mcp") or "/mcp"
        http_path = http_path.strip()
        if not http_path.startswith("/"):
            http_path = f"/{http_path}"

        dns_rebinding_protection = get_bool_value("MCP_DNS_REBINDING_PROTECTION", True)

        allowed_hosts_raw = get_value("MCP_ALLOWED_HOSTS", "") or ""
        allowed_hosts = tuple(
            host.strip() for host in allowed_hosts_raw.split(",") if host.strip()
        )

        root_path = Path(root_dir_value).expanduser().resolve()
        if not root_path.exists():
            raise ConfigError(f"AUDIO_ROOT_DIR '{root_path}' does not exist.")
        if not root_path.is_dir():
            raise ConfigError(f"AUDIO_ROOT_DIR '{root_path}' is not a directory.")

        return cls(
            root_dir=root_path,
            output_device=output_device,
            default_format=default_format,
            ffplay_path=ffplay_path,
            transport=transport,
            http_host=http_host,
            http_port=http_port,
            http_path=http_path,
            dns_rebinding_protection=dns_rebinding_protection,
            allowed_hosts=allowed_hosts,
        )
