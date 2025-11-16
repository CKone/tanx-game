"""Simple computer opponent logic for the pygame client."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    """Heuristic targeting helper that searches around plausible shot values."""

    def __init__(
        self,
        angle_step: int = 3,
        power_step: float = 0.08,
        samples: int = 24,
        rng: Optional[random.Random] = None,
        humanize: bool = True,
    ) -> None:
        self.angle_step = max(1, angle_step)
        self.power_step = max(0.01, power_step)
        self.samples = max(10, samples)
        self._rng = rng or random.Random(1337)
        self.humanize = humanize
        self._memory: Dict[int, Dict[str, float]] = {}
        self._experience: Dict[int, int] = {}

    def find_best_shot(
        self,
        game: Game,
        shooter: Tank,
        targets: Sequence[Tank],
    ) -> Optional[ShotPlan]:
        if not targets:
            return None
        shooter_id = id(shooter)
        original_state = (shooter.turret_angle, shooter.shot_power, shooter.last_command)
        target = self._select_primary_target(shooter, targets)
        candidates = self._generate_candidates(game, shooter, target)

        best: Optional[ShotPlan] = None
        try:
            for angle, power in candidates:
                shooter.turret_angle = angle
                shooter.shot_power = power
                result = game.step_projectile(shooter, apply_effects=False)
                score = self._score_result(result, targets)
                if best is None or score > best.confidence:
                    best = ShotPlan(angle=angle, power=power, confidence=score, prediction=result)
            if best is None or best.prediction.impact_x is None:
                fallback = self._fallback_scan(game, shooter, targets)
                if fallback is None:
                    return None
                best = fallback
            final_plan = self._apply_human_variance(game, shooter, best, targets, target)
            self._memory[shooter_id] = {
                "angle": final_plan.angle,
                "power": final_plan.power,
                "score": final_plan.confidence,
                "impact_x": final_plan.prediction.impact_x,
                "impact_y": final_plan.prediction.impact_y,
            }
            self._experience[shooter_id] = self._experience.get(shooter_id, 0) + 1
            return final_plan
        finally:
            shooter.turret_angle, shooter.shot_power, shooter.last_command = original_state

    def _select_primary_target(self, shooter: Tank, targets: Sequence[Tank]) -> Tank:
        return min(targets, key=lambda target: abs(target.x - shooter.x))

    def _generate_candidates(
        self,
        game: Game,
        shooter: Tank,
        target: Tank,
    ) -> List[Tuple[int, float]]:
        base_angle, base_power = self._estimate_baseline(game, shooter, target)
        memory = self._memory.get(id(shooter))
        suggestions: List[Tuple[float, float]] = []
        if memory:
            history_candidate = self._refine_from_history(shooter, target, memory)
            if history_candidate:
                suggestions.append(history_candidate)
            suggestions.append((memory.get("angle", base_angle), memory.get("power", base_power)))
        suggestions.append((base_angle, base_power))
        offsets = [-2, -1, 0, 1, 2]
        power_offsets = (-1, 0, 1)
        for offset in offsets:
            angle = base_angle + offset * self.angle_step
            for power_offset in power_offsets:
                suggestions.append((angle, base_power + power_offset * self.power_step))
                if len(suggestions) >= self.samples:
                    break
            if len(suggestions) >= self.samples:
                break
        while len(suggestions) < self.samples:
            jitter_angle = base_angle + self._rng.uniform(-12.0, 12.0)
            jitter_power = base_power + self._rng.uniform(-0.35, 0.35)
            suggestions.append((jitter_angle, jitter_power))
        clamped: List[Tuple[int, float]] = []
        for angle, power in suggestions[: self.samples]:
            clamped.append((self._clamp_angle(shooter, angle), self._clamp_power(shooter, power)))
        return clamped

    def _estimate_baseline(
        self,
        game: Game,
        shooter: Tank,
        target: Tank,
    ) -> Tuple[int, float]:
        dx = target.x - shooter.x
        distance = max(1.0, abs(dx))
        world_span = max(1.0, game.world.width - 1)
        normalized = min(1.1, distance / (world_span * 0.45))
        height_delta = shooter.y - target.y
        base_angle = 18.0 + normalized * 45.0 + height_delta * 0.6
        if height_delta < 0:
            base_angle += 4.0
        if dx * shooter.facing < 0:
            # Target is behind the turret; bias toward extreme angles
            base_angle = shooter.max_angle if dx > 0 else shooter.min_angle
        base_power = shooter.min_power + normalized * (shooter.max_power - shooter.min_power) * 0.85
        base_power += height_delta * 0.01
        return self._clamp_angle(shooter, base_angle), self._clamp_power(shooter, base_power)

    def _fallback_scan(
        self,
        game: Game,
        shooter: Tank,
        targets: Sequence[Tank],
    ) -> Optional[ShotPlan]:
        step = max(2, self.angle_step)
        best: Optional[ShotPlan] = None
        for angle in range(shooter.min_angle, shooter.max_angle + 1, step):
            shooter.turret_angle = angle
            for power in self._power_samples(shooter):
                shooter.shot_power = power
                result = game.step_projectile(shooter, apply_effects=False)
                if result.impact_x is None or result.impact_y is None:
                    continue
                score = self._score_result(result, targets)
                if best is None or score > best.confidence:
                    best = ShotPlan(angle=angle, power=power, confidence=score, prediction=result)
        return best

    def _power_samples(self, tank: Tank) -> Iterable[float]:
        values: List[float] = []
        current = tank.min_power
        limit = max(6, int((tank.max_power - tank.min_power) / max(self.power_step, 0.01)))
        for _ in range(limit + 1):
            values.append(round(max(tank.min_power, min(tank.max_power, current)), 3))
            current += self.power_step
            if current > tank.max_power:
                break
        if values[-1] != round(tank.max_power, 3):
            values.append(round(tank.max_power, 3))
        return values

    def _refine_from_history(
        self,
        shooter: Tank,
        target: Tank,
        memory: Dict[str, float],
    ) -> Optional[Tuple[float, float]]:
        impact_x = memory.get("impact_x")
        impact_y = memory.get("impact_y")
        if impact_x is None or impact_y is None:
            return None
        dx = target.x - impact_x
        dy = target.y - impact_y
        distance = math.hypot(dx, dy)
        if distance < 0.5:
            return memory.get("angle"), memory.get("power")
        adjust_factor = min(1.5, distance / max(3.0, abs(shooter.x - target.x) + 0.01))
        angle_delta = self.angle_step * adjust_factor * (1 if dx > 0 else -1)
        power_delta = self.power_step * adjust_factor * (1 if dx > 0 else -1)
        if abs(dy) > 4:
            angle_delta += (dy / 20.0)
        new_angle = memory.get("angle", shooter.turret_angle) + angle_delta
        new_power = memory.get("power", shooter.shot_power) + power_delta * 0.5
        return new_angle, new_power

    def _apply_human_variance(
        self,
        game: Game,
        shooter: Tank,
        plan: ShotPlan,
        targets: Sequence[Tank],
        target: Tank,
    ) -> ShotPlan:
        if not self.humanize:
            return plan
        shooter_id = id(shooter)
        experience = self._experience.get(shooter_id, 0)
        recent = self._memory.get(shooter_id)
        history_distance = 999.0
        if recent and recent.get("impact_x") is not None and recent.get("impact_y") is not None:
            history_distance = math.hypot(target.x - recent["impact_x"], target.y - recent["impact_y"])
        angle_variance = max(1.5, 10.0 - min(experience, 6) * 1.5)
        power_variance = max(0.05, 0.45 - min(experience, 6) * 0.05)
        if history_distance < 4.0:
            angle_variance *= 0.4
            power_variance *= 0.4
        uncertainty = max(0.25, 1.2 - plan.confidence)
        angle_noise = self._rng.uniform(-angle_variance, angle_variance) * uncertainty
        power_noise = self._rng.uniform(-power_variance, power_variance) * uncertainty
        angle = self._clamp_angle(shooter, plan.angle + angle_noise)
        power = self._clamp_power(shooter, plan.power + power_noise)
        if recent:
            # prevent wild swings when last attempt was close
            angle = int(
                round(
                    (angle * 0.6)
                    + (recent.get("angle", angle) * 0.4)
                )
            )
            power = round(
                power * 0.6 + recent.get("power", power) * 0.4,
                3,
            )
        shooter.turret_angle = angle
        shooter.shot_power = power
        result = game.step_projectile(shooter, apply_effects=False)
        confidence = self._score_result(result, targets)
        if result.impact_x is None or result.impact_y is None:
            return plan
        return ShotPlan(angle=angle, power=power, confidence=confidence, prediction=result)

    def _clamp_angle(self, shooter: Tank, angle: float) -> int:
        return int(max(shooter.min_angle, min(shooter.max_angle, round(angle))))

    def _clamp_power(self, shooter: Tank, power: float) -> float:
        return max(shooter.min_power, min(shooter.max_power, round(power, 3)))

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
