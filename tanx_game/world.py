"""Procedural world generation and terrain handling for the Tanx game."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, List, Optional


@dataclass
class TerrainSettings:
    """Configuration options for terrain generation."""

    width: int = 48
    height: int = 20
    min_height: int = 4
    max_height: int = 12
    smoothing: int = 3
    seed: Optional[int] = None


class World:
    """A simple 2D destructible terrain represented on a grid."""

    def __init__(self, settings: Optional[TerrainSettings] = None) -> None:
        self.settings = settings or TerrainSettings()
        self.width = self.settings.width
        self.height = self.settings.height
        self.grid: List[List[bool]] = [
            [False for _ in range(self.width)] for _ in range(self.height)
        ]
        self._generate()

    def _generate(self) -> None:
        rng = random.Random(self.settings.seed)
        min_h = self.settings.min_height
        max_h = self.settings.max_height
        last_height = rng.randint(min_h, max_h)
        column_heights: List[int] = []
        for x in range(self.width):
            delta = sum(rng.randint(-1, 1) for _ in range(self.settings.smoothing))
            next_height = max(min_h, min(max_h, last_height + delta))
            column_heights.append(next_height)
            last_height = next_height
        for x, column_height in enumerate(column_heights):
            ground_start = self.height - column_height
            for y in range(ground_start, self.height):
                self.grid[y][x] = True

    def is_inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_solid(self, x: int, y: int) -> bool:
        if not self.is_inside(x, y):
            return False
        return self.grid[y][x]

    def carve_circle(self, cx: float, cy: float, radius: float) -> None:
        """Remove terrain in a circular radius around a point."""

        r_sq = radius * radius
        min_x = max(int(cx - radius) - 1, 0)
        max_x = min(int(cx + radius) + 1, self.width - 1)
        min_y = max(int(cy - radius) - 1, 0)
        max_y = min(int(cy + radius) + 1, self.height - 1)
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                dx = x + 0.5 - cx
                dy = y + 0.5 - cy
                if dx * dx + dy * dy <= r_sq:
                    self.grid[y][x] = False

    def highest_solid(self, x: int) -> Optional[int]:
        """Return the highest (smallest y) solid cell in the column."""

        if not 0 <= x < self.width:
            return None
        for y in range(self.height):
            if self.grid[y][x]:
                return y
        return None

    def surface_y(self, x: int) -> Optional[int]:
        """Return the y coordinate the tank should stand on for a column."""

        top = self.highest_solid(x)
        if top is None:
            return None
        return top - 1

    def iter_rows(self) -> Iterable[str]:
        for y in range(self.height):
            yield "".join("#" if cell else " " for cell in self.grid[y])

    def copy_grid(self) -> List[List[str]]:
        return [["#" if cell else " " for cell in row] for row in self.grid]
