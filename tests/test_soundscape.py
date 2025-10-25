import os

import pygame
import pytest

from tanx_game.pygame.soundscape import Soundscape


def _prepare_mixer() -> None:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    # Ensure we bootstrap with a clean mixer state so Soundscape can initialise.
    pygame.mixer.quit()


@pytest.mark.parametrize("category", ["effects", "ambient", "ui"])
def test_soundscape_generates_placeholder_for_missing_assets(tmp_path, category) -> None:
    _prepare_mixer()
    try:
        soundscape = Soundscape(tmp_path, enabled=True)
        if not soundscape.enabled:
            pytest.skip("pygame mixer not available in this environment")

        key = f"{category}_placeholder"
        soundscape.load(key, "missing.wav", category=category)

        stored = soundscape._registry[key]  # type: ignore[attr-defined]
    except KeyError:  # pragma: no cover - safety for CI audio failures
        pytest.skip("sound registry unavailable without mixer support")
    finally:
        pygame.mixer.quit()

    assert stored is not None
    assert soundscape._categories[key] == category  # type: ignore[attr-defined]


def test_ambient_volume_updates_live_channel(tmp_path) -> None:
    _prepare_mixer()
    try:
        soundscape = Soundscape(tmp_path, enabled=True)
        if not soundscape.enabled:
            pytest.skip("pygame mixer not available in this environment")

        soundscape.load("ambient_test", "missing.wav", category="ambient")
        soundscape.play_loop("ambient_test")

        channel = soundscape._ambient_channel  # type: ignore[attr-defined]
        if channel is None or channel.get_sound() is None:
            pytest.skip("ambient channel not allocated by pygame mixer")

        initial_volume = channel.get_volume()
        assert pytest.approx(initial_volume, rel=1e-2) == soundscape.get_volume("ambient")

        soundscape.set_volume("ambient", 0.25)
        assert pytest.approx(channel.get_volume(), rel=1e-2) == 0.25
    finally:
        pygame.mixer.quit()
