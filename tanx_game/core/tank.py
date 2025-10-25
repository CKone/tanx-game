"""Tank entity definitions and actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tanx_game.core.world import World


@dataclass
class Tank:
    """A player-controlled tank."""

    name: str
    x: int
    y: int
    facing: int  # 1 for right, -1 for left
    hp: int = 100
    turret_angle: int = 45
    min_angle: int = -75
    max_angle: int = 75
    move_distance: int = 1
    shot_power: float = 1.0
    min_power: float = 0.4
    max_power: float = 1.8
    power_step: float = 0.1
    super_power: float = 0.0
    last_command: Optional[str] = field(default=None, init=False)

    def clamp_turret(self) -> None:
        self.turret_angle = max(self.min_angle, min(self.max_angle, self.turret_angle))

    def raise_turret(self, amount: int = 5) -> None:
        self.turret_angle += amount
        self.clamp_turret()
        self.last_command = f"turret +{amount}"

    def lower_turret(self, amount: int = 5) -> None:
        self.turret_angle -= amount
        self.clamp_turret()
        self.last_command = f"turret -{amount}"

    def increase_power(self, amount: Optional[float] = None) -> None:
        step = amount if amount is not None else self.power_step
        self.shot_power = min(self.max_power, self.shot_power + step)
        self.last_command = f"power +{step:.2f}"

    def decrease_power(self, amount: Optional[float] = None) -> None:
        step = amount if amount is not None else self.power_step
        self.shot_power = max(self.min_power, self.shot_power - step)
        self.last_command = f"power -{step:.2f}"

    def stand_y(self, world: World, x: int) -> Optional[int]:
        surface = world.surface_y(x)
        if surface is None:
            return None
        return surface

    def move(self, world: World, direction: int) -> bool:
        target_x = self.x + direction * self.move_distance
        if not 0 <= target_x < world.width:
            return False
        if world.is_column_blocked(target_x, include_rubble=False):
            return False
        surface = self.stand_y(world, target_x)
        if surface is None or surface < 0:
            return False
        if abs(surface - self.y) > 1:
            return False
        self.x = target_x
        self.y = surface
        self.last_command = "left" if direction < 0 else "right"
        return True

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def add_super_power(self, amount: float) -> None:
        self.super_power = max(0.0, min(1.0, self.super_power + amount))

    def reset_super_power(self) -> None:
        self.super_power = 0.0

    def info_line(self) -> str:
        facing_arrow = ">" if self.facing > 0 else "<"
        return (
            f"{self.name} HP:{self.hp:3d} Pos:{self.x:2d}"
            f" Angle:{self.turret_angle:3d}{facing_arrow}"
            f" Pow:{self.shot_power:4.2f}x"
        )
