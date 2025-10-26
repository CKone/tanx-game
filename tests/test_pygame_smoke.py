import pygame
import pytest

from tanx_game import PygameTanx
from tanx_game.pygame import config


@pytest.mark.smoke
def test_pygame_client_initialises(monkeypatch, tmp_path) -> None:
    """Ensure the graphical client can boot in a headless environment."""

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(config, "_SETTINGS_PATH", tmp_path / "user_settings.json", raising=False)

    app = None
    try:
        app = PygameTanx(start_in_menu=True, debug=False)
        assert app.menu.state == "main_menu"
        assert app.logic.world.width > 0
        assert app.logic.world.height > 0
    finally:
        if app:
            app.running = False
        pygame.quit()
