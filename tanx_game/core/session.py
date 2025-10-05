"""Game session management decoupled from rendering concerns."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from tanx_game.core.game import Game, ShotResult
from tanx_game.core.tank import Tank


@dataclass
class ProjectileStep:
    """Incremental update for a projectile animation."""

    trail_positions: List[tuple[float, float]] = field(default_factory=list)
    finished: bool = False
    result: Optional[ShotResult] = None


class GameSession:
    """Own the mutable state of an active Tanx match."""

    def __init__(self, game: Game, *, projectile_interval: float = 0.03) -> None:
        self.game = game
        self.projectile_interval = projectile_interval

        self.current_player = 0
        self.message = f"{self.game.tanks[self.current_player].name}'s turn"

        self.projectile_result: Optional[ShotResult] = None
        self.projectile_timer = 0.0
        self.projectile_index = 0
        self.projectile_position: Optional[tuple[float, float]] = None

        self.active_shooter: Optional[Tank] = None
        self.superpower_active_player: Optional[int] = None

        self.winner: Optional[Tank] = None
        self.winner_delay = 0.0

    # ------------------------------------------------------------------
    # Properties
    @property
    def tanks(self) -> Sequence[Tank]:
        return self.game.tanks

    @property
    def current_tank(self) -> Tank:
        return self.game.tanks[self.current_player]

    def is_animating_projectile(self) -> bool:
        return self.projectile_result is not None

    # ------------------------------------------------------------------
    # Turn helpers
    def advance_turn(self) -> None:
        self.current_player = 1 - self.current_player

    def check_victory(self) -> None:
        alive = [tank for tank in self.game.tanks if tank.alive]
        if len(alive) == 1:
            self.winner = alive[0]
            loser = next(t for t in self.game.tanks if t is not self.winner)
            self.message = f"{self.winner.name} wins! {loser.name} is destroyed."
        elif len(alive) == 0:
            self.winner = None
            self.message = "Both tanks destroyed!"

    def tick_winner_delay(self, dt: float) -> None:
        if self.winner and self.winner_delay > 0:
            self.winner_delay = max(0.0, self.winner_delay - dt)

    # ------------------------------------------------------------------
    # Player actions
    def attempt_move(self, direction: int) -> bool:
        tank = self.current_tank
        if tank.move(self.game.world, direction):
            direction_text = "left" if direction < 0 else "right"
            self.advance_turn()
            self.message = (
                f"{tank.name} moved {direction_text}. "
                f"Next: {self.current_tank.name}'s turn"
            )
            self.check_victory()
            return True
        self.message = f"{tank.name} cannot move that way"
        return False

    def begin_projectile(self, tank: Tank) -> ShotResult:
        tank.last_command = "fire"
        result = self.game.step_projectile(tank, apply_effects=False)
        self.projectile_result = result
        self.projectile_index = 0
        self.projectile_timer = 0.0
        self.projectile_position = result.path[0] if result.path else None
        self.active_shooter = tank
        self.message = f"{tank.name} fires!"
        return result

    def update_projectile(self, dt: float) -> ProjectileStep:
        step = ProjectileStep()
        if self.projectile_result is None:
            return step
        self.projectile_timer += dt
        path = self.projectile_result.path
        while self.projectile_timer >= self.projectile_interval:
            self.projectile_timer -= self.projectile_interval
            self.projectile_index += 1
            if self.projectile_index >= len(path):
                result = self.projectile_result
                self.projectile_result = None
                self.projectile_position = None
                step.finished = True
                step.result = result
                return step
            position = path[self.projectile_index]
            self.projectile_position = position
            step.trail_positions.append(position)
        return step

    def resolve_projectile(self, result: Optional[ShotResult]) -> Optional[ShotResult]:
        if result:
            self.game.apply_shot_effects(result)
        if result and result.hit_tank:
            self.message = f"Direct hit on {result.hit_tank.name}!"
        elif result and result.impact_x is not None:
            self.message = "Shot impacted the terrain."
        else:
            self.message = "Shot flew off into the distance."

        self.active_shooter = None

        shooter = self.game.tanks[self.current_player]
        self._update_super_power(shooter, result)

        self.advance_turn()
        self.check_victory()
        if self.winner:
            if result and result.fatal_hit:
                self.winner_delay = 2.0
            else:
                self.winner_delay = 0.0
        else:
            self.winner_delay = 0.0
            self.message += (
                f" Next: {self.game.tanks[self.current_player].name}'s turn"
            )
        return result

    def complete_superpower(self) -> None:
        self.superpower_active_player = None
        self.advance_turn()
        self.check_victory()
        if not self.winner:
            self.message = (
                f"Next: {self.game.tanks[self.current_player].name}'s turn"
            )
        self.winner_delay = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    def _update_super_power(
        self, shooter: Tank, result: Optional[ShotResult]
    ) -> None:
        base_gain = 0.08
        bonus = 0.0

        opponents = [tank for tank in self.game.tanks if tank is not shooter and tank.alive]

        if result and result.hit_tank and result.hit_tank is not shooter:
            bonus = 0.75
        elif result and result.impact_x is not None and opponents:
            distances = [
                math.hypot(
                    tank.x - result.impact_x,
                    tank.y - (result.impact_y if result.impact_y is not None else tank.y),
                )
                for tank in opponents
            ]
            min_dist = min(distances)
            if min_dist <= 0.5:
                bonus = 0.6
            else:
                falloff = max(0.0, (6.0 - min_dist) / 6.0)
                bonus = 0.45 * (falloff ** 2)
        else:
            bonus = 0.0

        shooter.add_super_power(base_gain + bonus)


__all__ = ["GameSession", "ProjectileStep"]
