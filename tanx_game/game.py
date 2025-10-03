"""Interactive text-based game loop for Tanx."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from .tank import Tank
from .world import TerrainSettings, World


@dataclass
class ShotResult:
    """Information about the projectile simulation."""

    hit_tank: Optional[Tank]
    impact_x: Optional[float]
    impact_y: Optional[float]
    path: List[tuple]


class Game:
    """Text-based artillery duel between two tanks."""

    def __init__(
        self,
        player_one: str = "Player 1",
        player_two: str = "Player 2",
        settings: Optional[TerrainSettings] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.world = World(settings or TerrainSettings(seed=seed))
        self.tanks = self._spawn_tanks(player_one, player_two)
        self.gravity = 0.35
        self.projectile_speed = 6.5
        self.damage = 25
        self.explosion_radius = 1.8
        self.projectile_time_step = 0.1

    def _spawn_tanks(self, player_one: str, player_two: str) -> List[Tank]:
        left_x, left_y = self._find_spawn(2, 1)
        right_x, right_y = self._find_spawn(self.world.width - 3, -1)
        return [
            Tank(player_one, left_x, left_y, facing=1, turret_angle=45),
            Tank(player_two, right_x, right_y, facing=-1, turret_angle=45),
        ]

    def _find_spawn(self, start: int, step: int) -> tuple[int, int]:
        x = start
        while 0 <= x < self.world.width:
            surface = self.world.surface_y(x)
            if surface is not None and surface >= 0:
                return x, surface
            x += step
        raise RuntimeError("Failed to find spawn positions for tanks")

    # Rendering -----------------------------------------------------------------
    def render(self, projectile: Optional[tuple] = None) -> str:
        grid = self.world.copy_grid()
        for tank in self.tanks:
            if tank.alive and 0 <= tank.y < self.world.height:
                grid[tank.y][tank.x] = "T" if tank.facing > 0 else "t"
        if projectile:
            px, py = projectile
            if 0 <= int(py) < self.world.height and 0 <= int(px) < self.world.width:
                grid[int(py)][int(px)] = "*"
        lines = ["".join(row) for row in grid]
        return "\n".join(lines)

    def info_panel(self) -> str:
        return " | ".join(tank.info_line() for tank in self.tanks)

    # Input ---------------------------------------------------------------------
    def command_help(self) -> str:
        return (
            "Commands: left, right, up, down, fire, status, help, quit\n"
            "  left/right: move the tank\n"
            "  up/down: adjust turret angle\n"
            "  power+/power-: adjust shot force\n"
            "  fire: shoot a projectile\n"
            "  status: display tank stats"
        )

    def parse_command(self, command: str) -> str:
        return command.strip().lower()

    # Simulation ----------------------------------------------------------------
    def step_projectile(self, shooter: Tank) -> ShotResult:
        angle_deg = shooter.turret_angle
        direction = shooter.facing
        angle_rad = math.radians(angle_deg)
        speed = self.projectile_speed * shooter.shot_power
        vx = math.cos(angle_rad) * speed * direction
        vy = -math.sin(angle_rad) * speed
        x = shooter.x + 0.5 + direction * 0.6
        y = shooter.y - 0.5
        path: List[tuple] = []
        hit_tank: Optional[Tank] = None
        impact_x: Optional[float] = None
        impact_y: Optional[float] = None
        dt = self.projectile_time_step
        for _ in range(360):
            x += vx * dt
            y += vy * dt
            vy += self.gravity * dt
            path.append((x, y))
            if x < 0 or x >= self.world.width or y >= self.world.height:
                break
            if y < 0:
                continue
            ix = int(round(x))
            iy = int(round(y))
            for tank in self.tanks:
                if not tank.alive or tank is shooter:
                    continue
                if abs(tank.x - x) <= 0.6 and abs(tank.y - y) <= 0.6:
                    hit_tank = tank
                    impact_x, impact_y = x, y
                    break
            if hit_tank:
                break
            if self.world.is_solid(ix, iy):
                impact_x, impact_y = x, y
                break
        if impact_x is not None and impact_y is not None:
            self.world.carve_circle(impact_x, impact_y, self.explosion_radius)
        if hit_tank:
            hit_tank.take_damage(self.damage)
        elif impact_x is not None and impact_y is not None:
            for tank in self.tanks:
                if tank.alive and abs(tank.x - impact_x) <= 1.0 and abs(tank.y - impact_y) <= 1.0:
                    tank.take_damage(self.damage // 2)
        for tank in self.tanks:
            if not tank.alive:
                continue
            self.settle_tank(tank)
        return ShotResult(hit_tank, impact_x, impact_y, path)

    # Game loop -----------------------------------------------------------------
    def play(self) -> None:
        os.system("clear")
        print("Tanx - Text Artillery Duel")
        print(self.command_help())
        current = 0
        while all(tank.alive for tank in self.tanks):
            shooter = self.tanks[current]
            print("\n" + self.render())
            print(self.info_panel())
            print(f"It's {shooter.name}'s turn. Last action: {shooter.last_command}")
            command = self.parse_command(input("> "))
            if command in {"quit", "exit"}:
                print("Game aborted.")
                return
            if command in {"help", "?"}:
                print(self.command_help())
                continue
            if command == "status":
                print(self.info_panel())
                continue
            if command in {"left", "l"}:
                if not shooter.move(self.world, -1):
                    print("Cannot move left.")
                else:
                    current = 1 - current
                continue
            if command in {"right", "r"}:
                if not shooter.move(self.world, 1):
                    print("Cannot move right.")
                else:
                    current = 1 - current
                continue
            if command in {"up", "u"}:
                shooter.raise_turret()
                continue
            if command in {"down", "d"}:
                shooter.lower_turret()
                continue
            if command in {"power+", "p+", "powerup", "+"}:
                before = shooter.shot_power
                shooter.increase_power()
                if shooter.shot_power == before:
                    print("Power already at maximum.")
                else:
                    print(f"Shot power increased to {shooter.shot_power:.2f}x")
                continue
            if command in {"power-", "p-", "powerdown", "-"}:
                before = shooter.shot_power
                shooter.decrease_power()
                if shooter.shot_power == before:
                    print("Power already at minimum.")
                else:
                    print(f"Shot power decreased to {shooter.shot_power:.2f}x")
                continue
            if command == "fire":
                result = self.step_projectile(shooter)
                self.animate_projectile(result)
                current = 1 - current
                continue
            print("Unknown command. Type 'help' for a list of commands.")
        winner = next(tank for tank in self.tanks if tank.alive)
        loser = next(tank for tank in self.tanks if not tank.alive)
        print("\n" + self.render())
        print(self.info_panel())
        print(f"{winner.name} wins! {loser.name} has been destroyed.")

    def animate_projectile(self, result: ShotResult) -> None:
        for position in result.path:
            os.system("clear")
            print("Tanx - Text Artillery Duel")
            print(self.render(projectile=position))
            print(self.info_panel())
            time.sleep(0.05)
        os.system("clear")
        print("Tanx - Text Artillery Duel")
        print(self.render())
        print(self.info_panel())
        if result.hit_tank:
            print(f"Direct hit on {result.hit_tank.name}!")
        elif result.impact_x is not None:
            print("The shot impacted the terrain.")
        else:
            print("The shot flew off into the distance.")

    def settle_tank(self, tank: Tank) -> None:
        """Allow a tank to fall if the terrain beneath has been destroyed."""

        while tank.y + 1 < self.world.height and not self.world.is_solid(
            tank.x, tank.y + 1
        ):
            tank.y += 1
        surface = self.world.surface_y(tank.x)
        if surface is None:
            return
        if surface < 0:
            tank.y = 0
        elif surface < tank.y:
            tank.y = surface
