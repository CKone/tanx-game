"""Procedural terrain representation using a high-resolution signed-distance field."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, List, Optional


@dataclass
class TerrainSettings:
    """Configuration options for terrain generation."""

    width: int = 48
    height: int = 36
    min_height: float = 12.0
    max_height: float = 26.0
    smoothing: int = 3
    detail: int = 6  # number of SDF samples per gameplay cell
    seed: Optional[int] = None


class World:
    """Terrain described by a 2D signed-distance field derived from a height map."""

    def __init__(self, settings: Optional[TerrainSettings] = None) -> None:
        self.settings = settings or TerrainSettings()
        self.width = self.settings.width
        self.height = self.settings.height
        self.detail = max(2, self.settings.detail)
        self.grid_width = self.width * self.detail
        self.grid_height = self.height * self.detail
        self._rng = random.Random(self.settings.seed)

        self.height_map: List[float] = [self.height * 0.5 for _ in range(self.grid_width)]
        self._generate_height_map()

    # ------------------------------------------------------------------
    # Generation
    def _generate_height_map(self) -> None:
        rng = self._rng
        min_h = self.settings.min_height
        max_h = min(self.height - 2, self.settings.max_height)
        span = self.grid_width
        self.height_map = [0.0 for _ in range(span)]

        layers = [
            (self.detail * 18, 0.55),
            (self.detail * 9, 0.3),
            (self.detail * 4, 0.15),
        ]
        for spacing, strength in layers:
            noise = self._value_noise(spacing)
            amplitude = (max_h - min_h) * strength
            for i in range(span):
                self.height_map[i] += (noise[i] - 0.5) * amplitude

        offset = (min_h + max_h) * 0.5
        for i in range(span):
            self.height_map[i] = max(min_h, min(max_h, offset + self.height_map[i]))

        self._smooth_heights(0, span - 1, iterations=6)

    # ------------------------------------------------------------------
    # Queries
    def is_inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def sample_sdf(self, x: float, y: float) -> float:
        """Return signed distance (positive above ground, negative inside)."""

        x = max(0.0, min(self.width - 1e-4, x))
        base = x * self.detail
        ix = int(math.floor(base))
        fx = base - ix
        h0 = self.height_map[ix]
        h1 = self.height_map[min(ix + 1, self.grid_width - 1)]
        height = h0 * (1 - fx) + h1 * fx
        return height - y

    def is_solid(self, x: int, y: int) -> bool:
        if not self.is_inside(x, y):
            return False
        center_y = y + 0.5
        hx = min(self.grid_width - 1, max(0, int((x + 0.5) * self.detail)))
        height = self.height_map[hx]
        return center_y >= height

    def highest_solid(self, x: int) -> Optional[int]:
        if not 0 <= x < self.width:
            return None
        hx = min(self.grid_width - 1, max(0, int(x * self.detail)))
        return int(math.floor(self.height_map[hx]))

    def surface_y(self, x: int) -> Optional[int]:
        top = self.highest_solid(x)
        if top is None:
            return None
        return max(0, top - 1)

    def ground_height(self, x_float: float) -> Optional[float]:
        if x_float < 0 or x_float > self.width - 1e-4:
            return None
        base = x_float * self.detail
        ix = int(math.floor(base))
        fx = base - ix
        h0 = self.height_map[ix]
        h1 = self.height_map[min(ix + 1, self.grid_width - 1)]
        return h0 * (1 - fx) + h1 * fx

    # ------------------------------------------------------------------
    # Terrain manipulation
    def carve_circle(self, cx: float, cy: float, radius: float) -> None:
        if radius <= 0:
            return
        detail = self.detail
        start = max(0, int((cx - radius * 1.8) * detail))
        end = min(self.grid_width - 1, int((cx + radius * 1.8) * detail))
        if start > end:
            return

        crater_depth = radius * 0.7
        for hx in range(start, end + 1):
            x_world = hx / detail
            dx = x_world - cx
            dist = abs(dx)
            if dist > radius * 1.8:
                continue

            current = self.height_map[hx]
            # Bowl interior
            if dist <= radius:
                profile = math.cos((dist / radius) * math.pi) * 0.5 + 0.5
                target = cy + profile * crater_depth
                self.height_map[hx] = max(current, min(self.height - 1, target))
            else:
                # Slight rim elevation beyond the crater edge.
                rim_span = radius * 0.6
                if dist <= radius + rim_span:
                    rim_t = 1 - (dist - radius) / rim_span
                    rim_height = rim_t * (crater_depth * 0.2)
                    self.height_map[hx] = max(self.settings.min_height, current - rim_height)

        self._smooth_heights(start, end, iterations=4)

    def carve_square(self, cx: float, cy: float, size: int = 4) -> None:
        radius = max(1.0, size) / math.sqrt(2)
        self.carve_circle(cx, cy, radius)

    # ------------------------------------------------------------------
    # Utilities
    def iter_rows(self) -> Iterable[str]:
        for y in range(self.height):
            row_chars = []
            center = y + 0.5
            for x in range(self.width):
                hx = min(self.grid_width - 1, max(0, int((x + 0.5) * self.detail)))
                char = '#' if center >= self.height_map[hx] else ' '
                row_chars.append(char)
            yield ''.join(row_chars)

    def copy_grid(self) -> List[List[str]]:
        return [list(row) for row in self.iter_rows()]

    def highest_solid_high(self, hx: int) -> Optional[int]:
        if not (0 <= hx < self.grid_width):
            return None
        height = self.height_map[hx]
        return int(min(self.grid_height - 1, max(0, math.floor(height * self.detail))))

    # ------------------------------------------------------------------
    def _smooth_heights(self, start: int, end: int, iterations: int = 1) -> None:
        if start >= end:
            return
        kernel = [0.15, 0.35, 0.35, 0.15]
        half = len(kernel) // 2
        temp = self.height_map[:]
        for _ in range(iterations):
            for hx in range(start, end + 1):
                accum = 0.0
                weight = 0.0
                for k, w in enumerate(kernel):
                    offset = k - half
                    idx = min(max(start, hx + offset), end)
                    accum += temp[idx] * w
                    weight += w
                self.height_map[hx] = max(self.settings.min_height, min(self.settings.max_height, accum / weight))
            temp = self.height_map[:]

    def _value_noise(self, spacing: int) -> List[float]:
        spacing = max(1, spacing)
        span = self.grid_width
        control_count = span // spacing + 3
        controls = [self._rng.random() for _ in range(control_count)]
        noise = [0.0] * span
        for hx in range(span):
            idx = hx // spacing
            local = (hx % spacing) / spacing
            t = local * local * (3 - 2 * local)  # smoothstep
            n0 = controls[idx]
            n1 = controls[idx + 1]
            noise[hx] = n0 * (1 - t) + n1 * t
        return noise
