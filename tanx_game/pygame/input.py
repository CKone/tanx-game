"""Input handling for the pygame client."""

from __future__ import annotations

import pygame

from ..core.tank import Tank
from .keybindings import KeyBindings


class InputHandler:
    """Translate pygame events into application actions."""

    def __init__(self, app) -> None:
        self.app = app

    # ------------------------------------------------------------------
    # Event entry point
    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    # ------------------------------------------------------------------
    # Internal helpers
    def _handle_key(self, key: int) -> None:
        app = self.app
        if app.superpowers.is_active():
            return
        if app.state in {"main_menu", "pause_menu", "post_game_menu", "settings_menu", "keybind_menu"}:
            self._handle_menu_key(key)
            return

        if app.cheat_enabled and key == pygame.K_F1:
            if app.session.is_animating_projectile() or app.winner:
                return
            app.cheat_menu_visible = not app.cheat_menu_visible
            app.message = (
                "Cheat console opened" if app.cheat_menu_visible else "Cheat console closed"
            )
            return

        if app.cheat_menu_visible:
            if key in {pygame.K_ESCAPE, pygame.K_F1}:
                app.cheat_menu_visible = False
                app.message = "Cheat console closed"
                return
            if key == pygame.K_1:
                app._cheat_explode(0)
                return
            if key == pygame.K_2:
                app._cheat_explode(1)
                return
            if key in {pygame.K_3, pygame.K_KP3}:
                app._cheat_fill_super_power()
                return
            return

        current_tank = app.session.current_tank
        if current_tank.super_power >= 1.0:
            if key == pygame.K_b and app._trigger_superpower("bomber"):
                return
            if key == pygame.K_n and app._trigger_superpower("squad"):
                return

        if app.session.is_animating_projectile():
            if key == pygame.K_ESCAPE:
                app._activate_menu("pause_menu")
            return

        if app.winner:
            if key == pygame.K_ESCAPE:
                app._activate_menu("post_game_menu")
            return

        if key == pygame.K_ESCAPE:
            app._activate_menu("pause_menu")
            return

        tank = current_tank
        bindings = app.player_bindings[app.current_player]

        if key == bindings.move_left:
            app._attempt_move(tank, -1)
            return
        if key == bindings.move_right:
            app._attempt_move(tank, 1)
            return
        if key == bindings.turret_up:
            tank.raise_turret()
            app.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.turret_down:
            tank.lower_turret()
            app.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.power_increase:
            previous = tank.shot_power
            tank.increase_power()
            if tank.shot_power == previous:
                app.message = f"{tank.name} power already max"
            else:
                app.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.power_decrease:
            previous = tank.shot_power
            tank.decrease_power()
            if tank.shot_power == previous:
                app.message = f"{tank.name} power already min"
            else:
                app.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.fire:
            app._fire_projectile(tank)
            return

    def _handle_menu_key(self, key: int) -> None:
        app = self.app
        if key == pygame.K_ESCAPE:
            if app.state == "keybind_menu":
                if app.keybindings.rebinding_target is not None:
                    app._cancel_binding()
                else:
                    app._action_keybindings_back()
                return
            if app.state == "main_menu":
                app._action_exit_game()
                return
            if app.state == "pause_menu":
                app._action_resume_game()
                return
            if app.state == "settings_menu":
                app._action_settings_back()
                return
            if app.state == "post_game_menu":
                app._action_return_to_start_menu()
                return

        if app.state == "settings_menu" and app.menu.selection == app.settings_resolution_option_index:
            if key == pygame.K_LEFT:
                app._change_resolution(-1)
                return
            if key == pygame.K_RIGHT:
                app._change_resolution(1)
                return

        if app.state == "keybind_menu":
            if app.keybindings.rebinding_target is not None:
                app._finish_binding(key)
                return

        if not app.menu.options:
            return

        if key in {pygame.K_UP, pygame.K_w}:
            app.menu.change_selection(-1)
            return
        if key in {pygame.K_DOWN, pygame.K_s}:
            app.menu.change_selection(1)
            return
        if key in {pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER}:
            app.menu.execute_current()


__all__ = ["InputHandler", "KeyBindings"]
