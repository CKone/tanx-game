"""Pygame-powered presentation layer for the Tanx duel."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

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

        self.winner: Optional[Tank] = None

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

    def _draw(self) -> None:
        self._draw_background()
        self._draw_world()
        self._draw_tanks()
        if self.projectile_position:
            self._draw_projectile(self.projectile_position)
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
        result = self.logic.step_projectile(tank)
        self.projectile_result = result
        self.projectile_index = 0
        self.projectile_timer = 0.0
        if result.path:
            self.projectile_position = result.path[0]
        else:
            self.projectile_position = None
        self.message = f"{tank.name} fires!"

    def _finish_projectile(self, result: Optional[ShotResult]) -> None:
        if result and result.hit_tank:
            self.message = f"Direct hit on {result.hit_tank.name}!"
        elif result and result.impact_x is not None:
            self.message = "Shot impacted the terrain."
        else:
            self.message = "Shot flew off into the distance."

        self._advance_turn()
        self._check_victory()
        if not self.winner:
            self.message += f" Next: {self.logic.tanks[self.current_player].name}'s turn"

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
        )

    def _advance_turn(self) -> None:
        self.current_player = 1 - self.current_player

    def _check_victory(self) -> None:
        alive = [tank for tank in self.logic.tanks if tank.alive]
        if len(alive) == 1:
            self.winner = alive[0]
            loser = next(t for t in self.logic.tanks if t is not self.winner)
            self.message = f"{self.winner.name} wins! {loser.name} is destroyed."

    def _is_animating_projectile(self) -> bool:
        return self.projectile_result is not None

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
        for idx, line in enumerate(instructions):
            text_surface = self.font_small.render(line, True, pygame.Color(200, 200, 200))
            self.screen.blit(text_surface, (16, 76 + idx * 18))

        if self.winner:
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


def run_pygame(**kwargs: object) -> None:
    """Convenience helper for launching the pygame client."""

    app = PygameTanx(**kwargs)
    app.run()
