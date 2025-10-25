"""Pygame-powered presentation layer for the Tanx duel."""

from __future__ import annotations

from typing import List, Optional

try:
    import pygame
    import pygame.gfxdraw
except ImportError as exc:  # pragma: no cover - depends on runtime environment
    raise RuntimeError(
        "The pygame package is required to run the graphical version of Tanx."
    ) from exc

from tanx_game.core.game import Game, ShotResult
from tanx_game.core.session import GameSession, ProjectileStep
from tanx_game.core.tank import Tank
from tanx_game.core.world import TerrainSettings
from tanx_game.pygame.config import load_user_settings, save_user_settings
from tanx_game.pygame.display import DisplayManager
from tanx_game.pygame.effects import EffectsSystem
from tanx_game.pygame.input import InputHandler
from tanx_game.pygame.keybindings import KeybindingManager, KeyBindings
from tanx_game.pygame.menu_controller import MenuController, MenuDefinition, MenuOption
from tanx_game.pygame.renderer import (
    draw_background,
    draw_aim_indicator,
    draw_rubble,
    draw_buildings,
    draw_debris,
    draw_explosions,
    draw_particles,
    draw_projectile,
    draw_trails,
    draw_tanks,
    draw_world,
)
from tanx_game.pygame.menus import draw_menu_overlay, draw_ui
from tanx_game.pygame.superpowers import SuperpowerManager


class PygameTanx:
    """Graphical Tanx client built on top of the core game logic."""

    def __init__(
        self,
        player_one: str = "Player 1",
        player_two: str = "Player 2",
        terrain_settings: Optional[TerrainSettings] = None,
        seed: Optional[int] = None,
        cell_size: int = 28,
        ui_height: int = 180,
        cheat_enabled: bool = False,
        start_in_menu: bool = True,
        debug: bool = False,
    ) -> None:
        pygame.init()
        pygame.font.init()

        self.cheat_enabled = cheat_enabled
        self.debug = debug
        self._ui_height = ui_height

        self._user_settings = load_user_settings()
        stored_cell_size = self._user_settings.get("cell_size")
        if isinstance(stored_cell_size, int) and stored_cell_size >= 4:
            cell_size = stored_cell_size

        self.display = DisplayManager(
            cell_size=cell_size,
            ui_height=ui_height,
            caption="Tanx - Arcade Duel",
        )

        self.font_small = pygame.font.SysFont("consolas", 16)
        self.font_regular = pygame.font.SysFont("consolas", 20)
        self.font_large = pygame.font.SysFont(None, 48)

        self.clock = pygame.time.Clock()
        self.running = True

        self.player_names = [player_one, player_two]
        self._reset_match_progress()

        self.projectile_interval = 0.03

        self._terrain_styles = [
            {"key": "classic", "label": "Classic Hills"},
            {"key": "urban", "label": "Urban Conflict"},
        ]
        self._terrain_style_index = 0
        self._terrain_descriptions = {
            "classic": "Classic Hills: rolling procedural terrain ideal for long-range duels.",
            "urban": "Urban Conflict: dense city blocks with destructible buildings and rubble cover.",
        }

        self.effects = EffectsSystem(
            cell_size=self.cell_size,
            ui_height=self.ui_height,
        )
        self.input = InputHandler(self)

        self.menu = MenuController()
        self.state = "main_menu" if start_in_menu else "playing"
        self._settings_instructions = (
            "Use ←/→ to adjust the highlighted option. Enter toggles fullscreen."
        )

        self.cheat_menu_visible = False

        self.settings_resolution_option_index = 0
        self.settings_style_option_index = 1
        self.settings_keybind_option_index = 2
        self.settings_fullscreen_option_index = 3

        self.keybindings = KeybindingManager()
        self.player_bindings = self.keybindings.player_bindings
        self.superpowers = SuperpowerManager(self)

        stored_keybindings = self._user_settings.get("keybindings")
        if isinstance(stored_keybindings, list):
            self.keybindings.load_from_config(stored_keybindings)
            self.player_bindings = self.keybindings.player_bindings

        stored_style = self._user_settings.get("terrain_style")
        if isinstance(stored_style, str):
            self._set_terrain_style(stored_style)
        else:
            self._set_terrain_style(self._terrain_styles[self._terrain_style_index]["key"])

        self.sky_color_top = pygame.Color(78, 149, 205)
        self.sky_color_bottom = pygame.Color(19, 57, 84)
        self.ground_color = pygame.Color(87, 59, 32)
        self.tank_colors = [pygame.Color(80, 200, 120), pygame.Color(237, 85, 59)]
        self.projectile_color = pygame.Color(255, 231, 97)
        self.crater_rim_color = pygame.Color(120, 93, 63)

        self._register_menus()

        self._setup_new_match(player_one, player_two, terrain_settings, seed)

        if self._user_settings.get("windowed_fullscreen") and not self.display.windowed_fullscreen:
            self._enter_windowed_fullscreen()

        if self.state == "main_menu":
            self._activate_menu("main_menu")

        if not self.display.windowed_fullscreen:
            self._last_regular_settings = TerrainSettings(**vars(self.logic.world.settings))

        self._save_user_settings()

    @property
    def cell_size(self) -> int:
        return self.display.cell_size

    @cell_size.setter
    def cell_size(self, value: int) -> None:
        self.display.cell_size = value

    @property
    def ui_height(self) -> int:
        return self._ui_height

    @property
    def screen(self) -> pygame.Surface:
        return self.display.screen

    @property
    def display_surface(self) -> pygame.Surface:
        return self.display.display_surface

    @property
    def render_surface(self) -> Optional[pygame.Surface]:
        return self.display.render_surface

    @property
    def playfield_offset_x(self) -> int:
        return self.display.playfield_offset_x

    @property
    def world_width(self) -> int:
        try:
            return self.logic.world.width
        except AttributeError:
            return 0

    @property
    def world_height(self) -> int:
        try:
            return self.logic.world.height
        except AttributeError:
            return 0

    @property
    def message(self) -> str:
        return self.session.message

    @message.setter
    def message(self, value: str) -> None:
        self.session.message = value

    @property
    def current_player(self) -> int:
        return self.session.current_player

    @property
    def winner(self) -> Optional[Tank]:
        return self.session.winner

    @property
    def winner_delay(self) -> float:
        return self.session.winner_delay

    def _save_user_settings(self) -> None:
        data = {
            "cell_size": int(self.display.cell_size),
            "windowed_fullscreen": bool(self.display.windowed_fullscreen),
            "keybindings": self.keybindings.to_config(),
            "terrain_style": self.terrain_style,
        }
        save_user_settings(data)
        self._user_settings = data

    def _debug(self, message: str) -> None:
        if self.debug:
            print(f"[DEBUG] {message}", flush=True)

    def _debug_world_summary(self) -> None:
        if not self.debug:
            return
        game = getattr(self, "logic", None)
        if game is None:
            return
        terrain = getattr(game, "world", None)
        if terrain is None:
            return
        style = getattr(terrain.settings, "style", "classic")
        self._debug(
            f"World generated: style={style}, size={terrain.width}x{terrain.height}, buildings={len(getattr(terrain, 'buildings', []))}"
        )
        buildings = getattr(terrain, "buildings", [])
        if not buildings:
            return
        limit = 5
        for building in buildings[:limit]:
            floors_status = ", ".join(
                f"{floor.hp}/{floor.max_hp}" for floor in building.floors
            )
            self._debug(
                f"  Building {building.id}: x=({building.left:.1f},{building.right:.1f}), base={building.base:.1f}, floors={len(building.floors)} [{floors_status}]"
            )
        remaining = len(buildings) - limit
        if remaining > 0:
            self._debug(f"  ... and {remaining} more buildings")

    def _reset_match_progress(self) -> None:
        self.match_scores = [0, 0]
        self.rounds_played = 0
        self._round_recorded = False

    def _setup_new_match(
        self,
        player_one: str,
        player_two: str,
        terrain_settings: Optional[TerrainSettings],
        seed: Optional[int],
    ) -> None:
        if terrain_settings is None:
            effective_settings = TerrainSettings(seed=seed)
        else:
            effective_settings = TerrainSettings(**vars(terrain_settings))
            if seed is not None:
                effective_settings.seed = seed
        effective_settings.style = self.terrain_style
        self.logic = Game(player_one, player_two, effective_settings, effective_settings.seed)
        self.player_names = [player_one, player_two]
        self._terrain_settings = self.logic.world.settings

        self.display.configure_world(
            self.logic.world.width,
            self.logic.world.height,
        )

        self.effects.cell_size = self.cell_size
        self.effects.ui_height = self.ui_height
        self.effects.reset()

        self.session = GameSession(
            self.logic, projectile_interval=self.projectile_interval
        )
        self.cheat_menu_visible = False
        self._round_recorded = False

        if not self.display.windowed_fullscreen:
            self._last_regular_settings = TerrainSettings(**vars(self.logic.world.settings))

        for tank in self.logic.tanks:
            tank.reset_super_power()

        self._debug_world_summary()

    def _clone_current_settings(self) -> TerrainSettings:
        settings = self.logic.world.settings
        return TerrainSettings(**vars(settings))

    def _register_menus(self) -> None:
        self.menu.register(
            "main_menu",
            MenuDefinition(
                title=(
                    "Tanx - Arcade Duel\n"
                    "A Father and Son Project of an old school tank game"
                ),
                build_options=lambda: [
                    MenuOption("Start Game", self._action_start_game),
                    MenuOption("Settings", self._action_open_settings),
                    MenuOption("Exit Game", self._action_exit_game),
                ],
                default_message=lambda: "Use ↑/↓ and Enter to choose.",
            ),
        )
        self.menu.register(
            "pause_menu",
            MenuDefinition(
                title="Pause",
                build_options=lambda: [
                    MenuOption("Resume Game", self._action_resume_game),
                    MenuOption("Abandon Game", self._action_abandon_game),
                ],
                default_message=lambda: "Game paused.",
            ),
        )
        self.menu.register(
            "settings_menu",
            MenuDefinition(
                title="Settings",
                build_options=self._build_settings_menu_options,
                default_message=lambda: self._settings_instructions,
            ),
        )
        self.menu.register(
            "keybind_menu",
            MenuDefinition(
                title="Key Bindings",
                build_options=self._build_keybinding_menu_options,
                default_message=self.keybindings.menu_message,
            ),
        )
        self.menu.register(
            "post_game_menu",
            MenuDefinition(
                title="Game Over",
                build_options=lambda: [
                    MenuOption("Start New Game", self._action_start_new_game),
                    MenuOption("Return to Start Menu", self._action_return_to_start_menu),
                ],
                default_message=lambda: self.message,
            ),
        )

    def _restart_match(
        self,
        *,
        start_in_menu: bool,
        message: Optional[str] = None,
        reset_scores: bool = False,
    ) -> None:
        settings = self._clone_current_settings()
        if reset_scores:
            self._reset_match_progress()
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
            self._close_menu()
            if message:
                self.message = message

    def _resolution_option_label(self) -> str:
        return self.display.resolution_option_label()

    def _windowed_fullscreen_label(self) -> str:
        return self.display.windowed_fullscreen_label()

    def _terrain_style_option_label(self) -> str:
        style = self._terrain_styles[self._terrain_style_index]
        return f"Map Style: {style['label']}"

    def _terrain_style_description(self) -> str:
        style_key = self._terrain_styles[self._terrain_style_index]["key"]
        return self._terrain_descriptions.get(style_key, "")

    @property
    def terrain_style(self) -> str:
        return self._terrain_styles[self._terrain_style_index]["key"]

    def _set_terrain_style(self, style_key: str) -> None:
        for idx, entry in enumerate(self._terrain_styles):
            if entry["key"] == style_key:
                self._terrain_style_index = idx
                break
        else:
            self._terrain_style_index = 0

    def _change_terrain_style(self, direction: int) -> None:
        if not self._terrain_styles:
            return
        current = self._terrain_style_index
        self._terrain_style_index = (self._terrain_style_index + direction) % len(self._terrain_styles)
        if self._terrain_style_index != current:
            style = self._terrain_styles[self._terrain_style_index]
            if self.state == "settings_menu":
                description = self._terrain_descriptions.get(style["key"], "")
                message = f"Map style set to {style['label']}"
                if description:
                    message = f"{message}\n{description}"
                self.menu.set_message(message)
                self._update_settings_menu_options()
            self._debug(f"Terrain style changed to {style['key']} ({style['label']})")
            self._save_user_settings()

    def _enter_windowed_fullscreen(self) -> None:
        base_settings = self._last_regular_settings
        new_settings, message = self.display.enter_windowed_fullscreen(base_settings)
        if new_settings is None:
            if self.state == "settings_menu" and message:
                self.menu.set_message(message)
            return
        self._setup_new_match(
            self.player_names[0],
            self.player_names[1],
            new_settings,
            new_settings.seed,
        )
        if self.state == "settings_menu" and message:
            self.menu.set_message(message)
            self._update_settings_menu_options()
        self._save_user_settings()

    def _apply_resolution(self, cell_size: int) -> None:
        if not self.display.apply_resolution(cell_size):
            return
        settings = TerrainSettings(**vars(self._last_regular_settings))
        self._setup_new_match(
            self.player_names[0],
            self.player_names[1],
            settings,
            settings.seed,
        )
        if self.state == "settings_menu":
            self._update_settings_menu_options()
        self._save_user_settings()

    def _change_resolution(self, direction: int) -> None:
        preset = self.display.change_resolution(direction)
        if preset is None:
            return
        self._apply_resolution(preset.cell_size)
        if self.state == "settings_menu":
            self.menu.set_message(f"Resolution set to {preset.label}")
            self._update_settings_menu_options()

    def _build_settings_menu_options(self) -> List[MenuOption]:
        self.settings_resolution_option_index = 0
        self.settings_style_option_index = 1
        self.settings_keybind_option_index = 2
        self.settings_fullscreen_option_index = 3
        return [
            MenuOption(self._resolution_option_label(), self._action_cycle_resolution_forward),
            MenuOption(self._terrain_style_option_label(), self._action_cycle_terrain_style_forward),
            MenuOption("Configure Keybindings", self._action_open_keybindings),
            MenuOption(self._windowed_fullscreen_label(), self._action_enter_windowed_fullscreen),
            MenuOption("Back to Start Menu", self._action_settings_back),
        ]

    def _update_settings_menu_options(self) -> None:
        if self.state != "settings_menu":
            return
        self.menu.update_options()

    def _build_keybinding_menu_options(self) -> List[MenuOption]:
        entries = self.keybindings.build_menu_options(
            self._select_binding,
            self._action_reset_keybindings,
            self._action_keybindings_back,
        )
        return [MenuOption(label, action) for (label, action) in entries]

    def _update_keybinding_menu_options(self) -> None:
        if self.state != "keybind_menu":
            return
        self.menu.update_options()
        self.menu.set_message(self.keybindings.menu_message())


    def _activate_menu(self, name: str, message: Optional[str] = None) -> None:
        self.state = name
        self.cheat_menu_visible = False
        self.menu.activate(name, message=message)
        if name == "post_game_menu" and self.winner:
            self.menu.title = f"{self.winner.name} Wins!"

    def _close_menu(self) -> None:
        self.menu.state = None
        self.menu.options = []
        self.menu.selection = 0
        self.menu.title = "Tanx"
        self.menu.message = None

    def _action_start_game(self) -> None:
        self._restart_match(start_in_menu=False, reset_scores=True)

    def _action_exit_game(self) -> None:
        self.running = False

    def _action_open_settings(self) -> None:
        self._activate_menu("settings_menu")
        desc = self._terrain_style_description()
        if desc:
            self.menu.set_message(f"{self._settings_instructions}\n{desc}")
        else:
            self.menu.set_message(self._settings_instructions)

    def _action_settings_back(self) -> None:
        message = None
        current_message = self.menu.message
        if current_message and current_message != self._settings_instructions:
            message = current_message
        self._activate_menu("main_menu", message=message)

    def _action_open_keybindings(self) -> None:
        self.keybindings.rebinding_target = None
        self._activate_menu("keybind_menu")
        self.menu.set_message(self.keybindings.menu_message())

    def _action_keybindings_back(self) -> None:
        self.keybindings.rebinding_target = None
        self._activate_menu("settings_menu")
        desc = self._terrain_style_description()
        if desc:
            self.menu.set_message(f"{self._settings_instructions}\n{desc}")
        else:
            self.menu.set_message(self._settings_instructions)

    def _action_reset_keybindings(self) -> None:
        self.menu.set_message(self.keybindings.reset_to_defaults())
        self.player_bindings = self.keybindings.player_bindings
        self._update_keybinding_menu_options()
        self._save_user_settings()

    def _select_binding(self, player_idx: int, field: str) -> None:
        self.menu.set_message(self.keybindings.start_rebinding(player_idx, field))
        self._update_keybinding_menu_options()

    def _finish_binding(self, key: int) -> None:
        self.menu.set_message(self.keybindings.finish_rebinding(key))
        self.player_bindings = self.keybindings.player_bindings
        self._update_keybinding_menu_options()
        self._save_user_settings()

    def _cancel_binding(self) -> None:
        self.menu.set_message(self.keybindings.cancel_rebinding())
        self._update_keybinding_menu_options()

    def _trigger_superpower(self, kind: str) -> bool:
        if self.superpowers.is_active() or self.session.is_animating_projectile():
            return False
        tank = self.session.current_tank
        if tank.super_power < 1.0:
            self.message = f"{tank.name}'s superpower is not ready"
            return False
        if not self.superpowers.activate(kind, self.current_player):
            return False
        tank.reset_super_power()
        if kind in {"bomber", "squad"}:
            self.session.superpower_active_player = self.current_player
        else:
            self.session.superpower_active_player = None
        if kind == "bomber":
            self.message = f"{tank.name} calls in a bomber strike!"
        elif kind == "squad":
            self.message = f"{tank.name} deploys an assault squad!"
        else:
            self.message = f"{tank.name} engages the targeting computer!"
        return True

    def _apply_superpower_damage(
        self,
        x_world: float,
        y_world: float,
        damage_scale: float = 1.0,
        explosion_scale: float = 1.0,
    ) -> None:
        result = ShotResult(hit_tank=None, impact_x=x_world, impact_y=y_world, path=[])
        original_damage = self.logic.damage
        scaled_damage = max(1, int(original_damage * damage_scale))
        self.logic.damage = scaled_damage
        try:
            self.logic.apply_shot_effects(result)
        finally:
            self.logic.damage = original_damage
        self.effects.spawn_explosion((x_world, y_world), explosion_scale)
        if result.fatal_hit:
            self.effects.spawn_fatal_debris(result, self.logic.tanks, self.tank_colors)

    def _action_enter_windowed_fullscreen(self) -> None:
        self._enter_windowed_fullscreen()

    def _action_cycle_resolution_forward(self) -> None:
        self._change_resolution(1)

    def _action_cycle_terrain_style_forward(self) -> None:
        self._change_terrain_style(1)

    def _action_resume_game(self) -> None:
        self.state = "playing"
        self._close_menu()

    def _action_abandon_game(self) -> None:
        self._restart_match(
            start_in_menu=True,
            message="Game abandoned.",
            reset_scores=True,
        )

    def _action_start_new_game(self) -> None:
        self._restart_match(start_in_menu=False)

    def _action_return_to_start_menu(self) -> None:
        victory_message = None
        if self.winner:
            victory_message = f"{self.winner.name} secured the round."
        self._restart_match(
            start_in_menu=True,
            message=victory_message,
            reset_scores=True,
        )

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
        collapsed_buildings = self.logic.world.update_collapsing_buildings(dt)
        collapse_events: List[tuple[List[tuple[Tank, int]], List[Tank]]] = []
        for building in collapsed_buildings:
            affected, fatalities = self.logic.handle_building_collapse(building)
            collapse_events.append((affected, fatalities))
            if self.debug:
                self._debug(
                    f"Building {building.id} collapsed at x=({building.left:.1f},{building.right:.1f})"
                )
                if affected:
                    for tank, damage in affected:
                        self._debug(f"  {tank.name} took {damage} collapse damage (hp={int(tank.hp)})")
                if fatalities:
                    names = ", ".join(tank.name for tank in fatalities)
                    self._debug(f"  Fatalities: {names}")
            self.effects.spawn_dust_column(
                (
                    (building.left + building.right) * 0.5,
                    building.base,
                ),
                scale=max(1.0, building.width * 0.4),
            )
        for affected, fatalities in collapse_events:
            self.session.on_building_collapse(affected, fatalities)
        power_finished = self.superpowers.update(dt)
        if power_finished and self.session.superpower_active_player is not None:
            self.session.complete_superpower()

        if self.superpowers.is_active():
            return

        self.session.tick_winner_delay(dt)

        if self.winner and not self._round_recorded:
            self._record_round_result()

        if self.state != "playing":
            return

        self.input.update(dt)

        if (
            self.winner
            and self.winner_delay <= 0
            and not self.session.is_animating_projectile()
        ):
            self._activate_menu("post_game_menu", message=self.message)
            return

        if not self.session.is_animating_projectile():
            return

        step = self.session.update_projectile(dt)
        for position in step.trail_positions:
            self.effects.spawn_trail(position)
        if step.finished:
            self._handle_projectile_resolution(step.result)

    def _handle_projectile_resolution(self, result: Optional[ShotResult]) -> None:
        resolved = self.session.resolve_projectile(result)
        if resolved:
            self.effects.spawn_impact_particles(resolved)
            if self.debug and resolved.hit_building is not None:
                building = resolved.hit_building
                floor_idx = resolved.hit_building_floor
                status = "unknown"
                if floor_idx is not None and 0 <= floor_idx < len(building.floors):
                    floor = building.floors[floor_idx]
                    status = "destroyed" if floor.destroyed else f"{floor.hp}/{floor.max_hp}"
                self._debug(
                    f"Projectile hit building {building.id} floor={floor_idx} status={status} unstable={building.unstable}"
                )
            elif self.debug and resolved.hit_rubble is not None:
                segment = resolved.hit_rubble
                status = "destroyed" if segment.destroyed else f"{segment.hp}/{segment.max_hp}"
                self._debug(
                    f"Projectile hit rubble {segment.id} status={status}"
                )
        if resolved and resolved.impact_x is not None and resolved.impact_y is not None:
            scale = 1.0
            if resolved.fatal_hit:
                scale = 1.8
                self.effects.spawn_fatal_debris(
                    resolved, self.logic.tanks, self.tank_colors
                )
            elif resolved.hit_tank is not None:
                scale = 1.15
            self.effects.spawn_explosion((resolved.impact_x, resolved.impact_y), scale)

    def _draw(self) -> None:
        target_surface = self.screen
        target_surface.fill((0, 0, 0))
        draw_background(self)
        draw_world(self)
        draw_rubble(self)
        draw_buildings(self)
        draw_tanks(self)
        draw_aim_indicator(self)
        draw_trails(self)
        draw_particles(self)
        draw_debris(self)
        if self.session.projectile_position:
            draw_projectile(self, self.session.projectile_position)
        draw_explosions(self)
        self.superpowers.draw(self.screen)
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
        _ = tank  # maintained for signature compatibility
        self.session.attempt_move(direction)

    def _fire_projectile(self, tank: Tank) -> None:
        result = self.session.begin_projectile(tank)
        if result.path:
            self.effects.spawn_trail(result.path[0])
        self.superpowers.consume_trajectory_preview(self.current_player)

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
        self.session.projectile_result = None
        self.session.projectile_position = None
        self.session.active_shooter = None
        self.session.superpower_active_player = None
        self.cheat_menu_visible = False
        for player in self.logic.tanks:
            player.super_power = 1.0
        self.session.check_victory()
        if self.winner:
            loser = result.fatal_tank or tank
            if result.fatal_hit:
                self.session.winner_delay = 2.0
            else:
                self.session.winner_delay = 0.0
            self.message = f"Cheat console: {loser.name} obliterated"
        else:
            self.session.winner_delay = 0.0
            self.message = f"Cheat console: {tank.name} detonated"

    def _cheat_fill_super_power(self) -> None:
        if not self.cheat_enabled:
            return
        for tank in self.logic.tanks:
            tank.super_power = 1.0
        self.menu.set_message("Cheat console: Superpower maxed")
        self.message = "Cheat console: Superpower maxed"
        self.cheat_menu_visible = False

    def _record_round_result(self) -> None:
        if self._round_recorded:
            return
        winner = self.winner
        if winner:
            for idx, tank in enumerate(self.logic.tanks):
                if tank is winner:
                    self.match_scores[idx] += 1
                    break
        self.rounds_played += 1
        self._round_recorded = True
        score_line = (
            f"Score: {self.player_names[0]} {self.match_scores[0]} - "
            f"{self.player_names[1]} {self.match_scores[1]}"
        )
        if self.message:
            self.message = f"{self.message} {score_line}"
        else:
            self.message = score_line

def run_pygame(**kwargs: object) -> None:
    """Convenience helper for launching the pygame client."""

    app = PygameTanx(**kwargs)
    app.run()
