"""Pygame-powered presentation layer for the Tanx duel."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    import pygame
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
    ) -> None:
        pygame.init()
        pygame.font.init()

        self.logic = Game(player_one, player_two, terrain_settings, seed)
        self.cell_size = cell_size
        self.ui_height = ui_height
        self.world_width = self.logic.world.width
        self.world_height = self.logic.world.height

        width = self.world_width * self.cell_size
        height = self.world_height * self.cell_size + self.ui_height

        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Tanx - Arcade Duel")

        self.clock = pygame.time.Clock()
        self.running = True
        self.current_player = 0
        self.message = f"{self.logic.tanks[0].name}'s turn"

        self.projectile_result: Optional[ShotResult] = None
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_interval = 0.03
        self.projectile_position: Optional[tuple[float, float]] = None
        self.active_shooter: Optional[Tank] = None

        self.explosions: List[Tuple[tuple[float, float], float, float]] = []
        self.explosion_duration = 0.45
        self.trail_particles: List[Tuple[tuple[float, float], float]] = []
        self.trail_duration = 0.25
        self.particles: List[Particle] = []
        self.particle_gravity = 18.0
        self.debris: List[Debris] = []
        self.cheat_enabled = cheat_enabled
        self.cheat_menu_visible = False

        self.winner: Optional[Tank] = None
        self.winner_delay = 0.0

        self.font_small = pygame.font.SysFont("consolas", 16)
        self.font_regular = pygame.font.SysFont("consolas", 20)
        self.font_large = pygame.font.SysFont(None, 48)

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
        if self.cheat_enabled and key == pygame.K_F1:
            if self._is_animating_projectile():
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

        if self.winner or self._is_animating_projectile():
            if key == pygame.K_ESCAPE:
                self.running = False
            elif key in {pygame.K_r, pygame.K_F5} and self.winner:
                self._reset()
            return

        if key == pygame.K_ESCAPE:
            self.running = False
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
        self._draw_ui()
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
    # ------------------------------------------------------------------
    # Utilities
    def _reset(self) -> None:
        player_names = [tank.name for tank in self.logic.tanks]
        settings = self.logic.world.settings
        self.__init__(
            player_one=player_names[0],
            player_two=player_names[1],
            terrain_settings=settings,
            seed=settings.seed,
            cell_size=self.cell_size,
            ui_height=self.ui_height,
            cheat_enabled=self.cheat_enabled,
        )

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
        offset_y = self.ui_height
        for y, row in enumerate(self.logic.world.grid):
            for x, solid in enumerate(row):
                if solid:
                    rect = pygame.Rect(
                        x * self.cell_size,
                        y * self.cell_size + offset_y,
                        self.cell_size,
                        self.cell_size,
                    )
                    pygame.draw.rect(self.screen, self.ground_color, rect)
                elif self._neighboring_solid(x, y):
                    rim_rect = pygame.Rect(
                        x * self.cell_size,
                        y * self.cell_size + offset_y,
                        self.cell_size,
                        self.cell_size,
                    )
                    pygame.draw.rect(self.screen, self.crater_rim_color, rim_rect, width=1)

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

    def _neighboring_solid(self, x: int, y: int) -> bool:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx = x + dx
            ny = y + dy
            if 0 <= nx < self.logic.world.width and 0 <= ny < self.logic.world.height:
                if self.logic.world.grid[ny][nx]:
                    return True
        return False

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
            "Esc to quit",
            "R to restart once the duel ends",
        ]
        if self.cheat_enabled:
            instructions.append("F1: open cheat console")
        for idx, line in enumerate(instructions):
            text_surface = self.font_small.render(line, True, pygame.Color(200, 200, 200))
            self.screen.blit(text_surface, (16, 76 + idx * 18))

        if self.winner:
            if self.winner_delay <= 0:
                overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 140))
                self.screen.blit(overlay, (0, 0))
                win_text = f"{self.winner.name} Wins!"
                text_surface = self.font_large.render(win_text, True, pygame.Color("white"))
                rect = text_surface.get_rect(center=(self.screen.get_width() / 2, self.ui_height / 2))
                self.screen.blit(text_surface, rect)
                prompt_surface = self.font_regular.render("Press R to restart or Esc to quit", True, pygame.Color("white"))
                prompt_rect = prompt_surface.get_rect(
                    center=(self.screen.get_width() / 2, self.ui_height / 2 + 48)
                )
                self.screen.blit(prompt_surface, prompt_rect)
        elif self.cheat_enabled and self.cheat_menu_visible:
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
