"""Tap sound player for TinyHand Linux. Plays WAV files non-blocking."""
import subprocess
from pathlib import Path
from threading import Thread
from typing import Optional

from . import paths
from . import prefs


# Mapping from pointer style ID to sound choice.
# Based on available sound files: tap_blip.wav, tap_boop.wav, tap_chirp.wav,
# tap_clack.wav, tap_click.wav, tap_coin.wav, tap_pew.wav, tap_pop.wav,
# tap_quack.wav, tap_snap.wav, tap_squeak.wav, tap_thock.wav, tap_tock.wav,
# tap_typewriter.wav, tap_wood.wav
STYLE_TO_SOUND: dict[str, str] = {
    "wood": "wood",
    "click": "click",
    "clack": "clack",
    "pop": "pop",
    "snap": "snap",
    "blip": "blip",
    "boop": "boop",
    "chirp": "chirp",
    "coin": "coin",
    "pew": "pew",
    "quack": "quack",
    "squeak": "squeak",
    "thock": "thock",
    "tock": "tock",
    "typewriter": "typewriter",
}


class TapSound:
    """Plays tap sounds non-blocking using pw-play, paplay, or aplay."""

    _enabled: bool = True
    _sound_players: list[str] = ["pw-play", "paplay", "aplay"]

    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        """Enable or disable tap sounds."""
        cls._enabled = enabled

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if tap sounds are enabled."""
        return cls._enabled and prefs.Prefs().hand_sound

    @classmethod
    def play(cls, pointer_style_id: Optional[str] = None) -> None:
        """Play the tap sound for the given pointer style, or the default."""
        if not cls.is_enabled():
            return

        # Determine which sound to play
        sound_name: str
        if pointer_style_id:
            # Try to find a direct mapping
            sound_name = STYLE_TO_SOUND.get(pointer_style_id, "thock")
        else:
            # Use the preference
            sound_name = prefs.Prefs().tap_sound

        # Play the sound file non-blocking
        sound_file = paths.SOUNDS_DIR / f"tap_{sound_name}.wav"
        if not sound_file.exists():
            return

        # Try each player in order
        cmd = None
        for player in cls._sound_players:
            if _which(player):
                cmd = [player, str(sound_file)]
                break

        if cmd is None:
            return

        # Start the player in a background thread to avoid blocking
        def play_in_thread():
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

        thread = Thread(target=play_in_thread, daemon=True)
        thread.start()


def _which(executable: str) -> bool:
    """Check if an executable is available in PATH."""
    import shutil
    return shutil.which(executable) is not None


if __name__ == "__main__":
    # Self-test: exercise core logic
    paths.ensure_dirs()

    # Check that sound files exist
    sound_files = list(paths.SOUNDS_DIR.glob("tap_*.wav"))
    print(f"Found {len(sound_files)} sound files in {paths.SOUNDS_DIR}")

    # Test play with a known sound
    TapSound.set_enabled(True)
    TapSound.play("wood")  # Should play tap_wood.wav if available

    # Test disabled
    TapSound.set_enabled(False)
    TapSound.play("wood")  # Should not play

    # Test with no style (uses preference)
    TapSound.set_enabled(True)
    TapSound.play(None)

    # Test with unknown style (should fall back to default)
    TapSound.play("nonexistent_style")

    print("tapsound.py self-test passed")
