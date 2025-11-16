"""Simple computer opponent logic for the pygame client."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from tanx_game.core.game import Game, ShotResult
from tanx_game.core.tank import Tank


@dataclass
class ShotPlan:
    """Predicted shot parameters selected by the AI planner."""

    angle: int
    power: float
    confidence: float
    prediction: ShotResult


class ShotPlanner:
    """Search turret angles and shot powers for a promising trajectory."""

    def __init__(self, angle_step: int = 3, power_step: float = 0.08) -> None:
        self.angle_step = max(1, angle_step)
        self.power_step = max(0.01, power_step)

    def find_best_shot(
        self,
        game: Game,
        shooter: Tank,
        targets: Sequence[Tank],
    ) -> Optional[ShotPlan]:
        if not targets:
            return None
        original_angle = shooter.turret_angle
        original_power = shooter.shot_power
        original_command = shooter.last_command

        best: Optional[ShotPlan] = None
        for angle in range(shooter.min_angle, shooter.max_angle + 1, self.angle_step):
            shooter.turret_angle = angle
            for power in self._power_values(shooter):
                shooter.shot_power = power
                result = game.step_projectile(shooter, apply_effects=False)
                score = self._score_result(result, targets)
                if best is None or score > best.confidence:
                    best = ShotPlan(angle=angle, power=power, confidence=score, prediction=result)
                if best and math.isclose(best.confidence, 1.0, abs_tol=1e-3):
                    break
            if best and math.isclose(best.confidence, 1.0, abs_tol=1e-3):
                break

        shooter.turret_angle = original_angle
        shooter.shot_power = original_power
        shooter.last_command = original_command

        return best

    def _power_values(self, tank: Tank) -> Iterable[float]:
        current = tank.min_power
        yield round(current, 3)
        while current < tank.max_power:
            current = min(tank.max_power, current + self.power_step)
            yield round(current, 3)

    @staticmethod
    def _score_result(result: ShotResult, targets: Sequence[Tank]) -> float:
        opponents = [tank for tank in targets if tank.alive]
        if not opponents:
            return 0.0
        if result.hit_tank and result.hit_tank in opponents:
            return 1.0
        if result.impact_x is None or result.impact_y is None:
            return 0.0
        distances = [
            math.hypot(tank.x - result.impact_x, tank.y - result.impact_y)
            for tank in opponents
        ]
        if not distances:
            return 0.0
        closest = min(distances)
        if closest <= 0.5:
            return 0.95
        return 1.0 / (1.0 + closest)


class ComputerOpponent:
    """State machine that automates Player 2 turns when enabled."""

    def __init__(
        self,
        app: "PygameTanx",
        *,
        player_index: int = 1,
        planner: Optional[ShotPlanner] = None,
    ) -> None:
        self.app = app
        self.player_index = player_index
        self.planner = planner or ShotPlanner()
        self.enabled = False
        self._turn_active = False
        self._phase = "idle"
        self._timer = 0.0
        self._plan: Optional[ShotPlan] = None
        self._rng = random.Random()

    # ------------------------------------------------------------------
    def set_enabled(self, flag: bool) -> None:
        self.enabled = flag
        if not flag:
            self.reset_turn()

    def on_new_match(self) -> None:
        self.reset_turn()

    def reset_turn(self) -> None:
        self._turn_active = False
        self._phase = "idle"
        self._timer = 0.0
        self._plan = None

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.enabled:
            return
        app = self.app
        session = app.session
        if (
            app.state != "playing"
            or app.winner is not None
            or session.is_animating_projectile()
            or app.superpowers.is_active()
            or getattr(app, "cheat_menu_visible", False)
        ):
            return
        if session.current_player != self.player_index:
            self.reset_turn()
            return
        if not self._turn_active:
            self._start_turn()
            return
        if self._phase == "thinking":
            self._timer -= dt
            if self._timer <= 0:
                self._plan = self._compute_plan()
                self._phase = "aiming"
                self._timer = self._rng.uniform(0.35, 0.6)
        elif self._phase == "aiming":
            self._timer -= dt
            if self._timer <= 0:
                self._apply_plan()
                self._phase = "firing"
                self._timer = self._rng.uniform(0.25, 0.45)
        elif self._phase == "firing":
            self._timer -= dt
            if self._timer <= 0:
                self._fire()
                self._phase = "waiting"
        elif self._phase == "waiting":
            if session.current_player != self.player_index:
                self.reset_turn()

    # ------------------------------------------------------------------
    def _start_turn(self) -> None:
        self._turn_active = True
        self._phase = "thinking"
        self._plan = None
        self._timer = self._rng.uniform(0.4, 0.9)
        tank = self.app.session.current_tank
        self.app.message = f"{tank.name}'s targeting computer calibrates sensors"

    def _compute_plan(self) -> Optional[ShotPlan]:
        tank = self.app.session.current_tank
        opponents = [
            other
            for idx, other in enumerate(self.app.logic.tanks)
            if idx != self.player_index and other.alive
        ]
        plan = self.planner.find_best_shot(self.app.logic, tank, opponents)
        if plan is None:
            self.app.message = f"{tank.name}'s AI hesitates"
        else:
            self.app.message = (
                f"{tank.name} locks angle {plan.angle}° at {plan.power:.2f}x"
            )
        return plan

    def _apply_plan(self) -> None:
        if not self._plan:
            return
        tank = self.app.session.current_tank
        tank.turret_angle = self._plan.angle
        tank.shot_power = self._plan.power
        tank.last_command = "aim"

    def _fire(self) -> None:
        tank = self.app.session.current_tank
        self.app._fire_projectile(tank)


__all__ = ["ComputerOpponent", "ShotPlan", "ShotPlanner"]
