"""Pygame-powered presentation layer for the Tanx duel."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

try:
    import pygame
    import pygame.gfxdraw
except ImportError as exc:  # pragma: no cover - depends on runtime environment
    raise RuntimeError(
        "The pygame package is required to run the graphical version of Tanx."
    ) from exc

from .game import Game, ShotResult
from .tank import Tank
from .world import TerrainSettings
from .ui.effects import EffectsSystem
from .ui.input import InputHandler, KeyBindings
from .ui.renderer.scene import (
    draw_background,
    draw_debris,
    draw_explosions,
    draw_particles,
    draw_projectile,
    draw_trails,
    draw_tanks,
    draw_world,
)
from .ui.menus import draw_menu_overlay, draw_ui


class PygameTanx:
    """Graphical Tanx client built on top of the core game logic."""

    def __init__(
        self,
        player_one: str = "Player 1",
        player_two: str = "Player 2",
        terrain_settings: Optional[TerrainSettings] = None,
        seed: Optional[int] = None,
        cell_size: int = 28,
        ui_height: int = 120,
        cheat_enabled: bool = False,
        start_in_menu: bool = True,
    ) -> None:
        pygame.init()
        pygame.font.init()

        self.cell_size = cell_size
        self.ui_height = ui_height
        self.cheat_enabled = cheat_enabled

        self.font_small = pygame.font.SysFont("consolas", 16)
        self.font_regular = pygame.font.SysFont("consolas", 20)
        self.font_large = pygame.font.SysFont(None, 48)

        self.clock = pygame.time.Clock()
        self.running = True

        self.player_names = [player_one, player_two]

        self.projectile_interval = 0.03

        self.effects = EffectsSystem(
            cell_size=self.cell_size,
            ui_height=self.ui_height,
        )
        self.input = InputHandler(self)

        self.menu_selection = 0
        self.menu_title = "Tanx - Arcade Duel"
        self.menu_message: Optional[str] = None
        self.menu_options: List[tuple[str, Callable[[], None]]] = []
        self.state = "main_menu" if start_in_menu else "playing"
        self.active_menu: Optional[str] = "main_menu" if start_in_menu else None
        self._settings_instructions = "Use ←/→ to adjust the resolution, Enter toggles fullscreen."

        self.windowed_fullscreen = False
        self.windowed_fullscreen_size: Optional[Tuple[int, int]] = None
        self._display_flags = 0
        self.screen = pygame.display.set_mode((640, 480), self._display_flags)
        pygame.display.set_caption("Tanx - Arcade Duel")
        self.display_surface = self.screen
        self.render_surface: Optional[pygame.Surface] = None
        self.playfield_offset_x = 0

        self.projectile_result: Optional[ShotResult] = None
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_position: Optional[tuple[float, float]] = None
        self.active_shooter: Optional[Tank] = None
        self.cheat_menu_visible = False
        self.winner: Optional[Tank] = None
        self.winner_delay = 0.0

        self._supported_cell_sizes = [20, 24, 28, 32, 36]
        self.resolution_presets: List[dict[str, object]] = []
        self.resolution_index = 0
        self.settings_resolution_option_index = 0
        self.settings_keybind_option_index = 1
        self.settings_fullscreen_option_index = 2
        self.binding_fields: List[tuple[str, str]] = [
            ("Move Left", "move_left"),
            ("Move Right", "move_right"),
            ("Turret Up", "turret_up"),
            ("Turret Down", "turret_down"),
            ("Fire", "fire"),
            ("Power -", "power_decrease"),
            ("Power +", "power_increase"),
        ]
        self.rebinding_target: Optional[tuple[int, str]] = None

        self.default_bindings = [
            KeyBindings(
                move_left=pygame.K_a,
                move_right=pygame.K_d,
                turret_up=pygame.K_w,
                turret_down=pygame.K_s,
                fire=pygame.K_SPACE,
                power_decrease=pygame.K_q,
                power_increase=pygame.K_e,
            ),
            KeyBindings(
                move_left=pygame.K_LEFT,
                move_right=pygame.K_RIGHT,
                turret_up=pygame.K_UP,
                turret_down=pygame.K_DOWN,
                fire=pygame.K_RETURN,
                power_decrease=pygame.K_LEFTBRACKET,
                power_increase=pygame.K_RIGHTBRACKET,
            ),
        ]
        self.player_bindings = [KeyBindings(**vars(binding)) for binding in self.default_bindings]

        self.sky_color_top = pygame.Color(78, 149, 205)
        self.sky_color_bottom = pygame.Color(19, 57, 84)
        self.ground_color = pygame.Color(87, 59, 32)
        self.tank_colors = [pygame.Color(80, 200, 120), pygame.Color(237, 85, 59)]
        self.projectile_color = pygame.Color(255, 231, 97)
        self.crater_rim_color = pygame.Color(120, 93, 63)

        self._setup_new_match(player_one, player_two, terrain_settings, seed)

        if self.state == "main_menu":
            self._activate_menu("main_menu")

        self._last_regular_settings = TerrainSettings(**vars(self.logic.world.settings))

    def _setup_new_match(
        self,
        player_one: str,
        player_two: str,
        terrain_settings: Optional[TerrainSettings],
        seed: Optional[int],
    ) -> None:
        self.logic = Game(player_one, player_two, terrain_settings, seed)
        self.player_names = [player_one, player_two]
        self._terrain_settings = self.logic.world.settings

        self.world_width = self.logic.world.width
        self.world_height = self.logic.world.height

        width = self.world_width * self.cell_size
        height = self.world_height * self.cell_size + self.ui_height
        if self.windowed_fullscreen and self.windowed_fullscreen_size:
            self._set_display_mode(self.windowed_fullscreen_size, pygame.NOFRAME)
        else:
            self._set_display_mode((width, height))

        self.effects.cell_size = self.cell_size
        self.effects.ui_height = self.ui_height
        self.effects.reset()

        self.current_player = 0
        self.message = f"{self.logic.tanks[0].name}'s turn"

        self.projectile_result = None
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_position = None
        self.active_shooter = None

        self.winner = None
        self.winner_delay = 0.0
        self.cheat_menu_visible = False

        self._sync_resolution_presets()

        if not self.windowed_fullscreen:
            self._last_regular_settings = TerrainSettings(**vars(self.logic.world.settings))

    def _clone_current_settings(self) -> TerrainSettings:
        settings = self.logic.world.settings
        return TerrainSettings(**vars(settings))

    def _restart_match(self, *, start_in_menu: bool, message: Optional[str] = None) -> None:
        settings = self._clone_current_settings()
        self._setup_new_match(
            self.player_names[0],
            self.player_names[1],
            settings,
            settings.seed,
        )
        if start_in_menu:
            self._activate_menu("main_menu", message=message)
        else:
            self.state = "playing"
            self.active_menu = None
            self.menu_message = None
            if message:
                self.message = message

    def _set_display_mode(self, size: tuple[int, int], flags: int = 0) -> None:
        if self._display_flags != flags or self.display_surface.get_size() != size:
            self.display_surface = pygame.display.set_mode(size, flags)
            self._display_flags = flags
            pygame.display.set_caption("Tanx - Arcade Duel")
        self._update_render_target()

    def _update_render_target(self) -> None:
        if self.windowed_fullscreen:
            width = self.world_width * self.cell_size
            height = self.world_height * self.cell_size + self.ui_height
            desired = (width, height)
            if self.render_surface is None or self.render_surface.get_size() != desired:
                self.render_surface = pygame.Surface(desired).convert_alpha()
            self.screen = self.render_surface
        else:
            self.render_surface = None
            self.screen = self.display_surface
        self._update_playfield_offset()

    def _update_playfield_offset(self) -> None:
        if not hasattr(self, "world_width") or not hasattr(self, "cell_size"):
            self.playfield_offset_x = 0
            return
        playfield_width = self.world_width * self.cell_size
        screen_width = self.screen.get_width()
        self.playfield_offset_x = max(0, (screen_width - playfield_width) // 2)

    def _sync_resolution_presets(self) -> None:
        if not hasattr(self, "world_width") or not hasattr(self, "world_height"):
            return
        unique_sizes = sorted(set(self._supported_cell_sizes + [self.cell_size]))
        presets: List[dict[str, object]] = []
        for cell_size in unique_sizes:
            width = self.world_width * cell_size
            height = self.world_height * cell_size + self.ui_height
            presets.append(
                {
                    "cell_size": cell_size,
                    "label": f"{width}×{height}",
                    "size": (width, height),
                }
            )
        self.resolution_presets = presets
        self.resolution_index = 0
        for idx, preset in enumerate(presets):
            if int(preset["cell_size"]) == self.cell_size:
                self.resolution_index = idx
                break

    def _resolution_option_label(self) -> str:
        if not self.resolution_presets:
            self._sync_resolution_presets()
        if not self.resolution_presets:
            return "Resolution: unavailable"
        preset = self.resolution_presets[self.resolution_index]
        label = str(preset["label"])
        return f"Resolution: {label}"

    def _format_key_name(self, key: int) -> str:
        name = pygame.key.name(key)
        return name.upper()

    def _binding_label(self, field: str) -> str:
        for label, attr in self.binding_fields:
            if attr == field:
                return label
        return field

    def _windowed_fullscreen_label(self) -> str:
        label = "Windowed Fullscreen"
        if self.windowed_fullscreen_size:
            width, height = self.windowed_fullscreen_size
            label = f"{label} ({width}×{height})"
            return label

    def _enter_windowed_fullscreen(self) -> None:
        try:
            desktops = pygame.display.get_desktop_sizes()
        except AttributeError:
            desktops = []
        if not desktops:
            info = pygame.display.Info()
            desktops = [(info.current_w, info.current_h)] if info.current_w and info.current_h else []
        if not desktops:
            if self.state == "settings_menu":
                self.menu_message = "Desktop size unavailable"
            return
        width, height = desktops[0]
        if width <= 0 or height <= 0:
            if self.state == "settings_menu":
                self.menu_message = "Desktop size unavailable"
            return
        available_height = max(1, height - self.ui_height)
        base_settings = self._last_regular_settings
        height_cells = max(1, base_settings.height)
        cell_from_height = max(4, available_height // height_cells)
        cell_size = min(max(self._supported_cell_sizes), cell_from_height)
        if cell_size not in self._supported_cell_sizes:
            self._supported_cell_sizes.append(cell_size)
            self._supported_cell_sizes.sort()

        width_cells = max(base_settings.width, max(1, width // max(1, cell_size)))
        new_settings = TerrainSettings(**vars(base_settings))
        new_settings.width = width_cells

        self.windowed_fullscreen = True
        self.windowed_fullscreen_size = (width, height)
        self.cell_size = cell_size
        self._setup_new_match(
            self.player_names[0],
            self.player_names[1],
            new_settings,
            new_settings.seed,
        )
        if self.state == "settings_menu":
            self.menu_message = f"Windowed fullscreen {width}×{height}"
            self._update_settings_menu_options()

    def _apply_resolution(self, cell_size: int) -> None:
        updated = cell_size != self.cell_size or self.windowed_fullscreen
        self.windowed_fullscreen = False
        self.windowed_fullscreen_size = None
        if updated:
            self.cell_size = cell_size
            settings = TerrainSettings(**vars(self._last_regular_settings))
            self._setup_new_match(
                self.player_names[0],
                self.player_names[1],
                settings,
                settings.seed,
            )
        self._sync_resolution_presets()
        if self.state == "settings_menu":
            self._update_settings_menu_options()

    def _change_resolution(self, direction: int) -> None:
        if not self.resolution_presets:
            self._sync_resolution_presets()
        if not self.resolution_presets:
            return
        target_index = (self.resolution_index + direction) % len(self.resolution_presets)
        target = self.resolution_presets[target_index]
        label = str(target["label"])
        self.resolution_index = target_index
        self._apply_resolution(int(target["cell_size"]))
        if self.state == "settings_menu":
            self.menu_message = f"Resolution set to {label}"
            self._update_settings_menu_options()

    def _build_settings_menu_options(self) -> List[tuple[str, Callable[[], None]]]:
        self.settings_resolution_option_index = 0
        self.settings_keybind_option_index = 1
        self.settings_fullscreen_option_index = 2
        return [
            (self._resolution_option_label(), self._action_cycle_resolution_forward),
            ("Configure Keybindings", self._action_open_keybindings),
            (self._windowed_fullscreen_label(), self._action_enter_windowed_fullscreen),
            ("Back to Start Menu", self._action_settings_back),
        ]

    def _update_settings_menu_options(self) -> None:
        if self.state != "settings_menu":
            return
        current_selection = min(self.menu_selection, max(len(self.menu_options) - 1, 0))
        self.menu_options = self._build_settings_menu_options()
        self.menu_selection = min(current_selection, len(self.menu_options) - 1)

    def _build_keybinding_menu_options(self) -> List[tuple[str, Callable[[], None]]]:
        options: List[tuple[str, Callable[[], None]]] = []
        for player_idx, prefix in enumerate(["Player 1", "Player 2"]):
            bindings = self.player_bindings[player_idx]
            for label, field in self.binding_fields:
                key_code = getattr(bindings, field)
                options.append(
                    (
                        f"{prefix} {label}: {self._format_key_name(key_code)}",
                        lambda pi=player_idx, f=field: self._start_rebinding(pi, f),
                    )
                )
        options.append(("Reset to Defaults", self._action_reset_keybindings))
        options.append(("Back to Settings", self._action_keybindings_back))
        return options

    def _update_keybinding_menu_options(self) -> None:
        if self.state != "keybind_menu":
            return
        current_selection = min(self.menu_selection, max(len(self.menu_options) - 1, 0))
        self.menu_options = self._build_keybinding_menu_options()
        self.menu_selection = min(current_selection, len(self.menu_options) - 1)
        if self.rebinding_target is not None:
            player_idx, field = self.rebinding_target
            label = self._binding_label(field)
            self.menu_message = (
                f"Press a key for Player {player_idx + 1} {label} (Esc to cancel)"
            )
        else:
            self.menu_message = "Select an action to rebind."


    def _activate_menu(self, name: str, message: Optional[str] = None) -> None:
        self.active_menu = name
        self.state = name
        self.menu_selection = 0
        self.menu_message = message
        self.cheat_menu_visible = False

        if name == "main_menu":
            self.menu_title = "Tanx - Arcade Duel"
            self.menu_options = [
                ("Start Game", self._action_start_game),
                ("Settings", self._action_open_settings),
                ("Exit Game", self._action_exit_game),
            ]
        elif name == "pause_menu":
            self.menu_title = "Pause"
            self.menu_options = [
                ("Resume Game", self._action_resume_game),
                ("Abandon Game", self._action_abandon_game),
            ]
        elif name == "settings_menu":
            self.menu_title = "Settings"
            self.menu_options = self._build_settings_menu_options()
        elif name == "keybind_menu":
            self.menu_title = "Key Bindings"
            self.menu_options = self._build_keybinding_menu_options()
        elif name == "post_game_menu":
            title = f"{self.winner.name} Wins!" if self.winner else "Game Over"
            self.menu_title = title
            self.menu_options = [
                ("Start New Game", self._action_start_new_game),
                ("Return to Start Menu", self._action_return_to_start_menu),
            ]
        else:
            self.menu_title = "Tanx"
            self.menu_options = []

        if self.menu_message is None:
            if name == "main_menu":
                self.menu_message = "Use ↑/↓ and Enter to choose."
            elif name == "pause_menu":
                self.menu_message = "Game paused."
            elif name == "settings_menu":
                self.menu_message = self._settings_instructions
            elif name == "keybind_menu":
                self.menu_message = "Select an action to rebind."
            elif name == "post_game_menu":
                self.menu_message = self.message

    def _action_start_game(self) -> None:
        self._restart_match(start_in_menu=False)

    def _action_exit_game(self) -> None:
        self.running = False

    def _action_open_settings(self) -> None:
        self._activate_menu("settings_menu")

    def _action_settings_back(self) -> None:
        message = None
        if self.menu_message and self.menu_message != self._settings_instructions:
            message = self.menu_message
        self._activate_menu("main_menu", message=message)

    def _action_open_keybindings(self) -> None:
        self.rebinding_target = None
        self._activate_menu("keybind_menu")

    def _action_keybindings_back(self) -> None:
        self.rebinding_target = None
        self._activate_menu("settings_menu")

    def _action_reset_keybindings(self) -> None:
        self.player_bindings = [KeyBindings(**vars(binding)) for binding in self.default_bindings]
        self.menu_message = "Key bindings reset to defaults."
        self._update_keybinding_menu_options()

    def _start_rebinding(self, player_idx: int, field: str) -> None:
        self.rebinding_target = (player_idx, field)
        label = self._binding_label(field)
        self.menu_message = (
            f"Press a key for Player {player_idx + 1} {label} (Esc to cancel)"
        )
        self._update_keybinding_menu_options()

    def _finish_rebinding(self, key: int) -> None:
        if self.rebinding_target is None:
            return
        player_idx, field = self.rebinding_target
        setattr(self.player_bindings[player_idx], field, key)
        self.rebinding_target = None
        label = self._binding_label(field)
        self.menu_message = (
            f"Player {player_idx + 1} {label} bound to {self._format_key_name(key)}"
        )
        self._update_keybinding_menu_options()

    def _cancel_rebinding(self) -> None:
        if self.rebinding_target is None:
            return
        self.rebinding_target = None
        self.menu_message = "Rebinding cancelled."
        self._update_keybinding_menu_options()

    def _action_enter_windowed_fullscreen(self) -> None:
        self._enter_windowed_fullscreen()

    def _action_cycle_resolution_forward(self) -> None:
        self._change_resolution(1)

    def _action_resume_game(self) -> None:
        self.state = "playing"
        self.active_menu = None
        self.menu_message = None

    def _action_abandon_game(self) -> None:
        self._restart_match(start_in_menu=True, message="Game abandoned.")

    def _action_start_new_game(self) -> None:
        self._restart_match(start_in_menu=False)

    def _action_return_to_start_menu(self) -> None:
        victory_message = None
        if self.winner:
            victory_message = f"{self.winner.name} secured the round."
        self._restart_match(start_in_menu=True, message=victory_message)

    # ------------------------------------------------------------------
    # Game Loop helpers
    def run(self) -> None:
        """Main pygame loop."""

        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            else:
                self.input.process_event(event)

    def _update(self, dt: float) -> None:
        self.effects.update(dt, self.logic.world)
        if self.winner and self.winner_delay > 0:
            self.winner_delay = max(0.0, self.winner_delay - dt)

        if self.state != "playing":
            return

        if self.winner and self.winner_delay <= 0 and not self._is_animating_projectile():
            self._activate_menu("post_game_menu", message=self.message)
            return

        if not self._is_animating_projectile():
            return
        self.projectile_timer += dt
        while self.projectile_timer >= self.projectile_interval:
            self.projectile_timer -= self.projectile_interval
            assert self.projectile_result is not None
            path = self.projectile_result.path
            self.projectile_index += 1
            if self.projectile_index >= len(path):
                result = self.projectile_result
                self.projectile_position = None
                self.projectile_result = None
                self._finish_projectile(result)
                break
            self.projectile_position = path[self.projectile_index]
            self.effects.spawn_trail(self.projectile_position)

    def _draw(self) -> None:
        target_surface = self.screen
        target_surface.fill((0, 0, 0))
        draw_background(self)
        draw_world(self)
        draw_tanks(self)
        draw_trails(self)
        draw_particles(self)
        draw_debris(self)
        if self.projectile_position:
            draw_projectile(self, self.projectile_position)
        draw_explosions(self)
        if self.state in {"playing", "pause_menu"}:
            draw_ui(self)
        if self.state in {"main_menu", "pause_menu", "post_game_menu", "settings_menu", "keybind_menu"}:
            draw_menu_overlay(self)

        if self.render_surface is not None:
            if self.render_surface.get_size() == self.display_surface.get_size():
                self.display_surface.blit(self.render_surface, (0, 0))
            else:
                pygame.transform.smoothscale(
                    self.render_surface,
                    self.display_surface.get_size(),
                    self.display_surface,
                )
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Actions
    def _attempt_move(self, tank: Tank, direction: int) -> None:
        if tank.move(self.logic.world, direction):
            direction_text = "left" if direction < 0 else "right"
            self._advance_turn()
            self.message = (
                f"{tank.name} moved {direction_text}. "
                f"Next: {self.logic.tanks[self.current_player].name}'s turn"
            )
        else:
            self.message = f"{tank.name} cannot move that way"

    def _fire_projectile(self, tank: Tank) -> None:
        tank.last_command = "fire"
        result = self.logic.step_projectile(tank, apply_effects=False)
        self.projectile_result = result
        self.projectile_index = 0
        self.projectile_timer = 0.0
        if result.path:
            self.projectile_position = result.path[0]
            self.effects.spawn_trail(self.projectile_position)
        else:
            self.projectile_position = None
        self.message = f"{tank.name} fires!"
        self.active_shooter = tank

    def _finish_projectile(self, result: Optional[ShotResult]) -> None:
        if result:
            self.logic.apply_shot_effects(result)
            self.effects.spawn_impact_particles(result)
        if result and result.hit_tank:
            self.message = f"Direct hit on {result.hit_tank.name}!"
        elif result and result.impact_x is not None:
            self.message = "Shot impacted the terrain."
        else:
            self.message = "Shot flew off into the distance."

        if result and result.impact_x is not None and result.impact_y is not None:
            scale = 1.0
            if result.fatal_hit:
                scale = 1.8
                self.effects.spawn_fatal_debris(result, self.logic.tanks, self.tank_colors)
            elif result.hit_tank is not None:
                scale = 1.15
            self.effects.spawn_explosion((result.impact_x, result.impact_y), scale)

        self.active_shooter = None

        self._advance_turn()
        self._check_victory()
        if self.winner:
            if result and result.fatal_hit:
                self.winner_delay = 2.0
            else:
                self.winner_delay = 0.0
        if not self.winner:
            self.message += f" Next: {self.logic.tanks[self.current_player].name}'s turn"

    def _cheat_explode(self, tank_index: int) -> None:
        if not self.cheat_enabled:
            return
        if not (0 <= tank_index < len(self.logic.tanks)):
            return
        tank = self.logic.tanks[tank_index]
        if not tank.alive:
            self.message = f"Cheat console: {tank.name} already destroyed"
            self.cheat_menu_visible = False
            return
        # Ensure upcoming damage will be lethal
        if tank.hp > self.logic.damage:
            tank.hp = self.logic.damage
        elif tank.hp <= 0:
            tank.hp = 1
        result = ShotResult(
            hit_tank=tank,
            impact_x=float(tank.x),
            impact_y=float(tank.y),
            path=[],
        )
        self.logic.apply_shot_effects(result)
        result.impact_x = float(tank.x)
        result.impact_y = float(tank.y)
        if result.hit_tank is None:
            result.hit_tank = tank
        if not result.fatal_hit:
            # Guarantee the tank is destroyed for spectacle
            tank.take_damage(tank.hp or 1)
            result.fatal_hit = True
            result.fatal_tank = tank
        scale = 1.8 if result.fatal_hit else 1.15
        self.effects.spawn_impact_particles(result)
        self.effects.spawn_explosion((result.impact_x, result.impact_y), scale)
        if result.fatal_hit:
            self.effects.spawn_fatal_debris(result, self.logic.tanks, self.tank_colors)
        self.projectile_result = None
        self.projectile_position = None
        self.cheat_menu_visible = False
        self._check_victory()
        if self.winner:
            loser = result.fatal_tank or tank
            if result.fatal_hit:
                self.winner_delay = 2.0
            else:
                self.winner_delay = 0.0
            self.message = f"Cheat console: {loser.name} obliterated"
        else:
            self.winner_delay = 0.0
            self.message = f"Cheat console: {tank.name} detonated"
    def _advance_turn(self) -> None:
        self.current_player = 1 - self.current_player

    def _check_victory(self) -> None:
        alive = [tank for tank in self.logic.tanks if tank.alive]
        if len(alive) == 1:
            self.winner = alive[0]
            loser = next(t for t in self.logic.tanks if t is not self.winner)
            self.message = f"{self.winner.name} wins! {loser.name} is destroyed."
        elif len(alive) == 0:
            self.winner = None
            self.message = "Both tanks destroyed!"

    def _is_animating_projectile(self) -> bool:
        return self.projectile_result is not None


def run_pygame(**kwargs: object) -> None:
    """Convenience helper for launching the pygame client."""

    app = PygameTanx(**kwargs)
    app.run()
