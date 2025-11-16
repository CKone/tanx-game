"""Input handling for the pygame client."""

from __future__ import annotations

import pygame
from tanx_game.pygame.keybindings import KeyBindings


class InputHandler:
    """Translate pygame events into application actions."""

    def __init__(self, app) -> None:
        self.app = app
        self._held_keys: set[int] = set()
        self._angle_remainder: float = 0.0
        self._power_remainder: float = 0.0

    # ------------------------------------------------------------------
    # Event entry point
    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._held_keys.add(event.key)
            self._handle_key(event)
        elif event.type == pygame.KEYUP:
            if event.key in self._held_keys:
                self._held_keys.discard(event.key)
            if event.key in {pygame.K_LSHIFT, pygame.K_RSHIFT}:
                self._angle_remainder = 0.0
                self._power_remainder = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    def _handle_key(self, event: pygame.event.Event) -> None:
        app = self.app
        key = event.key
        mods = getattr(event, "mod", 0)
        shift_pressed = bool(mods & pygame.KMOD_SHIFT)
        turret_step = 5 if shift_pressed else 1
        power_step = 0.1 if shift_pressed else 0.02
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
            if key == pygame.K_m and app._trigger_superpower("trajectory"):
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

        if app.is_ai_controlled(app.current_player):
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
            tank.raise_turret(amount=turret_step)
            app.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.turret_down:
            tank.lower_turret(amount=turret_step)
            app.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.power_increase:
            previous = tank.shot_power
            tank.increase_power(amount=power_step)
            if tank.shot_power == previous:
                app.message = f"{tank.name} power already max"
            else:
                app.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.power_decrease:
            previous = tank.shot_power
            tank.decrease_power(amount=power_step)
            if tank.shot_power == previous:
                app.message = f"{tank.name} power already min"
            else:
                app.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.fire:
            app._fire_projectile(tank)
            return

    def update(self, dt: float) -> None:
        app = self.app
        if app.state not in {"playing"}:
            return
        if app.superpowers.is_active():
            return
        if app.cheat_menu_visible or app.session.is_animating_projectile() or app.winner:
            return
        if app.keybindings.rebinding_target is not None:
            return
        if app.is_ai_controlled(app.current_player):
            return

        current_tank = app.session.current_tank
        bindings = app.player_bindings[app.current_player]

        mods = pygame.key.get_mods()
        shift_pressed = bool(mods & pygame.KMOD_SHIFT)

        angle_rate = 40.0 if not shift_pressed else 100.0
        power_rate = 0.3 if not shift_pressed else 0.9

        angle_direction = 0
        if bindings.turret_up in self._held_keys:
            angle_direction += 1
        if bindings.turret_down in self._held_keys:
            angle_direction -= 1

        if angle_direction == 0:
            self._angle_remainder = 0.0
        else:
            self._angle_remainder += angle_direction * angle_rate * dt
            step = int(self._angle_remainder)
            if step != 0:
                if step > 0:
                    current_tank.raise_turret(step)
                else:
                    current_tank.lower_turret(-step)
                self._angle_remainder -= step
                app.message = f"{current_tank.name} turret: {current_tank.turret_angle}°"

        power_direction = 0
        if bindings.power_increase in self._held_keys:
            power_direction += 1
        if bindings.power_decrease in self._held_keys:
            power_direction -= 1

        if power_direction == 0:
            self._power_remainder = 0.0
        else:
            delta = power_direction * power_rate * dt
            self._power_remainder += delta
            step = self._power_remainder
            if step > 0:
                current_tank.increase_power(amount=step)
            else:
                current_tank.decrease_power(amount=-step)
            self._power_remainder = 0.0
            app.message = f"{current_tank.name} power: {current_tank.shot_power:.2f}x"

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

        if app.state == "settings_menu" and app.menu.selection == getattr(app, "settings_style_option_index", -1):
            if key == pygame.K_LEFT:
                app._change_terrain_style(-1)
                return
            if key == pygame.K_RIGHT:
                app._change_terrain_style(1)
                return

        if app.state == "settings_menu" and app.menu.selection == getattr(app, "settings_weather_option_index", -1):
            if key == pygame.K_LEFT:
                app._change_weather(-1)
                return
            if key == pygame.K_RIGHT:
                app._change_weather(1)
                return

        if app.state == "settings_menu" and app.menu.selection == getattr(app, "settings_direct_damage_option_index", -1):
            if key == pygame.K_LEFT:
                app._adjust_damage("direct", -1)
                return
            if key == pygame.K_RIGHT:
                app._adjust_damage("direct", 1)
                return

        if app.state == "settings_menu" and app.menu.selection == getattr(app, "settings_splash_damage_option_index", -1):
            if key == pygame.K_LEFT:
                app._adjust_damage("splash", -1)
                return
            if key == pygame.K_RIGHT:
                app._adjust_damage("splash", 1)
                return

        if app.state == "settings_menu" and app.menu.selection == getattr(app, "settings_ai_difficulty_option_index", -1):
            if key == pygame.K_LEFT:
                app._change_ai_difficulty(-1)
                return
            if key == pygame.K_RIGHT:
                app._change_ai_difficulty(1)
                return

        if app.state == "settings_menu":
            selection = app.menu.selection
            if selection == getattr(app, "settings_master_volume_option_index", -1):
                if key == pygame.K_LEFT:
                    app._adjust_volume("master", -1)
                    return
                if key == pygame.K_RIGHT:
                    app._adjust_volume("master", 1)
                    return
            if selection == getattr(app, "settings_effects_volume_option_index", -1):
                if key == pygame.K_LEFT:
                    app._adjust_volume("effects", -1)
                    return
                if key == pygame.K_RIGHT:
                    app._adjust_volume("effects", 1)
                    return
            if selection == getattr(app, "settings_ambient_volume_option_index", -1):
                if key == pygame.K_LEFT:
                    app._adjust_volume("ambient", -1)
                    return
                if key == pygame.K_RIGHT:
                    app._adjust_volume("ambient", 1)
                    return

        if app.state == "keybind_menu":
            if app.keybindings.rebinding_target is not None:
                if key == pygame.K_ESCAPE:
                    app._cancel_binding()
                else:
                    app._finish_binding(key)
                return

        if not app.menu.options:
            return

        if key in {pygame.K_UP, pygame.K_w}:
            previous = app.menu.selection
            app.menu.change_selection(-1)
            if app.menu.selection != previous:
                app._play_ui_sound("menu_move")
            return
        if key in {pygame.K_DOWN, pygame.K_s}:
            previous = app.menu.selection
            app.menu.change_selection(1)
            if app.menu.selection != previous:
                app._play_ui_sound("menu_move")
            return
        if key in {pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER}:
            app.menu.execute_current()


__all__ = ["InputHandler", "KeyBindings"]
