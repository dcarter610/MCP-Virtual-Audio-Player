import asyncio
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

from .config import AudioPlaybackConfig

PlaybackStatus = Literal["idle", "playing", "stopped", "error"]


@dataclass
class PlaybackState:
    status: PlaybackStatus = "idle"
    current_file: Optional[str] = None
    started_at_ms: Optional[int] = None
    start_offset_ms: int = 0

    def to_response(self) -> Dict[str, int | str | None]:
        return {
            "status": self.status,
            "current_file": self.current_file,
            "started_at_ms": self.started_at_ms,
            "position_estimate_ms": self._position_estimate(),
        }

    def _position_estimate(self) -> Optional[int]:
        if self.status != "playing" or self.started_at_ms is None:
            return None
        now_ms = int(time.time() * 1000)
        elapsed = now_ms - self.started_at_ms
        if elapsed < 0:
            return self.start_offset_ms
        return self.start_offset_ms + elapsed


class AudioPlaybackManager:
    def __init__(self, config: AudioPlaybackConfig) -> None:
        self.config = config
        self._state = PlaybackState()
        self._process: Optional[subprocess.Popen] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> Dict[str, int | str | None]:
        return self._state.to_response()

    async def play(
        self, filename: str, loop: bool = False, start_offset_ms: int = 0
    ) -> Tuple[bool, str, Dict[str, Optional[int | str | float]]]:
        async with self._lock:
            normalized_relative, resolved_path = self._normalize_filename(filename)
            if not resolved_path.exists():
                self._state = PlaybackState(status="idle")
                return (
                    False,
                    f"File '{normalized_relative}' not found under AUDIO_ROOT_DIR.",
                    self._state.to_response(),
                )

            # Get audio file duration
            duration_seconds = await self._get_audio_duration(resolved_path)

            await self._stop_process()

            command = self._build_ffplay_command(resolved_path, loop, start_offset_ms)

            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                self._state = PlaybackState(status="error")
                return (
                    False,
                    f"ffplay not found at '{self.config.ffplay_path}'.",
                    self._state.to_response(),
                )
            except Exception as exc:
                self._state = PlaybackState(status="error")
                return (
                    False,
                    f"Failed to start playback: {exc}",
                    self._state.to_response(),
                )

            self._process = process
            started_at_ms = int(time.time() * 1000)
            self._state = PlaybackState(
                status="playing",
                current_file=normalized_relative,
                started_at_ms=started_at_ms,
                start_offset_ms=start_offset_ms,
            )
            self._monitor_task = asyncio.create_task(self._monitor_process(process))
            message = (
                f"Playing '{normalized_relative}' from {start_offset_ms} ms."
            )
            if loop:
                message += " Looping until stopped."
            
            if duration_seconds is not None:
                message += f" Duration: {duration_seconds:.2f} seconds."

            response = self._state.to_response()
            if duration_seconds is not None:
                response["duration_seconds"] = duration_seconds

            return True, message, response

    async def stop(self) -> Tuple[bool, str, Dict[str, Optional[int | str]]]:
        async with self._lock:
            if not self._process:
                self._state = PlaybackState(status="stopped")
                return True, "No playback to stop.", self._state.to_response()

            await self._stop_process()
            self._state = PlaybackState(status="stopped")
            return True, "Playback stopped.", self._state.to_response()

    async def status(self) -> Tuple[bool, str, Dict[str, Optional[int | str]]]:
        async with self._lock:
            state_copy = self._state
            message = "Currently playing." if state_copy.status == "playing" else "Idle."
            if state_copy.status == "stopped":
                message = "Playback stopped."
            elif state_copy.status == "error":
                message = "Playback error encountered."
            return True, message, state_copy.to_response()

    async def _stop_process(self) -> None:
        if not self._process:
            return

        process = self._process
        process.terminate()
        try:
            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await asyncio.to_thread(process.wait)
        finally:
            self._process = None
            if self._monitor_task:
                self._monitor_task.cancel()
                self._monitor_task = None

    async def _monitor_process(self, process: subprocess.Popen) -> None:
        try:
            await asyncio.to_thread(process.wait)
        finally:
            async with self._lock:
                if self._process is process:
                    self._process = None
                    if self._state.status == "playing":
                        self._state = PlaybackState(status="stopped")

    def _normalize_filename(self, filename: str) -> Tuple[str, Path]:
        if not filename or not filename.strip():
            raise ValueError("Filename is required for playback.")

        relative_path = Path(filename.strip())
        if relative_path.is_absolute():
            raise ValueError("Filename must be a relative path under AUDIO_ROOT_DIR.")

        if not relative_path.suffix:
            relative_path = relative_path.with_suffix(f".{self.config.default_format}")

        normalized_relative = relative_path.as_posix()
        resolved = (self.config.root_dir / relative_path).resolve()
        root_resolved = self.config.root_dir.resolve()

        if root_resolved not in resolved.parents and resolved != root_resolved:
            raise ValueError("Filename must remain inside AUDIO_ROOT_DIR.")

        return normalized_relative, resolved

    async def _get_audio_duration(self, file_path: Path) -> Optional[float]:
        """Get the duration of an audio file in seconds using ffprobe."""
        # Determine ffprobe path (usually in the same directory as ffplay)
        ffplay_path = Path(self.config.ffplay_path)
        if ffplay_path.is_absolute():
            # If ffplay is an absolute path, try to find ffprobe in the same directory
            ffprobe_path = ffplay_path.parent / "ffprobe"
            if platform.system() == "Windows":
                ffprobe_path = ffprobe_path.with_suffix(".exe")
        else:
            # If ffplay is just a command name, assume ffprobe is also available
            ffprobe_path = "ffprobe"
            if platform.system() == "Windows":
                ffprobe_path = "ffprobe.exe"

        command = [
            str(ffprobe_path),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return duration
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired) as exc:
            # If ffprobe is not available or fails, we'll just continue without duration
            # This is not a critical error - playback can still work
            pass
        except Exception:
            # Silently ignore other errors - duration is optional
            pass

        return None

    def _build_ffplay_command(
        self, file_path: Path, loop: bool, start_offset_ms: int
    ) -> list[str]:
        command = [
            self.config.ffplay_path,
            "-nodisp",
            "-autoexit",
            "-vn",
            "-loglevel",
            "error",
        ]

        if start_offset_ms > 0:
            command.extend(["-ss", f"{start_offset_ms / 1000:.3f}"])

        if loop:
            command.extend(["-loop", "0"])

        # On Windows, ffplay doesn't support -device for output selection like ALSA on Linux.
        # We'll play the file normally and it will use the Windows default audio device.
        # On Linux/ALSA, use -device flag for output device selection.
        if platform.system() == "Windows":
            # Just play the file - Windows will route to default device
            command.extend(["-i", str(file_path)])
        else:
            # Linux/ALSA: use -device for output device
            if not self.config.output_device:
                raise ValueError("AUDIO_OUTPUT_DEVICE is required on non-Windows systems.")
            command.extend(["-device", self.config.output_device])
            command.extend(["-i", str(file_path)])

        return command
