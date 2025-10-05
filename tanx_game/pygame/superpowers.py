"""Superpower effects (bomber and squad) for the Tanx pygame client."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional

import pygame

from ..core.game import ShotResult


class SuperpowerBase:
    """Common helpers for superpower effects."""

    def __init__(self, app, player_index: int) -> None:
        self.app = app
        self.player_index = player_index
        self.enemy_index = 1 - player_index
        self.direction = 1 if player_index == 0 else -1
        self.cell = app.cell_size
        self.offset_x = app.playfield_offset_x
        self.offset_y = app.ui_height
        self.world_width = app.world_width
        self.world_height = app.world_height
        self.screen_height = self.offset_y + self.world_height * self.cell

    def screen_to_world(self, x_px: float, y_px: float) -> tuple[float, float]:
        x_world = (x_px - self.offset_x) / self.cell
        y_world = (y_px - self.offset_y) / self.cell
        x_world = max(0.0, min(self.world_width - 1e-3, x_world))
        y_world = max(0.0, min(self.world_height - 1e-3, y_world))
        return x_world, y_world

    def world_to_screen(self, x_world: float, y_world: float) -> tuple[float, float]:
        x_px = self.offset_x + x_world * self.cell
        y_px = self.offset_y + y_world * self.cell
        return x_px, y_px

    def apply_damage(
        self,
        x_world: float,
        y_world: float,
        damage_scale: float = 1.0,
        explosion_scale: float = 1.0,
    ) -> None:
        self.app._apply_superpower_damage(x_world, y_world, damage_scale, explosion_scale)


class BomberPower(SuperpowerBase):
    """Air strike that drops bombs across the opponent's position."""

    def __init__(self, app, player_index: int) -> None:
        super().__init__(app, player_index)
        width_px = self.world_width * self.cell
        margin = 160
        if self.direction > 0:
            self.x = self.offset_x - margin
            self.end_x = self.offset_x + width_px + margin
        else:
            self.x = self.offset_x + width_px + margin
            self.end_x = self.offset_x - margin
        self.y = self.offset_y + self.cell * 2.8
        self.speed = 320.0
        self.gravity = 620.0
        self.body_w = 68
        self.body_h = 24
        self.wing_span = 82
        target_tank = app.logic.tanks[self.enemy_index]
        target_x = self.offset_x + (target_tank.x + 0.5) * self.cell
        spread_px = self.cell * 3.4
        self.drop_points = sorted(
            [target_x + random.uniform(-spread_px, spread_px) for _ in range(5)],
            reverse=self.direction < 0,
        )
        self.bombs: List[dict[str, float]] = []
        self.finished = False

    def update(self, dt: float) -> bool:
        if self.finished and not self.bombs:
            return True

        if not self.finished:
            self.x += self.direction * self.speed * dt
            while self.drop_points and (
                (self.direction > 0 and self.x >= self.drop_points[0])
                or (self.direction < 0 and self.x <= self.drop_points[0])
            ):
                release_x = self.drop_points.pop(0)
                self._spawn_bomb(release_x)

            if (self.direction > 0 and self.x >= self.end_x) or (
                self.direction < 0 and self.x <= self.end_x
            ):
                self.finished = True

        for bomb in list(self.bombs):
            bomb["vy"] += self.gravity * dt
            bomb["x"] += bomb["vx"] * dt
            bomb["y"] += bomb["vy"] * dt
            x_world, y_world = self.screen_to_world(bomb["x"], bomb["y"])
            ground_height = self.app.logic.world.ground_height(x_world)
            if ground_height is None:
                continue
            if y_world >= ground_height:
                self.apply_damage(
                    x_world,
                    ground_height,
                    damage_scale=0.85,
                    explosion_scale=1.2,
                )
                self.bombs.remove(bomb)

        return self.finished and not self.bombs

    def _spawn_bomb(self, release_x: float) -> None:
        jitter = random.uniform(-12.0, 12.0)
        bomb = {
            "x": release_x + jitter,
            "y": self.y + self.body_h * 0.4,
            "vx": self.direction * random.uniform(35.0, 85.0),
            "vy": random.uniform(-5.0, 15.0),
        }
        self.bombs.append(bomb)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.finished:
            x = int(self.x)
            y = int(self.y)
            body_rect = pygame.Rect(x - self.body_w // 2, y - self.body_h // 2, self.body_w, self.body_h)
            pygame.draw.ellipse(surface, (160, 40, 40), body_rect)
            wing = pygame.Rect(x - self.wing_span // 2, y - 6, self.wing_span, 12)
            pygame.draw.ellipse(surface, (120, 25, 25), wing)
            cockpit = pygame.Rect(x + self.direction * 10 - 14, y - 6, 24, 12)
            pygame.draw.ellipse(surface, (210, 210, 230), cockpit)
            tail = [
                (x - self.direction * self.body_w // 2, y),
                (x - self.direction * (self.body_w // 2 + 10), y - 10),
                (x - self.direction * (self.body_w // 2 + 10), y + 10),
            ]
            pygame.draw.polygon(surface, (120, 25, 25), tail)

        for bomb in self.bombs:
            pygame.draw.circle(surface, (60, 60, 72), (int(bomb["x"]), int(bomb["y"])), 5)


@dataclass
class SquadFlash:
    x: float
    y: float
    life: float


class SquadPower(SuperpowerBase):
    """Ground squad that advances and fires a volley."""

    def __init__(self, app, player_index: int) -> None:
        super().__init__(app, player_index)
        tank = app.logic.tanks[player_index]
        start_world_x = max(0.5, min(self.world_width - 0.5, tank.x + 0.5))
        start_screen_x, start_screen_y = self.world_to_screen(start_world_x, tank.y - 0.1)
        self.base_y = start_screen_y
        self.soldiers: List[dict] = []
        spacing = self.cell * 2.2
        roles = ["panzerfaust", "panzerfaust", "mortar", "mortar", "rifle", "rifle"]
        for idx, role in enumerate(roles):
            offset = idx - (len(roles) - 1) / 2
            start_x = start_screen_x - self.direction * (3 * self.cell) + offset * spacing
            self.soldiers.append(
                {
                    "role": role,
                    "x": start_x,
                    "y": start_screen_y,
                    "state": "advance",
                    "timer": 0.0,
                    "fired": False,
                    "mortar_unfolded": False,
                }
            )

        enemy = app.logic.tanks[self.enemy_index]
        self.target_x = self.offset_x + (enemy.x + 0.5) * self.cell
        self.speed = 90.0
        self.flash_effects: List[SquadFlash] = []
        self.scale = max(0.6, min(1.0, self.cell / 28.0))
        self.spacing = spacing
        self.done = False
        self.phase = "advance"
        self.phase_timer = 0.0
        self.fire_order = list(range(len(self.soldiers)))
        self.fire_index = 0
        self.fire_timer = 0.0

    def update(self, dt: float) -> bool:
        self._update_flashes(dt)
        if self.done:
            return True

        self.phase_timer += dt

        if self.phase == "advance":
            all_reached = True
            for soldier in self.soldiers:
                if soldier["state"] != "advance":
                    continue
                soldier["timer"] += dt
                soldier["x"] += self.direction * self.speed * dt
                soldier["y"] = self._ground_height_screen(soldier["x"])
                engage_distance = 120 + random.uniform(-20, 20)
                if (self.direction > 0 and soldier["x"] >= self.target_x - engage_distance) or (
                    self.direction < 0 and soldier["x"] <= self.target_x + engage_distance
                ):
                    soldier["state"] = "deploy"
                    soldier["timer"] = 0.0
                else:
                    all_reached = False
            if all_reached:
                self.phase = "deploy"
                self.phase_timer = 0.0

        if self.phase == "deploy":
            all_ready = True
            for soldier in self.soldiers:
                if soldier["state"] == "deploy":
                    soldier["timer"] += dt
                    if soldier["role"] == "mortar" and soldier["timer"] >= 0.6:
                        soldier["mortar_unfolded"] = True
                    if soldier["timer"] >= 1.2:
                        soldier["state"] = "ready"
                        soldier["timer"] = 0.0
                    else:
                        all_ready = False
                elif soldier["state"] not in {"ready", "fire", "exit", "left"}:
                    all_ready = False
            if all_ready:
                for soldier in self.soldiers:
                    soldier["state"] = "fire"
                    soldier["timer"] = 0.0
                self.phase = "fire"
                self.phase_timer = 0.0
                self.fire_index = 0
                self.fire_timer = 0.0

        if self.phase == "fire":
            self.fire_timer += dt
            if self.fire_index < len(self.fire_order) and self.fire_timer >= 0.45 + random.uniform(0.0, 0.15):
                idx = self.fire_order[self.fire_index]
                soldier = self.soldiers[idx]
                if not soldier["fired"]:
                    self._fire_soldier(soldier)
                    soldier["fired"] = True
                self.fire_index += 1
                self.fire_timer = 0.0
            if self.fire_index >= len(self.fire_order) and all(s["fired"] for s in self.soldiers):
                if self.phase_timer >= 1.0:
                    self.phase = "exit"
                    self.phase_timer = 0.0
                    for soldier in self.soldiers:
                        soldier["state"] = "exit"
                        soldier["timer"] = 0.0

        if self.phase == "exit":
            all_left = True
            boundary = (
                self.offset_x + self.world_width * self.cell + 220
                if self.direction > 0
                else self.offset_x - 220
            )
            for soldier in self.soldiers:
                if soldier["state"] == "exit":
                    soldier["timer"] += dt
                    soldier["x"] += self.direction * self.speed * dt
                    soldier["y"] = self._ground_height_screen(soldier["x"])
                    if (self.direction > 0 and soldier["x"] > boundary) or (
                        self.direction < 0 and soldier["x"] < boundary
                    ):
                        soldier["state"] = "left"
                    else:
                        all_left = False
                elif soldier["state"] != "left":
                    all_left = False
            if all_left:
                self.done = True
                return True

        return False

    def _ground_height_screen(self, x_px: float) -> float:
        x_world = max(0.0, min(self.world_width - 1e-3, (x_px - self.offset_x) / self.cell))
        height = self.app.logic.world.ground_height(x_world)
        if height is None:
            height = self.world_height
        return self.offset_y + (height - 0.2) * self.cell

    def _fire_soldier(self, soldier: dict) -> None:
        role = soldier["role"]
        target_px = self.target_x + random.uniform(-80, 80)
        target_y_px = self.offset_y + (self.app.logic.tanks[self.enemy_index].y - 0.25) * self.cell
        x_world, y_world = self.screen_to_world(target_px, target_y_px)

        if role == "panzerfaust":
            self.apply_damage(x_world, y_world, damage_scale=1.2, explosion_scale=1.3)
        elif role == "mortar":
            mortar_y = y_world - 0.6
            self.apply_damage(x_world, max(0.0, mortar_y), damage_scale=1.0, explosion_scale=1.45)
        else:  # rifle
            self.apply_damage(x_world, y_world, damage_scale=0.4, explosion_scale=0.65)

        self.flash_effects.append(SquadFlash(soldier["x"], soldier["y"] - 18, 0.25))

    def _update_flashes(self, dt: float) -> None:
        for flash in list(self.flash_effects):
            flash.life -= dt
            if flash.life <= 0:
                self.flash_effects.remove(flash)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.soldiers:
            return

        for soldier in self.soldiers:
            self._draw_single_soldier(surface, soldier)
        for flash in self.flash_effects:
            alpha = max(0, min(255, int(255 * (flash.life / 0.25))))
            flash_surface = pygame.Surface((18, 8), pygame.SRCALPHA)
            pygame.draw.polygon(
                flash_surface,
                (255, 230, 120, alpha),
                [(0, 4), (18, 0), (18, 8)],
            )
            surface.blit(
                flash_surface,
                (
                    flash.x - (18 if self.direction > 0 else 0),
                    flash.y,
                ),
            )

    def _draw_single_soldier(self, surface: pygame.Surface, soldier: dict) -> None:
        x = soldier["x"]
        y = soldier["y"]
        S = self.scale
        facing_left = self.direction < 0

        color_body = (60, 110, 80)
        color_helmet = (80, 130, 90)
        color_rifle = (40, 40, 48)
        color_panzerfaust = (30, 30, 32)
        color_mortar = (45, 45, 50)
        color_detail = (200, 200, 200)

        head_r = max(3, int(6 * S))
        body_w = int(14 * S)
        body_h = int(20 * S)
        body_rect = pygame.Rect(0, 0, body_w, body_h)
        body_rect.center = (int(x), int(y + 4 * S))

        head_pos = (int(x), int(y - int(6 * S)))
        pygame.draw.circle(surface, color_helmet, head_pos, head_r)
        pygame.draw.circle(surface, color_detail, head_pos, max(1, head_r // 3))

        pygame.draw.rect(surface, color_body, body_rect, border_radius=max(2, int(3 * S)))
        pygame.draw.line(
            surface, color_body, (x - int(3 * S), y + int(14 * S)), (x - int(3 * S), y + int(24 * S)), max(1, int(2 * S))
        )
        pygame.draw.line(
            surface, color_body, (x + int(3 * S), y + int(14 * S)), (x + int(3 * S), y + int(24 * S)), max(1, int(2 * S))
        )

        pack_rect = pygame.Rect(0, 0, int(8 * S), int(12 * S))
        pack_rect.center = (int(x - 0.6 * body_w), int(y + int(3 * S)))
        pygame.draw.rect(surface, (50, 80, 60), pack_rect, border_radius=max(1, int(2 * S)))

        dir_mul = -1 if facing_left else 1
        shoulder_y = y + int(0 * S)

        role = soldier["role"]
        if role == "panzerfaust":
            pygame.draw.line(surface, color_body, (x, shoulder_y), (x + dir_mul * int(8 * S), shoulder_y), max(1, int(2 * S)))
            tube_len = int(30 * S)
            tube_w = max(3, int(5 * S))
            tx0 = int(x + dir_mul * (8 * S))
            ty0 = shoulder_y - int(3 * S)
            tube = [
                (tx0, ty0),
                (tx0 + dir_mul * tube_len, ty0 - tube_w // 2),
                (tx0 + dir_mul * tube_len, ty0 + tube_w // 2),
            ]
            pygame.draw.polygon(surface, color_panzerfaust, tube)
            muzzle = (tx0 + dir_mul * (tube_len + int(4 * S)), ty0)
            pygame.draw.circle(surface, color_detail, muzzle, max(1, int(2 * S)))
        elif role == "mortar":
            if soldier["mortar_unfolded"]:
                base_x = int(x + dir_mul * int(18 * S))
                base_y = int(y + int(10 * S))
                leg_len = int(12 * S)
                pygame.draw.line(
                    surface, color_mortar, (base_x, base_y), (base_x - dir_mul * leg_len, base_y + int(10 * S)), max(1, int(2 * S))
                )
                pygame.draw.line(
                    surface, color_mortar, (base_x, base_y), (base_x + dir_mul * leg_len, base_y + int(10 * S)), max(1, int(2 * S))
                )
                tube_len = int(28 * S)
                tube_w = max(3, int(5 * S))
                tube_end = (base_x + dir_mul * int(tube_len * 0.8), base_y - int(14 * S))
                pygame.draw.line(surface, color_mortar, (base_x, base_y - int(2 * S)), tube_end, tube_w)
                pygame.draw.rect(surface, (80, 80, 85), (base_x - int(4 * S), base_y - int(2 * S), int(8 * S), int(6 * S)))
            else:
                folded_x = int(x - dir_mul * int(10 * S))
                folded_y = int(y + int(0 * S))
                pygame.draw.rect(
                    surface,
                    color_mortar,
                    (folded_x - int(10 * S), folded_y - int(4 * S), int(20 * S), int(6 * S)),
                    border_radius=max(1, int(2 * S)),
                )
                pygame.draw.line(
                    surface,
                    color_detail,
                    (folded_x - int(8 * S), folded_y - int(2 * S)),
                    (x - int(3 * S), folded_y + int(2 * S)),
                    max(1, int(1 * S)),
                )
        else:
            hand_x = int(x + dir_mul * int(8 * S))
            hand_y = int(y + int(2 * S))
            barrel_len = int(28 * S)
            barrel_w = max(2, int(3 * S))
            stock = (x - dir_mul * int(6 * S), hand_y + int(2 * S))
            pygame.draw.line(surface, color_rifle, stock, (int(hand_x), hand_y), max(1, int(2 * S)))
            bx0 = int(hand_x)
            by0 = hand_y - int(1 * S)
            bx1 = int(bx0 + dir_mul * barrel_len)
            pygame.draw.line(surface, color_rifle, (bx0, by0), (bx1, by0), barrel_w)
            pygame.draw.circle(
                surface,
                color_detail,
                (int(bx0 + dir_mul * int(8 * S)), by0),
                max(1, int(1.5 * S)),
            )

        shadow_w = int(body_w * 1.2)
        shadow_h = int(6 * S)
        shadow_rect = pygame.Rect(0, 0, shadow_w, shadow_h)
        shadow_rect.center = (int(x), int(y + int(26 * S)))
        s_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (10, 10, 10, 100), (0, 0, shadow_rect.width, shadow_rect.height))
        surface.blit(s_surf, shadow_rect.topleft)


class SuperpowerManager:
    """Controller that manages the currently active superpower effect."""

    def __init__(self, app) -> None:
        self.app = app
        self.active: Optional[SuperpowerBase] = None

    def activate(self, kind: str, player_index: int) -> bool:
        if self.active is not None:
            return False
        if kind == "bomber":
            self.active = BomberPower(self.app, player_index)
        elif kind == "squad":
            self.active = SquadPower(self.app, player_index)
        else:
            return False
        return True

    def update(self, dt: float) -> bool:
        if self.active is None:
            return False
        finished = self.active.update(dt)
        if finished:
            self.active = None
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if self.active is not None:
            self.active.draw(surface)

    def is_active(self) -> bool:
        return self.active is not None


def draw_squad(
    surface: pygame.Surface,
    center: tuple[float, float],
    spacing: int = 72,
    scale: float = 1.0,
    mortar_unfolded=False,
    facing_left: bool = False,
) -> List[dict]:
    """Render six stylised soldiers and return their metadata."""

    if isinstance(mortar_unfolded, bool):
        mortar_flags = (mortar_unfolded, mortar_unfolded)
    else:
        mortar_flags = tuple(mortar_unfolded)[:2]
        if len(mortar_flags) < 2:
            mortar_flags = (False, False)

    cx, cy = center
    count = 6
    total_width = (count - 1) * spacing * scale
    start_x = cx - total_width / 2

    color_body = (60, 110, 80)
    color_helmet = (80, 130, 90)
    color_rifle = (40, 40, 48)
    color_panzerfaust = (30, 30, 32)
    color_mortar = (45, 45, 50)
    color_detail = (200, 200, 200)

    results: List[dict] = []

    def draw_soldier_at(surf, x, y, role: str, mortar_open=False):
        S = scale
        head_r = max(3, int(6 * S))
        body_w = int(14 * S)
        body_h = int(20 * S)
        body_rect = pygame.Rect(0, 0, body_w, body_h)
        body_rect.center = (int(x), int(y + 4 * S))

        head_pos = (int(x), int(y - int(6 * S)))
        pygame.draw.circle(surf, color_helmet, head_pos, head_r)
        pygame.draw.circle(surf, color_detail, head_pos, max(1, head_r // 3))

        pygame.draw.rect(surf, color_body, body_rect, border_radius=max(2, int(3 * S)))
        pygame.draw.line(
            surf, color_body, (x - int(3 * S), y + int(14 * S)), (x - int(3 * S), y + int(24 * S)), max(1, int(2 * S))
        )
        pygame.draw.line(
            surf, color_body, (x + int(3 * S), y + int(14 * S)), (x + int(3 * S), y + int(24 * S)), max(1, int(2 * S))
        )

        pack_rect = pygame.Rect(0, 0, int(8 * S), int(12 * S))
        pack_rect.center = (int(x - 0.6 * body_w), int(y + int(3 * S)))
        pygame.draw.rect(surf, (50, 80, 60), pack_rect, border_radius=max(1, int(2 * S)))

        dir_mul = -1 if facing_left else 1
        shoulder_y = y + int(0 * S)

        if role == "panzerfaust":
            pygame.draw.line(surf, color_body, (x, shoulder_y), (x + dir_mul * int(8 * S), shoulder_y), max(1, int(2 * S)))
            tube_len = int(30 * S)
            tube_w = max(3, int(5 * S))
            tx0 = int(x + dir_mul * (8 * S))
            ty0 = shoulder_y - int(3 * S)
            tube = [
                (tx0, ty0),
                (tx0 + dir_mul * tube_len, ty0 - tube_w // 2),
                (tx0 + dir_mul * tube_len, ty0 + tube_w // 2),
            ]
            pygame.draw.polygon(surf, color_panzerfaust, tube)
            muzzle = (tx0 + dir_mul * (tube_len + int(4 * S)), ty0)
            pygame.draw.circle(surf, color_detail, muzzle, max(1, int(2 * S)))
        elif role == "mortar":
            if mortar_open:
                base_x = int(x + dir_mul * int(18 * S))
                base_y = int(y + int(10 * S))
                leg_len = int(12 * S)
                pygame.draw.line(
                    surf, color_mortar, (base_x, base_y), (base_x - dir_mul * leg_len, base_y + int(10 * S)), max(1, int(2 * S))
                )
                pygame.draw.line(
                    surf, color_mortar, (base_x, base_y), (base_x + dir_mul * leg_len, base_y + int(10 * S)), max(1, int(2 * S))
                )
                tube_len = int(28 * S)
                tube_w = max(3, int(5 * S))
                tube_end = (base_x + dir_mul * int(tube_len * 0.8), base_y - int(14 * S))
                pygame.draw.line(surf, color_mortar, (base_x, base_y - int(2 * S)), tube_end, tube_w)
                pygame.draw.rect(surf, (80, 80, 85), (base_x - int(4 * S), base_y - int(2 * S), int(8 * S), int(6 * S)))
            else:
                folded_x = int(x - dir_mul * int(10 * S))
                folded_y = int(y + int(0 * S))
                pygame.draw.rect(
                    surf,
                    color_mortar,
                    (folded_x - int(10 * S), folded_y - int(4 * S), int(20 * S), int(6 * S)),
                    border_radius=max(1, int(2 * S)),
                )
                pygame.draw.line(
                    surf,
                    color_detail,
                    (folded_x - int(8 * S), folded_y - int(2 * S)),
                    (x - int(3 * S), folded_y + int(2 * S)),
                    max(1, int(1 * S)),
                )
        else:  # rifle
            hand_x = int(x + dir_mul * int(8 * S))
            hand_y = int(y + int(2 * S))
            barrel_len = int(28 * S)
            barrel_w = max(2, int(3 * S))
            stock = (x - dir_mul * int(6 * S), hand_y + int(2 * S))
            pygame.draw.line(surf, color_rifle, stock, (int(hand_x), hand_y), max(1, int(2 * S)))
            bx0 = int(hand_x)
            by0 = hand_y - int(1 * S)
            bx1 = int(bx0 + dir_mul * barrel_len)
            pygame.draw.line(surf, color_rifle, (bx0, by0), (bx1, by0), barrel_w)
            pygame.draw.circle(
                surf,
                color_detail,
                (int(bx0 + dir_mul * int(8 * S)), by0),
                max(1, int(1.5 * S)),
            )

        shadow_w = int(body_w * 1.2)
        shadow_h = int(6 * S)
        shadow_rect = pygame.Rect(0, 0, shadow_w, shadow_h)
        shadow_rect.center = (int(x), int(y + int(26 * S)))
        s_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (10, 10, 10, 100), (0, 0, shadow_rect.width, shadow_rect.height))
        surf.blit(s_surf, shadow_rect.topleft)

        bounds = pygame.Rect(int(x - body_w), int(y - int(12 * S)), int(body_w * 2), int(body_h * 2 + int(10 * S)))
        return bounds

    roles = ["panzerfaust", "panzerfaust", "mortar", "mortar", "rifle", "rifle"]
    for i, role in enumerate(roles):
        x = start_x + i * spacing * scale
        y = cy
        m_open = False
        if role == "mortar":
            m_index = 0 if i == 2 else 1
            m_open = mortar_flags[m_index]
        rect = draw_soldier_at(surface, x, y, role, mortar_open=m_open)
        results.append({"role": role, "rect": rect, "pos": (x, y)})

    return results


__all__ = ["SuperpowerManager", "BomberPower", "SquadPower"]
