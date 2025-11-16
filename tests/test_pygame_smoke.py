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


@pytest.mark.smoke
def test_play_vs_computer_menu_option(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(config, "_SETTINGS_PATH", tmp_path / "user_settings.json", raising=False)

    app = None
    try:
        app = PygameTanx(start_in_menu=True, debug=False)
        assert any(
            option.label.startswith("Play vs Computer") for option in app.menu.options
        ), "Menu should list the computer opponent option"
        for option in app.menu.options:
            if option.label.startswith("Play vs Computer"):
                option.action()
                break
        assert app.state == "playing"
        assert app.ai_opponent_active
        assert app.is_ai_controlled(1)
        assert "CPU" in app.player_names[1]
    finally:
        if app:
            app.running = False
        pygame.quit()


@pytest.mark.smoke
def test_damage_settings_adjustment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(config, "_SETTINGS_PATH", tmp_path / "user_settings.json", raising=False)

    app = None
    try:
        app = PygameTanx(start_in_menu=True, debug=False)
        app._activate_menu("settings_menu")
        base_direct = app._damage_settings["direct"]
        base_splash = app._damage_settings["splash"]
        app._adjust_damage("direct", 1)
        assert app._damage_settings["direct"] == base_direct + app._damage_step
        assert app.logic.damage == app._damage_settings["direct"]
        app._adjust_damage("splash", -1)
        assert app._damage_settings["splash"] == max(
            app._damage_ranges["splash"][0], base_splash - app._damage_step
        )
        assert app.logic.splash_damage == app._damage_settings["splash"]
        labels = [option.label for option in app.menu.options]
        assert any(label.startswith("Direct Hit Damage") for label in labels)
        assert any(label.startswith("Splash Damage") for label in labels)
    finally:
        if app:
            app.running = False
        pygame.quit()
