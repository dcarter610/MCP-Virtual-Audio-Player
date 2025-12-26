from dataclasses import dataclass
from pathlib import Path
import json
import os
import platform
from typing import Any, Dict, Optional


CONFIG_ENV_VAR = "AUDIO_PLAYBACK_CONFIG"


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class AudioPlaybackConfig:
    root_dir: Path
    output_device: Optional[str] = None
    default_format: str = "wav"
    ffplay_path: str = "ffplay"

    @classmethod
    def load(cls, base_dir: Optional[Path] = None) -> "AudioPlaybackConfig":
        """Load configuration from environment variables and optional JSON.

        Environment variables take precedence. If ``AUDIO_PLAYBACK_CONFIG`` points to a
        JSON file, the file is read for defaults. If the variable is not set, a
        ``audio_playback_config.json`` file alongside the project root is used when
        present.
        """

        base = base_dir or Path(__file__).resolve().parent.parent.parent
        json_data: Dict[str, Any] = {}

        config_path_env = os.environ.get(CONFIG_ENV_VAR)
        candidate_paths = []
        if config_path_env:
            candidate_paths.append(Path(config_path_env))

        # Try project root config first, then src/config as fallback
        default_json = base / "config" / "audio_playback_config.json"
        if default_json.exists():
            candidate_paths.append(default_json)
        
        # Fallback to src/config if project root doesn't exist
        src_config_json = base / "src" / "config" / "audio_playback_config.json"
        if src_config_json.exists():
            candidate_paths.append(src_config_json)

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

        root_dir_value = get_value("AUDIO_ROOT_DIR")
        if not root_dir_value:
            raise ConfigError("AUDIO_ROOT_DIR is required.")

        # On Windows, output device is optional (uses default)
        # On Linux/ALSA, output device is required
        output_device = get_value("AUDIO_OUTPUT_DEVICE")
        if platform.system() != "Windows" and not output_device:
            raise ConfigError("AUDIO_OUTPUT_DEVICE is required on non-Windows systems.")

        default_format = get_value("DEFAULT_FORMAT", "wav") or "wav"
        ffplay_path = get_value("FFPLAY_PATH", "ffplay") or "ffplay"

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
        )
