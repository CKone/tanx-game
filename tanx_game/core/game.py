"""Interactive text-based game loop for Tanx."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from tanx_game.core.tank import Tank
from tanx_game.core.world import Building, RubbleSegment, TerrainSettings, World


@dataclass
class ShotResult:
    """Information about the projectile simulation."""

    hit_tank: Optional[Tank]
    impact_x: Optional[float]
    impact_y: Optional[float]
    path: List[tuple]
    fatal_hit: bool = False
    fatal_tank: Optional[Tank] = None
    hit_building: Optional[Building] = None
    hit_building_floor: Optional[int] = None
    hit_rubble: Optional[RubbleSegment] = None


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
        self.crater_size = 4
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
            if (
                surface is not None
                and surface >= 0
                and not self.world.is_column_blocked(x)
            ):
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
    def step_projectile(self, shooter: Tank, apply_effects: bool = True) -> ShotResult:
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
        hit_building: Optional[Building] = None
        hit_floor: Optional[int] = None
        hit_rubble: Optional[RubbleSegment] = None
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
            building_hit = self.world.building_hit_test(x, y)
            if building_hit:
                hit_building, hit_floor = building_hit
                impact_x, impact_y = x, y
                break
            rubble_hit = self.world.rubble_hit_test(x, y)
            if rubble_hit:
                hit_rubble = rubble_hit
                impact_x, impact_y = x, y
                break
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
        result = ShotResult(
            hit_tank=hit_tank,
            impact_x=impact_x,
            impact_y=impact_y,
            path=path,
            hit_building=hit_building,
            hit_building_floor=hit_floor,
            hit_rubble=hit_rubble,
        )
        if apply_effects:
            self.apply_shot_effects(result)
        return result

    def apply_shot_effects(self, result: ShotResult) -> None:
        impact_x, impact_y = result.impact_x, result.impact_y
        if result.hit_building is not None and impact_x is not None and impact_y is not None:
            self._apply_building_damage(result)
        elif result.hit_rubble is not None and impact_x is not None and impact_y is not None:
            self._apply_rubble_damage(result)
        elif impact_x is not None and impact_y is not None and result.hit_tank is None:
            self.world.carve_circle(impact_x, impact_y, self.explosion_radius)
        fatal_tank: Optional[Tank] = None
        if result.hit_tank:
            tank = result.hit_tank
            was_alive = tank.alive
            tank.take_damage(self.damage)
            if was_alive and not tank.alive:
                fatal_tank = tank
        elif impact_x is not None and impact_y is not None:
            splash_fatal = self._apply_splash_damage(impact_x, impact_y)
            if splash_fatal is not None:
                fatal_tank = splash_fatal
        for tank in self.tanks:
            if not tank.alive:
                continue
            self.settle_tank(tank)
        result.fatal_hit = fatal_tank is not None
        result.fatal_tank = fatal_tank

    def _apply_building_damage(self, result: ShotResult) -> None:
        building = result.hit_building
        if building is None or result.hit_building_floor is None:
            return
        floor_idx = result.hit_building_floor
        if not (0 <= floor_idx < len(building.floors)):
            return
        floor = building.floors[floor_idx]
        if floor.destroyed:
            return
        floor.damage(self.damage)
        if floor.destroyed:
            if floor_idx < len(building.floors) - 1:
                for upper_idx in range(floor_idx + 1, len(building.floors)):
                    upper_floor = building.floors[upper_idx]
                    if not upper_floor.destroyed:
                        upper_floor.hp = 0
                        upper_floor.destroyed = True
            intact_remaining = building.first_intact_floor_index()
            if intact_remaining is None:
                self.world.schedule_building_collapse(building, delay=0.8)
            elif floor_idx <= intact_remaining:
                building.unstable = True
                if floor_idx == 0:
                    self.world.schedule_building_collapse(building, delay=1.2)

    def _apply_rubble_damage(self, result: ShotResult) -> None:
        segment = result.hit_rubble
        if segment is None:
            return
        self.world.damage_rubble(segment, self.damage)

    def handle_building_collapse(self, building: Building) -> tuple[List[tuple[Tank, int]], List[Tank]]:
        affected: List[tuple[Tank, int]] = []
        fatalities: List[Tank] = []
        center = (building.left + building.right) * 0.5
        half_span = building.width * 0.5
        influence = half_span + 1.5
        base_damage = max(self.damage, int(self.damage * (1.1 + 0.15 * len(building.floors))))
        for tank in self.tanks:
            if not tank.alive:
                continue
            horizontal = abs(tank.x - center)
            if horizontal > influence:
                continue
            falloff = max(0.25, 1.0 - (horizontal / max(influence, 0.001)))
            damage = max(1, int(base_damage * falloff))
            before_hp = int(tank.hp)
            tank.take_damage(damage)
            dealt = max(0, before_hp - int(tank.hp))
            if dealt > 0:
                affected.append((tank, dealt))
            if before_hp > 0 and not tank.alive:
                fatalities.append(tank)
        for tank in self.tanks:
            if tank.alive:
                self.settle_tank(tank)
        return affected, fatalities

    def _apply_splash_damage(self, impact_x: float, impact_y: float) -> Optional[Tank]:
        radius = self.explosion_radius
        max_distance = radius
        fatal_tank: Optional[Tank] = None
        for tank in self.tanks:
            if not tank.alive:
                continue
            distance = math.hypot(tank.x - impact_x, tank.y - impact_y)
            if distance > max_distance:
                continue
            if distance <= 0.5:
                if tank.alive:
                    tank.take_damage(self.damage)
                    if not tank.alive:
                        fatal_tank = tank
                continue
            falloff = 1 - min(distance / max_distance, 1.0)
            splash_damage = max(1, int(self.damage * falloff * 0.6))
            was_alive = tank.alive
            tank.take_damage(splash_damage)
            if was_alive and not tank.alive:
                fatal_tank = tank
        return fatal_tank

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
