"""Procedural terrain representation using a high-resolution signed-distance field."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple


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
    style: str = "classic"


@dataclass
class BuildingFloor:
    """Single storey of a building footprint."""

    height: float
    max_hp: int
    hp: int
    destroyed: bool = False

    def damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.destroyed = True


@dataclass
class Building:
    """Rectilinear structure composed of stacked floors."""

    id: int
    left: float
    right: float
    base: float
    floors: List[BuildingFloor] = field(default_factory=list)
    style: str = "block"
    unstable: bool = False
    collapsed: bool = False
    collapse_timer: float = 0.0

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def top(self) -> float:
        return self.base - sum(f.height for f in self.floors)

    def floor_bounds(self, index: int) -> Tuple[float, float]:
        if not (0 <= index < len(self.floors)):
            raise IndexError("floor index out of range")
        bottom = self.base
        for floor in self.floors[:index]:
            bottom -= floor.height
        top = bottom - self.floors[index].height
        return top, bottom

    def first_intact_floor_index(self) -> Optional[int]:
        for idx, floor in enumerate(self.floors):
            if not floor.destroyed:
                return idx
        return None


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
        self.buildings: List[Building] = []
        self._generate_height_map()
        self._generate_structures()
        self._pending_collapses: List[Building] = []

    # ------------------------------------------------------------------
    # Generation
    def _generate_height_map(self) -> None:
        style = (self.settings.style or "classic").lower()
        if style == "urban":
            self._generate_urban_height_map()
        else:
            self._generate_classic_height_map()

    def _generate_classic_height_map(self) -> None:
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

    def _generate_urban_height_map(self) -> None:
        rng = self._rng
        min_h = self.settings.min_height
        max_h = min(self.height - 2, self.settings.max_height)
        base_height = max(min_h, min(max_h, (min_h * 2 + max_h) / 3))

        span = self.grid_width
        self.height_map = [base_height for _ in range(span)]

        large_scale = self._value_noise(self.detail * 24)
        medium_scale = self._value_noise(self.detail * 8)
        for hx in range(span):
            total = base_height
            total += (large_scale[hx] - 0.5) * 1.5
            total += (medium_scale[hx] - 0.5) * 0.6
            self.height_map[hx] = max(min_h, min(max_h, total))

        street_count = rng.randint(2, 4)
        for _ in range(street_count):
            center_cell = rng.uniform(6.0, max(7.0, self.width - 6.0))
            street_half_width = rng.uniform(1.8, 3.2)
            depression = rng.uniform(1.2, 2.4)
            influence = rng.uniform(3.0, 4.5)
            start = max(0, int((center_cell - influence) * self.detail))
            end = min(self.grid_width - 1, int((center_cell + influence) * self.detail))
            for hx in range(start, end + 1):
                x_world = hx / self.detail
                distance = abs(x_world - center_cell)
                if distance > influence:
                    continue
                t = max(0.0, 1.0 - (distance / influence))
                curb = max(0.0, 1.0 - (distance / street_half_width))
                drop = depression * (t ** 2)
                rim = 0.6 * curb
                target = self.height_map[hx] - drop + rim
                self.height_map[hx] = max(min_h, min(max_h, target))

        plaza_count = rng.randint(1, 2)
        for _ in range(plaza_count):
            center_cell = rng.uniform(10.0, max(12.0, self.width - 10.0))
            width_cells = rng.uniform(4.0, 7.0)
            elevation = rng.uniform(0.5, 1.4)
            start = max(0, int((center_cell - width_cells) * self.detail))
            end = min(self.grid_width - 1, int((center_cell + width_cells) * self.detail))
            for hx in range(start, end + 1):
                x_world = hx / self.detail
                distance = abs(x_world - center_cell)
                if distance > width_cells:
                    continue
                t = max(0.0, 1.0 - (distance / width_cells))
                self.height_map[hx] = max(min_h, min(max_h, self.height_map[hx] + elevation * (t ** 2)))

        self._smooth_heights(0, span - 1, iterations=max(2, self.settings.smoothing // 2))

    # ------------------------------------------------------------------
    def _generate_structures(self) -> None:
        style = (self.settings.style or "classic").lower()
        if style == "urban":
            self._generate_urban_structures()
        else:
            self.buildings = []

    def _generate_urban_structures(self) -> None:
        rng = self._rng
        self.buildings = []
        reserved_margin = 6.0
        left_bound = reserved_margin
        right_bound = max(left_bound, self.width - reserved_margin)
        if right_bound - left_bound < 8.0:
            return

        x = left_bound + rng.uniform(0.5, 1.5)
        building_id = 0
        while x < right_bound:
            width_cells = rng.uniform(3.0, 6.0)
            start = x
            end = start + width_cells
            if end > right_bound:
                break

            section = self._terrain_slice(start, end)
            if not section:
                x += rng.uniform(1.0, 2.0)
                continue
            heights = section
            min_height = min(heights)
            max_height = max(heights)
            if max_height - min_height > 1.4:
                x += rng.uniform(1.0, 2.0)
                continue

            base_height = min_height
            floor_count = rng.randint(2, 5)
            floors: List[BuildingFloor] = []
            for level in range(floor_count):
                floor_height = rng.uniform(2.2, 3.2) if level == 0 else rng.uniform(2.0, 2.8)
                max_hp = rng.randint(45, 70)
                floors.append(BuildingFloor(height=floor_height, max_hp=max_hp, hp=max_hp))

            while floors and (base_height - sum(f.height for f in floors)) < 1.5:
                floors.pop()
            if len(floors) < 1:
                x += rng.uniform(1.0, 2.0)
                continue

            variant = rng.choice(["block", "loft", "tower"])
            building = Building(
                id=building_id,
                left=start,
                right=end,
                base=base_height,
                floors=floors,
                style=variant,
            )
            self.buildings.append(building)
            building_id += 1

            gap = rng.uniform(1.2, 3.2)
            x = end + gap + rng.uniform(-0.4, 0.8)

    def _terrain_slice(self, left: float, right: float) -> List[float]:
        if right <= left:
            return []
        start = max(0, int(math.floor(left * self.detail)))
        end = min(self.grid_width - 1, int(math.ceil(right * self.detail)))
        if start >= self.grid_width or end < 0:
            return []
        return [self.height_map[hx] for hx in range(start, end + 1)]

    # ------------------------------------------------------------------
    # Building utilities
    def building_hit_test(self, x: float, y: float) -> Optional[Tuple[Building, int]]:
        tolerance = 0.05
        horizontal_pad = 0.15
        for building in self.buildings:
            if building.collapsed:
                continue
            if x < building.left - horizontal_pad or x > building.right + horizontal_pad:
                continue
            floor_bottom = building.base
            for idx, floor in enumerate(building.floors):
                floor_top = floor_bottom - floor.height
                if not floor.destroyed:
                    top_y = min(floor_top, floor_bottom)
                    bottom_y = max(floor_top, floor_bottom)
                    if top_y - tolerance <= y <= bottom_y + tolerance:
                        return building, idx
                floor_bottom = floor_top
        return None

    def schedule_building_collapse(self, building: Building, delay: float = 0.0) -> None:
        if building.collapsed:
            return
        building.unstable = True
        building.collapse_timer = max(0.0, delay)
        if building not in self._pending_collapses:
            self._pending_collapses.append(building)

    def update_collapsing_buildings(self, dt: float) -> List[Building]:
        collapsed: List[Building] = []
        still_pending: List[Building] = []
        for building in self._pending_collapses:
            if building.collapsed:
                continue
            building.collapse_timer = max(0.0, building.collapse_timer - dt)
            if building.collapse_timer > 0.0:
                still_pending.append(building)
                continue
            collapsed.append(building)
        self._pending_collapses = still_pending
        for building in collapsed:
            self._collapse_building(building)
        return collapsed

    def _collapse_building(self, building: Building) -> None:
        if building.collapsed:
            return
        building.collapsed = True
        building.unstable = False
        for floor in building.floors:
            floor.destroyed = True
            floor.hp = 0
        width = building.width
        center = (building.left + building.right) * 0.5
        radius = max(1.2, width * 0.8)
        self.carve_circle(center, building.base, radius)

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
