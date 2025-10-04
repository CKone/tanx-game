"""Pygame-powered presentation layer for the Tanx duel."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
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


@dataclass
class KeyBindings:
    """Input bindings for a player."""

    move_left: int
    move_right: int
    turret_up: int
    turret_down: int
    fire: int
    power_decrease: int
    power_increase: int


@dataclass
class Particle:
    """Simple particle used for impact effects."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    radius: float
    color: Tuple[int, int, int]


@dataclass
class Debris:
    """Larger debris chunk with rotation."""

    x: float
    y: float
    vx: float
    vy: float
    angle: float
    angular_velocity: float
    life: float
    max_life: float
    width: float
    height: float
    color: Tuple[int, int, int]


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
        self.explosion_duration = 0.45
        self.trail_duration = 0.25
        self.particle_gravity = 18.0

        self.menu_selection = 0
        self.menu_title = "Tanx - Arcade Duel"
        self.menu_message: Optional[str] = None
        self.menu_options: List[tuple[str, Callable[[], None]]] = []
        self.state = "main_menu" if start_in_menu else "playing"
        self.active_menu: Optional[str] = "main_menu" if start_in_menu else None

        self.screen = pygame.display.set_mode((640, 480))
        pygame.display.set_caption("Tanx - Arcade Duel")

        self.projectile_result: Optional[ShotResult] = None
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_position: Optional[tuple[float, float]] = None
        self.active_shooter: Optional[Tank] = None
        self.explosions: List[Tuple[tuple[float, float], float, float]] = []
        self.trail_particles: List[Tuple[tuple[float, float], float]] = []
        self.particles: List[Particle] = []
        self.debris: List[Debris] = []
        self.cheat_menu_visible = False
        self.winner: Optional[Tank] = None
        self.winner_delay = 0.0

        self.player_bindings = [
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

        self.sky_color_top = pygame.Color(78, 149, 205)
        self.sky_color_bottom = pygame.Color(19, 57, 84)
        self.ground_color = pygame.Color(87, 59, 32)
        self.tank_colors = [pygame.Color(80, 200, 120), pygame.Color(237, 85, 59)]
        self.projectile_color = pygame.Color(255, 231, 97)
        self.crater_rim_color = pygame.Color(120, 93, 63)

        self._setup_new_match(player_one, player_two, terrain_settings, seed)

        if self.state == "main_menu":
            self._activate_menu("main_menu")

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
        if self.screen.get_size() != (width, height):
            self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Tanx - Arcade Duel")

        self.current_player = 0
        self.message = f"{self.logic.tanks[0].name}'s turn"

        self.projectile_result = None
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_position = None
        self.active_shooter = None

        self.explosions = []
        self.trail_particles = []
        self.particles = []
        self.debris = []

        self.winner = None
        self.winner_delay = 0.0
        self.cheat_menu_visible = False

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
                ("Exit Game", self._action_exit_game),
            ]
        elif name == "pause_menu":
            self.menu_title = "Pause"
            self.menu_options = [
                ("Resume Game", self._action_resume_game),
                ("Abandon Game", self._action_abandon_game),
            ]
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
            elif name == "post_game_menu":
                self.menu_message = self.message

    def _handle_menu_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.state == "main_menu":
                self._action_exit_game()
            elif self.state == "pause_menu":
                self._action_resume_game()
            elif self.state == "post_game_menu":
                self._action_return_to_start_menu()
            return

        if not self.menu_options:
            return

        if key in {pygame.K_UP, pygame.K_w}:
            self.menu_selection = (self.menu_selection - 1) % len(self.menu_options)
            return
        if key in {pygame.K_DOWN, pygame.K_s}:
            self.menu_selection = (self.menu_selection + 1) % len(self.menu_options)
            return
        if key in {pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER}:
            _, action = self.menu_options[self.menu_selection]
            action()

    def _action_start_game(self) -> None:
        self._restart_match(start_in_menu=False)

    def _action_exit_game(self) -> None:
        self.running = False

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
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        if self.state in {"main_menu", "pause_menu", "post_game_menu"}:
            self._handle_menu_key(key)
            return

        if self.cheat_enabled and key == pygame.K_F1:
            if self._is_animating_projectile() or self.winner:
                return
            self.cheat_menu_visible = not self.cheat_menu_visible
            self.message = "Cheat console opened" if self.cheat_menu_visible else "Cheat console closed"
            return

        if self.cheat_menu_visible:
            if key in {pygame.K_ESCAPE, pygame.K_F1}:
                self.cheat_menu_visible = False
                self.message = "Cheat console closed"
                return
            if key == pygame.K_1:
                self._cheat_explode(0)
                return
            if key == pygame.K_2:
                self._cheat_explode(1)
                return
            return

        if self._is_animating_projectile():
            if key == pygame.K_ESCAPE:
                self._activate_menu("pause_menu")
            return

        if self.winner:
            if key == pygame.K_ESCAPE:
                self._activate_menu("post_game_menu")
            return

        if key == pygame.K_ESCAPE:
            self._activate_menu("pause_menu")
            return

        tank = self.logic.tanks[self.current_player]
        bindings = self.player_bindings[self.current_player]

        if key == bindings.move_left:
            self._attempt_move(tank, -1)
            return
        if key == bindings.move_right:
            self._attempt_move(tank, 1)
            return
        if key == bindings.turret_up:
            tank.raise_turret()
            self.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.turret_down:
            tank.lower_turret()
            self.message = f"{tank.name} turret: {tank.turret_angle}°"
            return
        if key == bindings.power_increase:
            previous = tank.shot_power
            tank.increase_power()
            if tank.shot_power == previous:
                self.message = f"{tank.name} power already max"
            else:
                self.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.power_decrease:
            previous = tank.shot_power
            tank.decrease_power()
            if tank.shot_power == previous:
                self.message = f"{tank.name} power already min"
            else:
                self.message = f"{tank.name} power: {tank.shot_power:.2f}x"
            return
        if key == bindings.fire:
            self._fire_projectile(tank)
            return

    def _update(self, dt: float) -> None:
        self._update_explosions(dt)
        self._update_trails(dt)
        self._update_particles(dt)
        self._update_debris(dt)
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
            self._spawn_trail(self.projectile_position)

    def _draw(self) -> None:
        self._draw_background()
        self._draw_world()
        self._draw_tanks()
        self._draw_trails()
        self._draw_particles()
        self._draw_debris()
        if self.projectile_position:
            self._draw_projectile(self.projectile_position)
        self._draw_explosions()
        if self.state in {"playing", "pause_menu"}:
            self._draw_ui()
        if self.state in {"main_menu", "pause_menu", "post_game_menu"}:
            self._draw_menu_overlay()
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
            self._spawn_trail(self.projectile_position)
        else:
            self.projectile_position = None
        self.message = f"{tank.name} fires!"
        self.active_shooter = tank

    def _finish_projectile(self, result: Optional[ShotResult]) -> None:
        if result:
            self.logic.apply_shot_effects(result)
            self._spawn_impact_particles(result)
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
                self._spawn_fatal_debris(result)
            elif result.hit_tank is not None:
                scale = 1.15
            self._spawn_explosion((result.impact_x, result.impact_y), scale)

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
        self._spawn_impact_particles(result)
        self._spawn_explosion((result.impact_x, result.impact_y), scale)
        if result.fatal_hit:
            self._spawn_fatal_debris(result)
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

    def _spawn_explosion(self, position: tuple[float, float], scale: float = 1.0) -> None:
        self.explosions.append((position, self.explosion_duration, scale))

    def _spawn_impact_particles(self, result: ShotResult) -> None:
        if result.impact_x is None or result.impact_y is None:
            return
        base_x = result.impact_x
        base_y = result.impact_y

        fatal = result.fatal_hit
        if result.hit_tank:
            dirt_particles = 32
            spark_particles = 18
        else:
            dirt_particles = 24
            spark_particles = 8

        if fatal:
            dirt_particles = int(dirt_particles * 1.6)
            spark_particles = int(spark_particles * 1.5) + 6

        for _ in range(dirt_particles):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            speed = random.uniform(1.2, 3.2)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.5, 1.0)
            radius = random.uniform(2.0, 4.5)
            self.particles.append(
                Particle(
                    x=base_x + random.uniform(-0.2, 0.2),
                    y=base_y + random.uniform(-0.1, 0.1),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(138, 96, 60),
                )
            )

        for _ in range(spark_particles):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(2.5, 5.5)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.35, 0.65)
            radius = random.uniform(1.0, 2.4)
            self.particles.append(
                Particle(
                    x=base_x,
                    y=base_y,
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(255, 214, 120),
                )
            )

        if fatal:
            for _ in range(6):
                angle = random.uniform(-math.pi * 0.8, -math.pi * 0.2)
                speed = random.uniform(1.0, 2.2)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                life = random.uniform(1.0, 1.6)
                radius = random.uniform(3.5, 6.0)
                self.particles.append(
                    Particle(
                        x=base_x + random.uniform(-0.3, 0.3),
                        y=base_y,
                        vx=vx,
                        vy=vy,
                        life=life,
                        max_life=life,
                        radius=radius,
                        color=(80, 78, 74),
                    )
                )

        if len(self.particles) > 240:
            self.particles = self.particles[-240:]

    def _spawn_fatal_debris(self, result: ShotResult) -> None:
        if result.fatal_tank is None:
            return
        base_x = result.impact_x if result.impact_x is not None else result.fatal_tank.x
        base_y = result.impact_y if result.impact_y is not None else result.fatal_tank.y
        tank_color = self.tank_colors[0]
        for idx, tank in enumerate(self.logic.tanks):
            if tank is result.fatal_tank:
                tank_color = self.tank_colors[idx % len(self.tank_colors)]
                break

        # Medium metal shards
        for _ in range(8):
            angle = random.uniform(-math.pi * 0.9, -math.pi * 0.1)
            speed = random.uniform(1.0, 3.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(1.4, 2.2)
            width = int(random.uniform(8, 18))
            height = int(random.uniform(4, 12))
            width = max(6, width)
            height = max(3, height)
            self.debris.append(
                Debris(
                    x=base_x + random.uniform(-0.3, 0.3),
                    y=base_y + random.uniform(-0.2, 0.2),
                    vx=vx,
                    vy=vy,
                    angle=random.uniform(0, math.tau),
                    angular_velocity=random.uniform(-4.0, 4.0),
                    life=life,
                    max_life=life,
                    width=width,
                    height=height,
                    color=(max(0, tank_color.r - 40), max(0, tank_color.g - 40), max(0, tank_color.b - 40)),
                )
            )

        # Turret chunk
        turret_speed = random.uniform(2.5, 3.6)
        turret_angle = random.uniform(-math.pi * 0.8, -math.pi * 0.2)
        self.debris.append(
            Debris(
                x=base_x,
                y=base_y,
                vx=math.cos(turret_angle) * turret_speed,
                vy=math.sin(turret_angle) * turret_speed,
                angle=random.uniform(0, math.tau),
                angular_velocity=random.uniform(-2.5, 2.5),
                life=2.8,
                max_life=2.8,
                width=int(max(12, self.cell_size * 1.1)),
                height=int(max(6, self.cell_size * 0.5)),
                color=(tank_color.r, tank_color.g, tank_color.b),
            )
        )

        if len(self.debris) > 48:
            self.debris = self.debris[-48:]

    def _update_explosions(self, dt: float) -> None:
        if not self.explosions:
            return
        updated: List[Tuple[tuple[float, float], float, float]] = []
        for pos, timer, scale in self.explosions:
            timer -= dt
            if timer > 0:
                updated.append((pos, timer, scale))
        self.explosions = updated

    def _spawn_trail(self, position: tuple[float, float]) -> None:
        self.trail_particles.append((position, self.trail_duration))

    def _update_trails(self, dt: float) -> None:
        if not self.trail_particles:
            return
        updated: List[Tuple[tuple[float, float], float]] = []
        for pos, timer in self.trail_particles:
            timer -= dt
            if timer > 0:
                updated.append((pos, timer))
        self.trail_particles = updated

    def _update_particles(self, dt: float) -> None:
        if not self.particles:
            return
        alive: List[Particle] = []
        for particle in self.particles:
            particle.life -= dt
            if particle.life <= 0:
                continue
            particle.vy += self.particle_gravity * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            if -2 <= particle.x <= self.logic.world.width + 2:
                surface = self.logic.world.ground_height(particle.x)
                if surface is not None and particle.y >= surface - 0.05:
                    gradient = 0.0
                    left = self.logic.world.ground_height(particle.x - 0.25)
                    right = self.logic.world.ground_height(particle.x + 0.25)
                    if left is not None and right is not None:
                        gradient = (right - left) * 0.3
                    particle.y = surface - 0.05
                    if particle.vy > 0:
                        particle.vy = -particle.vy * 0.25
                    particle.vx = (particle.vx + gradient) * 0.65
                    if abs(particle.vx) < 0.04:
                        particle.vx = 0.0
                    if abs(particle.vy) < 0.04:
                        particle.vy = 0.0
            alive.append(particle)
        self.particles = alive

    def _update_debris(self, dt: float) -> None:
        if not self.debris:
            return
        alive: List[Debris] = []
        for chunk in self.debris:
            chunk.life -= dt
            if chunk.life <= 0:
                continue
            chunk.vy += (self.particle_gravity * 0.6) * dt
            chunk.x += chunk.vx * dt
            chunk.y += chunk.vy * dt
            chunk.angle += chunk.angular_velocity * dt
            if -4 <= chunk.x <= self.logic.world.width + 4:
                surface = self.logic.world.ground_height(chunk.x)
                if surface is not None and chunk.y >= surface - 0.1:
                    gradient = 0.0
                    left = self.logic.world.ground_height(chunk.x - 0.4)
                    right = self.logic.world.ground_height(chunk.x + 0.4)
                    if left is not None and right is not None:
                        gradient = (right - left) * 0.4
                    chunk.y = surface - 0.1
                    if chunk.vy > 0:
                        chunk.vy = -chunk.vy * 0.35
                    chunk.vx = (chunk.vx + gradient) * 0.8
                    if abs(chunk.vx) < 0.05:
                        chunk.vx = 0.0
                    if abs(chunk.vy) < 0.05:
                        chunk.vy = 0.0
            alive.append(chunk)
        self.debris = alive

    # ------------------------------------------------------------------
    # Rendering helpers
    def _draw_background(self) -> None:
        width = self.screen.get_width()
        height = self.screen.get_height()
        for y in range(height):
            mix = y / max(height - 1, 1)
            color = pygame.Color(
                int(self.sky_color_top.r * (1 - mix) + self.sky_color_bottom.r * mix),
                int(self.sky_color_top.g * (1 - mix) + self.sky_color_bottom.g * mix),
                int(self.sky_color_top.b * (1 - mix) + self.sky_color_bottom.b * mix),
            )
            pygame.draw.line(self.screen, color, (0, y), (width, y))

    def _draw_world(self) -> None:
        world = self.logic.world
        detail = world.detail
        offset_y = self.ui_height
        bottom = world.height * self.cell_size + offset_y

        surface_points: List[tuple[int, int]] = []
        for hx in range(world.grid_width):
            x_world = hx / detail
            height = world.height_map[hx]
            x_pix = int(round(x_world * self.cell_size))
            y_pix = int(round(height * self.cell_size + offset_y))
            surface_points.append((x_pix, y_pix))

        if not surface_points:
            return

        light = pygame.math.Vector2(-0.35, -1.0)
        if light.length_squared() > 0:
            light = light.normalize()
        rock_color = pygame.Color(110, 112, 118)
        soil_color = pygame.Color(165, 126, 76)
        grass_color = pygame.Color(104, 164, 92)
        grass_thickness_px = int(self.cell_size * 0.45)
        soil_thickness_px = int(self.cell_size * 1.6)

        def shade(col: pygame.Color, factor: float) -> Tuple[int, int, int]:
            return (
                min(255, max(0, int(col.r * factor))),
                min(255, max(0, int(col.g * factor))),
                min(255, max(0, int(col.b * factor))),
            )

        for idx in range(len(surface_points) - 1):
            x0, y0 = surface_points[idx]
            x1, y1 = surface_points[idx + 1]
            if x0 == x1:
                continue
            h0 = world.height_map[idx]
            h1 = world.height_map[min(idx + 1, len(world.height_map) - 1)]
            dx = (1.0 / detail)
            dy = h1 - h0
            tangent = pygame.math.Vector2(dx, dy)
            if tangent.length_squared() == 0:
                tangent = pygame.math.Vector2(0.0, 1.0)
            normal = pygame.math.Vector2(-tangent.y, tangent.x)
            if normal.length_squared() == 0:
                normal = pygame.math.Vector2(0.0, 1.0)
            normal = normal.normalize()
            shade_factor = 0.35 + 0.65 * max(0.0, normal.dot(light))

            rock_poly = [(x0, y0), (x1, y1), (x1, bottom), (x0, bottom)]
            rock_col = shade(rock_color, shade_factor)
            pygame.gfxdraw.filled_polygon(self.screen, rock_poly, rock_col)
            pygame.gfxdraw.aapolygon(self.screen, rock_poly, rock_col)

            soil_col = shade(soil_color, shade_factor)
            soil_poly = [
                (x0, y0),
                (x1, y1),
                (x1, min(bottom, y1 + soil_thickness_px)),
                (x0, min(bottom, y0 + soil_thickness_px)),
            ]
            pygame.gfxdraw.filled_polygon(self.screen, soil_poly, soil_col)
            pygame.gfxdraw.aapolygon(self.screen, soil_poly, soil_col)

            grass_col = shade(grass_color, shade_factor)
            grass_poly = [
                (x0, y0),
                (x1, y1),
                (x1, min(bottom, y1 + grass_thickness_px)),
                (x0, min(bottom, y0 + grass_thickness_px)),
            ]
            pygame.gfxdraw.filled_polygon(self.screen, grass_poly, grass_col)
            pygame.gfxdraw.aapolygon(self.screen, grass_poly, grass_col)

        # Draw iso-line for the terrain surface.
        pygame.draw.aalines(self.screen, self.crater_rim_color, False, surface_points, blend=1)

    def _draw_tanks(self) -> None:
        offset_y = self.ui_height
        turret_length = self.cell_size * 0.8
        for idx, tank in enumerate(self.logic.tanks):
            if not tank.alive:
                continue
            color = self.tank_colors[idx % len(self.tank_colors)]
            x = tank.x * self.cell_size
            y = tank.y * self.cell_size + offset_y
            body_rect = pygame.Rect(x, y, self.cell_size, self.cell_size)
            pygame.draw.rect(self.screen, color, body_rect, border_radius=6)

            center_x = x + self.cell_size / 2
            center_y = y + self.cell_size / 2
            angle = math.radians(tank.turret_angle)
            dx = math.cos(angle) * turret_length * tank.facing
            dy = -math.sin(angle) * turret_length
            end_pos = (center_x + dx, center_y + dy)
            pygame.draw.line(
                self.screen,
                pygame.Color("black"),
                (center_x, center_y - self.cell_size * 0.25),
                end_pos,
                4,
            )

    def _draw_projectile(self, position: tuple[float, float]) -> None:
        offset_y = self.ui_height
        px = position[0] * self.cell_size
        py = position[1] * self.cell_size + offset_y
        pygame.draw.circle(
            self.screen,
            self.projectile_color,
            (int(px), int(py)),
            max(3, self.cell_size // 4),
        )

    def _draw_trails(self) -> None:
        if not self.trail_particles:
            return
        offset_y = self.ui_height
        for (x, y), timer in self.trail_particles:
            intensity = max(0.0, min(timer / self.trail_duration, 1.0))
            radius = max(2, int(self.cell_size * 0.25 * intensity + 1))
            alpha = int(180 * intensity)
            surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                surface,
                (255, 240, 150, alpha),
                (radius, radius),
                radius,
            )
            screen_x = x * self.cell_size - radius
            screen_y = y * self.cell_size + offset_y - radius
            self.screen.blit(surface, (screen_x, screen_y))

    def _draw_particles(self) -> None:
        if not self.particles:
            return
        offset_y = self.ui_height
        for particle in self.particles:
            alpha = max(0, min(255, int(255 * (particle.life / particle.max_life))))
            if alpha <= 0:
                continue
            color = pygame.Color(*particle.color, alpha)
            px = int(particle.x * self.cell_size)
            py = int(particle.y * self.cell_size + offset_y)
            radius = max(1, int(particle.radius))
            pygame.draw.circle(self.screen, color, (px, py), radius)

    def _draw_debris(self) -> None:
        if not self.debris:
            return
        offset_y = self.ui_height
        for chunk in self.debris:
            alpha = max(0, min(255, int(255 * (chunk.life / chunk.max_life))))
            if alpha <= 0:
                continue
            surface = pygame.Surface((chunk.width, chunk.height), pygame.SRCALPHA)
            surface.fill((*chunk.color, alpha))
            rotated = pygame.transform.rotate(surface, math.degrees(chunk.angle))
            rect = rotated.get_rect()
            rect.center = (
                chunk.x * self.cell_size,
                chunk.y * self.cell_size + offset_y,
            )
            self.screen.blit(rotated, rect)

    def _draw_explosions(self) -> None:
        if not self.explosions:
            return
        offset_y = self.ui_height
        for (x, y), timer, scale in self.explosions:
            progress = 1 - min(max(timer / self.explosion_duration, 0.0), 1.0)
            radius = self.cell_size * (1.2 + progress * 1.3) * scale
            alpha = int(200 * (1 - progress))
            overlay = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(
                overlay,
                (255, 160, 64, max(60, alpha)),
                (int(radius), int(radius)),
                int(radius),
            )
            pygame.draw.circle(
                overlay,
                (255, 230, 120, 220),
                (int(radius), int(radius)),
                max(2, int(radius * 0.6)),
            )
            screen_x = x * self.cell_size - radius
            screen_y = y * self.cell_size + offset_y - radius
            self.screen.blit(overlay, (screen_x, screen_y))

    def _draw_menu_overlay(self) -> None:
        if self.state not in {"main_menu", "pause_menu", "post_game_menu"}:
            return
        alpha = 200 if self.state == "main_menu" else 160
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2

        title_surface = self.font_large.render(self.menu_title, True, pygame.Color("white"))
        title_rect = title_surface.get_rect(center=(center_x, center_y - 120))
        self.screen.blit(title_surface, title_rect)

        if self.menu_message:
            message_surface = self.font_regular.render(self.menu_message, True, pygame.Color(220, 220, 220))
            message_rect = message_surface.get_rect(center=(center_x, title_rect.bottom + 36))
            self.screen.blit(message_surface, message_rect)
            options_start_y = message_rect.bottom + 24
        else:
            options_start_y = title_rect.bottom + 32

        for idx, (label, _) in enumerate(self.menu_options):
            is_selected = idx == self.menu_selection
            color = pygame.Color("white") if is_selected else pygame.Color(200, 200, 200)
            text_surface = self.font_regular.render(label, True, color)
            text_rect = text_surface.get_rect(center=(center_x, options_start_y + idx * 40))
            if is_selected:
                highlight = pygame.Surface((text_rect.width + 36, text_rect.height + 12), pygame.SRCALPHA)
                highlight.fill((255, 255, 255, 50))
                highlight_rect = highlight.get_rect(center=text_rect.center)
                self.screen.blit(highlight, highlight_rect)
            self.screen.blit(text_surface, text_rect)

        footer_text = None
        if self.state == "main_menu":
            footer_text = "Esc exits the game"
        elif self.state == "pause_menu":
            footer_text = "Esc resumes"
        elif self.state == "post_game_menu":
            footer_text = "Esc returns to the start menu"

        if footer_text:
            footer_surface = self.font_small.render(footer_text, True, pygame.Color(180, 180, 180))
            footer_rect = footer_surface.get_rect(center=(center_x, self.screen.get_height() - 36))
            self.screen.blit(footer_surface, footer_rect)

    def _draw_ui(self) -> None:
        tank_panel = " | ".join(tank.info_line() for tank in self.logic.tanks)
        panel_surface = self.font_regular.render(tank_panel, True, pygame.Color("white"))
        message_surface = self.font_regular.render(self.message, True, pygame.Color("white"))

        panel_bg = pygame.Rect(0, 0, self.screen.get_width(), self.ui_height)
        pygame.draw.rect(self.screen, pygame.Color(0, 0, 0, 180), panel_bg)

        self.screen.blit(panel_surface, (16, 16))
        self.screen.blit(message_surface, (16, 48))

        instructions = [
            "Player 1: A/D move, W/S aim, Space fire, Q/E power",
            "Player 2: ←/→ move, ↑/↓ aim, Enter fire, [/ ] power",
            "Esc opens the pause menu",
        ]
        if self.cheat_enabled:
            instructions.append("F1 toggles the cheat console")
        for idx, line in enumerate(instructions):
            text_surface = self.font_small.render(line, True, pygame.Color(200, 200, 200))
            self.screen.blit(text_surface, (16, 76 + idx * 18))

        if self.cheat_enabled and self.cheat_menu_visible:
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))
            menu_lines = [
                "Cheat Console",
                "1 - Detonate Player 1",
                "2 - Detonate Player 2",
                "F1 / Esc - Close",
            ]
            for idx, line in enumerate(menu_lines):
                font = self.font_large if idx == 0 else self.font_regular
                text_surface = font.render(line, True, pygame.Color("white"))
                rect = text_surface.get_rect(
                    center=(self.screen.get_width() / 2, self.screen.get_height() / 2 + idx * 36)
                )
                self.screen.blit(text_surface, rect)


def run_pygame(**kwargs: object) -> None:
    """Convenience helper for launching the pygame client."""

    app = PygameTanx(**kwargs)
    app.run()
