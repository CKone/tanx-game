import logging
import math
import os
from collections import Counter
from typing import Optional, Tuple

import pytest

from tanx_game.core.game import Game, ShotResult
from tanx_game.core.session import GameSession
from tanx_game.core.tank import Tank
from tanx_game.core.world import TerrainSettings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class AutoPlayCommander:
    """Search for deterministic firing solutions that finish a Tanx match."""

    def __init__(self, angle_step: int = 2, power_step: float = 0.05) -> None:
        self.angle_step = max(1, angle_step)
        self.power_step = max(0.01, power_step)
        self.shots_fired: Counter[str] = Counter()

    def execute_turn(
        self,
        session: GameSession,
        *,
        logger: logging.Logger,
    ) -> ShotResult:
        shooter = session.current_tank
        target = session.tanks[1 - session.current_player]
        angle, power, error = self._find_solution(session.game, shooter, target)
        self.shots_fired[shooter.name] += 1
        logger.info(
            "Selected shot for %s -> angle=%s°, power=%.2fx (estimated error %.2f)",
            shooter.name,
            angle,
            power,
            error,
        )

        shooter.turret_angle = angle
        shooter.shot_power = power

        result = session.begin_projectile(shooter)
        resolved = session.resolve_projectile(result)

        impact_desc = self._describe_result(resolved)
        logger.info(
            "Shot outcome: %s | %s HP: %s",
            impact_desc,
            target.name,
            target.hp,
        )
        logger.info("Session message: %s", session.message)
        return resolved

    def play_match(
        self,
        session: GameSession,
        *,
        logger: logging.Logger,
        max_turns: int = 14,
    ) -> Tank:
        """Automate alternating turns until a victor emerges."""

        self.shots_fired = Counter()
        for turn in range(1, max_turns + 1):
            current = session.current_tank
            logger.info(
                "---- Turn %02d: %s (HP %d, pos=%d, turret=%d, power=%.2f) ----",
                turn,
                current.name,
                current.hp,
                current.x,
                current.turret_angle,
                current.shot_power,
            )
            self.execute_turn(session, logger=logger)
            if session.winner:
                logger.info(
                    "Winner determined: %s after %d turns.",
                    session.winner.name,
                    turn,
                )
                return session.winner
            assert turn < max_turns, "Reached maximum turn budget without a victor."
        raise AssertionError("Automatic match did not produce a winner.")

    def _find_solution(
        self,
        game: Game,
        shooter: Tank,
        target: Tank,
    ) -> Tuple[int, float, float]:
        """Brute-force angles/powers to locate a shot that hits (or nearly hits)."""

        original_angle = shooter.turret_angle
        original_power = shooter.shot_power
        original_command = shooter.last_command

        best_params: Optional[Tuple[int, float]] = None
        best_error = math.inf

        angles = range(shooter.min_angle, shooter.max_angle + 1, self.angle_step)
        power_values = self._power_values(shooter)

        for angle in angles:
            shooter.turret_angle = angle
            for power in power_values:
                shooter.shot_power = power
                result = game.step_projectile(shooter, apply_effects=False)
                if result.hit_tank is target:
                    best_params = (angle, power)
                    best_error = 0.0
                    break
                error = self._estimate_error(result, target)
                if error < best_error:
                    best_params = (angle, power)
                    best_error = error
            if best_error == 0.0:
                break

        shooter.turret_angle = original_angle
        shooter.shot_power = original_power
        shooter.last_command = original_command

        if best_params is None:
            raise AssertionError("Failed to find a plausible firing solution for autoplayer.")

        return (*best_params, best_error)

    def _power_values(self, tank: Tank) -> list[float]:
        steps = int((tank.max_power - tank.min_power) / self.power_step) + 1
        values = []
        for idx in range(steps + 1):
            value = tank.min_power + self.power_step * idx
            value = max(tank.min_power, min(tank.max_power, value))
            values.append(round(value, 3))
        return sorted(set(values))

    @staticmethod
    def _estimate_error(result: ShotResult, target: Tank) -> float:
        if result.impact_x is None or result.impact_y is None:
            return math.inf
        dx = target.x - result.impact_x
        dy = target.y - result.impact_y
        return math.hypot(dx, dy)

    @staticmethod
    def _describe_result(result: Optional[ShotResult]) -> str:
        if not result:
            return "No projectile result"
        if result.hit_tank:
            tank = result.hit_tank
            return f"Direct hit on {tank.name} (fatal: {result.fatal_hit})"
        if result.hit_building:
            return "Impact against a building"
        if result.hit_rubble:
            return f"Impact against rubble segment {result.hit_rubble.id}"
        if result.impact_x is not None and result.impact_y is not None:
            return f"Impact at ({result.impact_x:.1f}, {result.impact_y:.1f})"
        return "Projectile flew out of bounds"


class MenuNavigator:
    """Drive every menu and setting exposed by the pygame client."""

    def __init__(self, logger: logging.Logger, pygame_module) -> None:
        self.logger = logger
        self.pg = pygame_module

    def exercise_main_flow(self, app) -> None:
        self._assert_menu(app, "main_menu")
        self._activate_option(app, "Start Game")
        assert app.state == "playing", "Start Game should transition into gameplay."
        self.logger.info("Gameplay launched from main menu; entering pause menu.")

        app._activate_menu("pause_menu")
        self._assert_menu(app, "pause_menu")
        self.logger.info("Pause menu options: %s", self._option_labels(app))
        self._activate_option(app, "Resume Game")
        assert app.state == "playing", "Resume Game should return to playing state."

        app._activate_menu("pause_menu")
        self._assert_menu(app, "pause_menu")
        self._activate_option(app, "Abandon Game")
        self._assert_menu(app, "main_menu")
        self.logger.info("Abandon Game returned to main menu.")

    def exercise_settings(self, app) -> None:
        self._assert_menu(app, "main_menu")
        self._activate_option(app, "Settings")
        self._assert_menu(app, "settings_menu")
        self.logger.info("Settings menu options: %s", self._option_labels(app))

        for prefix in (
            "Resolution",
            "Map Style",
            "Weather",
            "Master Volume",
            "Effects Volume",
            "Ambient Volume",
        ):
            self._activate_option(app, prefix)
            self.logger.info("Adjusted setting '%s'.", prefix)

        self._activate_option(app, "Configure Keybindings")
        self._exercise_keybindings(app)

        self._activate_option(app, "Windowed Fullscreen")
        self.logger.info("Attempted to enter windowed fullscreen mode.")

        self._activate_option(app, "Back to Start Menu")
        self._assert_menu(app, "main_menu")
        self.logger.info("Returned from settings to main menu.")

    def exercise_exit_option(self, app) -> None:
        self._assert_menu(app, "main_menu")
        self._activate_option(app, "Exit Game")
        self.logger.info("Exit Game toggled running flag to %s.", app.running)
        app.running = True
        self._assert_menu(app, "main_menu")

    def launch_game_from_main(self, app) -> None:
        self._assert_menu(app, "main_menu")
        self._activate_option(app, "Start Game")
        assert app.state == "playing", "Start Game should leave menu closed."

    def exercise_post_game(self, app) -> None:
        self._assert_menu(app, "post_game_menu")
        self.logger.info("Post game menu options: %s", self._option_labels(app))
        self._activate_option(app, "Start New Game")
        assert app.state == "playing", "Start New Game should resume gameplay."

        app._activate_menu("post_game_menu")
        self._assert_menu(app, "post_game_menu")
        self._activate_option(app, "Return to Start Menu")
        self._assert_menu(app, "main_menu")
        self.logger.info("Return to Start Menu restored the title screen.")

    # ------------------------------------------------------------------
    def _exercise_keybindings(self, app) -> None:
        self._assert_menu(app, "keybind_menu")
        self.logger.info("Keybinding menu options: %s", self._option_labels(app))
        options = list(app.menu.options)
        for option in options:
            label = option.label
            if label.startswith("Player"):
                option.action()
                assert (
                    app.keybindings.rebinding_target is not None
                ), "Rebinding target should be set after selecting a keybinding."
                player_idx, field = app.keybindings.rebinding_target
                current_key = getattr(app.keybindings.player_bindings[player_idx], field)
                key_name = self.pg.key.name(current_key).upper()
                self.logger.info(
                    "Rebinding %s (Player %d %s) using %s.",
                    label,
                    player_idx + 1,
                    field,
                    key_name,
                )
                app._finish_binding(current_key)
            elif label.startswith("Reset to Defaults"):
                option.action()
                self.logger.info("Reset key bindings to defaults.")
            elif label.startswith("Back to Settings"):
                option.action()
                self._assert_menu(app, "settings_menu")
                self.logger.info("Returned to settings menu after keybinding review.")
                return
        raise AssertionError("Keybinding menu did not provide a path back to settings.")

    def _activate_option(self, app, prefix: str):
        option = self._find_option(app, prefix)
        self.logger.info("Selecting menu option: %s", option.label)
        option.action()

    def _find_option(self, app, prefix: str):
        for option in app.menu.options:
            if option.label.startswith(prefix):
                return option
        raise AssertionError(f"Menu option starting with '{prefix}' not found in {self._option_labels(app)}")

    def _option_labels(self, app) -> list[str]:
        return [option.label for option in app.menu.options]

    def _assert_menu(self, app, expected: str) -> None:
        actual = app.menu.state
        assert (
            actual == expected
        ), f"Expected menu '{expected}' but found '{actual}'."


@pytest.mark.e2e
def test_automatic_playthrough_completes_match(monkeypatch, tmp_path) -> None:
    import pygame
    from tanx_game import PygameTanx
    from tanx_game.pygame import config

    logger = logging.getLogger("tanx.e2e")
    logger.setLevel(logging.INFO)

    monkeypatch.setattr(
        config,
        "_SETTINGS_PATH",
        tmp_path / "user_settings.json",
        raising=False,
    )

    settings = TerrainSettings(
        width=36,
        height=24,
        min_height=12.0,
        max_height=12.0,
        smoothing=0,
        detail=4,
        seed=2024,
    )

    app = None
    try:
        app = PygameTanx(
            player_one="Auto Commander Alpha",
            player_two="Auto Commander Bravo",
            terrain_settings=settings,
            seed=2024,
            start_in_menu=True,
            debug=False,
        )

        navigator = MenuNavigator(logger, pygame)
        navigator.exercise_main_flow(app)
        navigator.exercise_settings(app)
        navigator.exercise_exit_option(app)

        # Launch gameplay for the automated duel after menu validation.
        navigator.launch_game_from_main(app)

        commander = AutoPlayCommander(angle_step=2, power_step=0.05)
        _prepare_positions(app.logic, logger=logger)

        logger.info(
            "Initial positions -> %s at (x=%d, y=%d, hp=%d) | %s at (x=%d, y=%d, hp=%d)",
            app.logic.tanks[0].name,
            app.logic.tanks[0].x,
            app.logic.tanks[0].y,
            app.logic.tanks[0].hp,
            app.logic.tanks[1].name,
            app.logic.tanks[1].x,
            app.logic.tanks[1].y,
            app.logic.tanks[1].hp,
        )

        winner = commander.play_match(app.session, logger=logger)
        expected_shooters = {tank.name for tank in app.logic.tanks}
        assert set(commander.shots_fired) == expected_shooters, "Both tanks should fire during the autoplay session."
        assert all(
            commander.shots_fired[name] > 0 for name in expected_shooters
        ), "Each tank must fire at least once."
        assert winner.hp > 0, "Winner should retain positive HP."
        logger.info(
            "Autoplay duel complete -> %s won with HP %d; shot distribution %s",
            winner.name,
            winner.hp,
            dict(commander.shots_fired),
        )

        app._activate_menu("post_game_menu")
        navigator.exercise_post_game(app)
    finally:
        pygame.quit()


def _prepare_positions(game: Game, *, logger: logging.Logger) -> None:
    """Place tanks on predictable footing for deterministic duel."""

    left, right = game.tanks
    left.x = 6
    left_y = game.world.surface_y(left.x)
    if left_y is None:
        raise AssertionError("Surface height not available for left tank.")
    left.y = left_y
    left.facing = 1
    left.turret_angle = 30
    left.shot_power = 0.8

    right.x = game.world.width - 7
    right_y = game.world.surface_y(right.x)
    if right_y is None:
        raise AssertionError("Surface height not available for right tank.")
    right.y = right_y
    right.facing = -1
    right.turret_angle = 30
    right.shot_power = 0.8

    logger.info(
        "Adjusted spawn positions for flat engagement: left tank at x=%d (y=%d), right tank at x=%d (y=%d)",
        left.x,
        left.y,
        right.x,
        right.y,
    )
