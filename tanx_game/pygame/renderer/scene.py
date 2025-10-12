"""Rendering helpers for Tanx pygame client."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pygame
import pygame.gfxdraw

from tanx_game.core.game import Game
from tanx_game.core.tank import Tank
from tanx_game.pygame.effects import Debris, Particle


def _scale_color(color: pygame.Color, factor: float) -> pygame.Color:
    return pygame.Color(
        max(0, min(255, int(color.r * factor))),
        max(0, min(255, int(color.g * factor))),
        max(0, min(255, int(color.b * factor))),
    )


def _blend_color(color: pygame.Color, other: pygame.Color, ratio: float) -> pygame.Color:
    clamped = max(0.0, min(1.0, ratio))
    inv = 1.0 - clamped
    return pygame.Color(
        int(color.r * inv + other.r * clamped),
        int(color.g * inv + other.g * clamped),
        int(color.b * inv + other.b * clamped),
    )


def _projectile_preview(
    game: Game,
    tank: Tank,
    *,
    full: bool = False,
    max_distance: float = 6.5,
    max_points: int = 36,
) -> tuple[list[tuple[float, float]], Optional[tuple[float, float]]]:
    result = game.step_projectile(tank, apply_effects=False)
    path = list(result.path)
    if not path:
        return [], None

    impact = None
    if result.impact_x is not None and result.impact_y is not None:
        impact = (result.impact_x, result.impact_y)

    if full:
        return path, impact

    trimmed: list[tuple[float, float]] = []
    travelled = 0.0
    prev_x = tank.x + 0.5 + tank.facing * 0.6
    prev_y = tank.y - 0.5
    for point in path:
        trimmed.append(point)
        travelled += math.hypot(point[0] - prev_x, point[1] - prev_y)
        prev_x, prev_y = point
        if len(trimmed) >= max_points or travelled >= max_distance:
            break
    return trimmed, impact


def draw_aim_indicator(app) -> None:
    if app.state != "playing":
        return
    if app.superpowers.is_active():
        return
    if app.session.is_animating_projectile():
        return

    current_tank = app.session.current_tank
    if not current_tank.alive:
        return

    full_preview = app.superpowers.has_trajectory_preview(app.current_player)
    preview, impact = _projectile_preview(
        app.logic,
        current_tank,
        full=full_preview,
        max_distance=8.0,
        max_points=48,
    )
    if not preview:
        return

    surface = app.screen
    cell = app.cell_size
    offset_x = app.playfield_offset_x
    offset_y = app.ui_height

    max_dots = 26 if full_preview else 14
    dot_count = min(max_dots, len(preview))
    if dot_count <= 0:
        return

    indices: list[int] = []
    last_index = -1
    for i in range(dot_count):
        t = i / max(dot_count - 1, 1)
        idx = min(int(round(t * (len(preview) - 1))), len(preview) - 1)
        if idx == last_index:
            idx = min(idx + 1, len(preview) - 1)
        indices.append(idx)
        last_index = idx

    base_color = app.tank_colors[app.session.current_player % len(app.tank_colors)]
    highlight_color = _blend_color(base_color, pygame.Color("white"), 0.35)

    base_radius = max(2, int(cell * 0.22))
    min_radius = max(1, int(cell * 0.08))

    for idx, preview_index in enumerate(indices):
        px, py = preview[preview_index]
        screen_x = int(round(offset_x + px * cell))
        screen_y = int(round(offset_y + py * cell))
        t = idx / max(dot_count - 1, 1)
        radius = max(min_radius, int(round(base_radius * (1.0 - 0.55 * t))))
        color_mix = _blend_color(base_color, highlight_color, 0.5 * (1.0 - t))
        pygame.draw.circle(surface, color_mix, (screen_x, screen_y), radius)
        if full_preview and idx == len(indices) - 1:
            ring_radius = max(radius + 2, radius * 2)
            pygame.draw.circle(surface, pygame.Color(250, 242, 180), (screen_x, screen_y), ring_radius, 2)

    if full_preview and impact is not None:
        ix, iy = impact
        screen_x = int(round(offset_x + ix * cell))
        screen_y = int(round(offset_y + iy * cell))
        marker_radius = max(4, int(cell * 0.18))
        pygame.draw.circle(surface, pygame.Color(255, 210, 120), (screen_x, screen_y), marker_radius)
        pygame.draw.circle(surface, pygame.Color(60, 40, 20), (screen_x, screen_y), marker_radius, 2)


def draw_background(app) -> None:
    surface = app.screen
    width = surface.get_width()
    height = surface.get_height()
    top = app.sky_color_top
    bottom = app.sky_color_bottom
    for y in range(height):
        mix = y / max(height - 1, 1)
        color = pygame.Color(
            int(top.r * (1 - mix) + bottom.r * mix),
            int(top.g * (1 - mix) + bottom.g * mix),
            int(top.b * (1 - mix) + bottom.b * mix),
        )
        pygame.draw.line(surface, color, (0, y), (width, y))


def draw_world(app) -> None:
    game: Game = app.logic
    world = game.world
    detail = world.detail
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    bottom = world.height * app.cell_size + offset_y

    surface_points: List[tuple[int, int]] = []
    for hx in range(world.grid_width):
        x_world = hx / detail
        height = world.height_map[hx]
        x_pix = offset_x + int(round(x_world * app.cell_size))
        y_pix = int(round(height * app.cell_size + offset_y))
        surface_points.append((x_pix, y_pix))

    if not surface_points:
        return

    light = pygame.math.Vector2(-0.35, -1.0)
    if light.length_squared() > 0:
        light = light.normalize()
    rock_color = pygame.Color(110, 112, 118)
    soil_color = pygame.Color(165, 126, 76)
    grass_color = pygame.Color(104, 164, 92)
    grass_thickness_px = int(app.cell_size * 0.45)
    soil_thickness_px = int(app.cell_size * 1.6)

    def shade(col: pygame.Color, factor: float) -> Tuple[int, int, int]:
        return (
            min(255, max(0, int(col.r * factor))),
            min(255, max(0, int(col.g * factor))),
            min(255, max(0, int(col.b * factor))),
        )

    for idx in range(len(surface_points) - 1):
        x0, y0 = surface_points[idx]
        x1, y1 = surface_points[idx + 1]
        if x0 == x1:
            continue
        h0 = world.height_map[idx]
        h1 = world.height_map[min(idx + 1, len(world.height_map) - 1)]
        dx = (1.0 / detail)
        dy = h1 - h0
        tangent = pygame.math.Vector2(dx, dy)
        if tangent.length_squared() == 0:
            tangent = pygame.math.Vector2(0.0, 1.0)
        normal = pygame.math.Vector2(-tangent.y, tangent.x)
        if normal.length_squared() == 0:
            normal = pygame.math.Vector2(0.0, 1.0)
        normal = normal.normalize()
        shade_factor = 0.35 + 0.65 * max(0.0, normal.dot(light))

        rock_poly = [(x0, y0), (x1, y1), (x1, bottom), (x0, bottom)]
        rock_col = shade(rock_color, shade_factor)
        pygame.gfxdraw.filled_polygon(surface, rock_poly, rock_col)
        pygame.gfxdraw.aapolygon(surface, rock_poly, rock_col)

        soil_col = shade(soil_color, shade_factor)
        soil_poly = [
            (x0, y0),
            (x1, y1),
            (x1, min(bottom, y1 + soil_thickness_px)),
            (x0, min(bottom, y0 + soil_thickness_px)),
        ]
        pygame.gfxdraw.filled_polygon(surface, soil_poly, soil_col)
        pygame.gfxdraw.aapolygon(surface, soil_poly, soil_col)

        grass_col = shade(grass_color, shade_factor)
        grass_poly = [
            (x0, y0),
            (x1, y1),
            (x1, min(bottom, y1 + grass_thickness_px)),
            (x0, min(bottom, y0 + grass_thickness_px)),
        ]
        pygame.gfxdraw.filled_polygon(surface, grass_poly, grass_col)
        pygame.gfxdraw.aapolygon(surface, grass_poly, grass_col)

    pygame.draw.aalines(surface, app.crater_rim_color, False, surface_points, blend=1)


def draw_tanks(app) -> None:
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    cell = app.cell_size
    track_height = cell * 0.28
    hull_height = cell * 0.52
    turret_radius = cell * 0.28
    barrel_length = cell * 0.9
    barrel_width = cell * 0.16

    dark_grey = pygame.Color(32, 36, 42)
    steel = pygame.Color(180, 190, 204)

    for idx, tank in enumerate(app.logic.tanks):
        if not tank.alive:
            continue

        base_color = app.tank_colors[idx % len(app.tank_colors)]
        hull_color = _scale_color(base_color, 1.0)
        hull_highlight = _scale_color(base_color, 1.18)
        hull_shadow = _scale_color(base_color, 0.75)
        track_color = _scale_color(base_color, 0.45)
        wheel_color = _blend_color(track_color, steel, 0.3)
        turret_color = _scale_color(base_color, 1.05)
        turret_shadow = _scale_color(base_color, 0.8)

        x = offset_x + tank.x * cell
        ground = app.logic.world.ground_height(tank.x + 0.5)
        if ground is None:
            ground = tank.y + 1
        base_y = offset_y + ground * cell
        facing = tank.facing

        # Tracks -----------------------------------------------------------------
        track_margin = cell * 0.06
        track_height_px = max(2, int(round(track_height)))
        track_width_px = max(2, int(round(cell + track_margin * 2)))
        track_left = int(round(x - track_margin))
        track_bottom = int(round(base_y))
        track_top = track_bottom - track_height_px
        track_rect = pygame.Rect(track_left, track_top, track_width_px, track_height_px)
        pygame.draw.rect(surface, track_color, track_rect, border_radius=int(track_height * 0.35))

        wheel_radius = cell * 0.14
        wheel_spacing = (track_rect.width - wheel_radius * 2) / 4
        wheel_y = track_rect.bottom - wheel_radius * 1.1
        for i in range(4):
            wheel_x = track_rect.left + wheel_radius + wheel_spacing * i
            pygame.draw.circle(surface, wheel_color, (int(wheel_x), int(wheel_y)), int(wheel_radius))
            pygame.draw.circle(surface, dark_grey, (int(wheel_x), int(wheel_y)), int(wheel_radius * 0.55))

        # Hull --------------------------------------------------------------------
        hull_height_px = max(4, int(round(hull_height)))
        hull_width_px = max(4, int(round(cell * 1.1)))
        hull_left = int(round(x - cell * 0.05))
        hull_top = track_rect.top - hull_height_px
        hull_rect = pygame.Rect(hull_left, hull_top, hull_width_px, hull_height_px)
        pygame.draw.rect(surface, hull_color, hull_rect, border_radius=int(cell * 0.18))

        # Hull shading strip
        highlight_rect = pygame.Rect(hull_rect)
        highlight_rect.height = int(hull_rect.height * 0.35)
        pygame.draw.rect(surface, hull_highlight, highlight_rect, border_radius=int(cell * 0.18))

        shadow_rect = pygame.Rect(hull_rect)
        shadow_rect.y += int(hull_rect.height * 0.55)
        shadow_rect.height = int(hull_rect.height * 0.45)
        pygame.draw.rect(surface, hull_shadow, shadow_rect, border_radius=int(cell * 0.14))

        # Turret ------------------------------------------------------------------
        turret_center_x = x + cell * 0.5 + facing * cell * 0.05
        turret_center_y = hull_rect.y + hull_rect.height * 0.4
        pygame.draw.circle(surface, turret_color, (int(turret_center_x), int(turret_center_y)), int(turret_radius))
        pygame.draw.circle(
            surface,
            turret_shadow,
            (int(turret_center_x - facing * cell * 0.06), int(turret_center_y + cell * 0.06)),
            int(turret_radius * 0.65),
        )

        # Barrel ------------------------------------------------------------------
        angle = math.radians(tank.turret_angle)
        dir_x = math.cos(angle) * facing
        dir_y = -math.sin(angle)
        pivot = (
            turret_center_x + dir_y * (barrel_width * 0.15),
            turret_center_y - dir_x * (barrel_width * 0.15),
        )
        half_width = barrel_width / 2
        end_x = pivot[0] + dir_x * barrel_length
        end_y = pivot[1] + dir_y * barrel_length
        perp_x = -dir_y
        perp_y = dir_x

        barrel_points = [
            (pivot[0] - perp_x * half_width, pivot[1] - perp_y * half_width),
            (pivot[0] + perp_x * half_width, pivot[1] + perp_y * half_width),
            (end_x + perp_x * half_width * 0.8, end_y + perp_y * half_width * 0.8),
            (end_x - perp_x * half_width * 0.8, end_y - perp_y * half_width * 0.8),
        ]
        pygame.draw.polygon(surface, turret_color, [(int(px), int(py)) for px, py in barrel_points])

        muzzle_radius = max(2, int(half_width * 0.75))
        pygame.draw.circle(surface, dark_grey, (int(end_x), int(end_y)), muzzle_radius)
        pygame.draw.circle(surface, steel, (int(end_x), int(end_y)), max(1, muzzle_radius // 2))

        # Hatch detail -------------------------------------------------------------
        hatch_radius = turret_radius * 0.45
        pygame.draw.circle(
            surface,
            _blend_color(turret_color, steel, 0.25),
            (
                int(turret_center_x + facing * cell * 0.05),
                int(turret_center_y - cell * 0.08),
            ),
            int(hatch_radius),
        )
        pygame.draw.circle(
            surface,
            _scale_color(turret_color, 0.6),
            (
                int(turret_center_x + facing * cell * 0.05),
                int(turret_center_y - cell * 0.08),
            ),
            max(1, int(hatch_radius * 0.45)),
        )

        # Body rivets --------------------------------------------------------------
        rivet_radius = max(1, int(cell * 0.04))
        for i in range(3):
            rivet_x = hull_rect.left + hull_rect.width * (0.2 + 0.3 * i)
            rivet_y = hull_rect.top + hull_rect.height * 0.32
            pygame.draw.circle(surface, _scale_color(base_color, 0.7), (int(rivet_x), int(rivet_y)), rivet_radius)


def draw_projectile(app, position: tuple[float, float]) -> None:
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    px = offset_x + position[0] * app.cell_size
    py = position[1] * app.cell_size + offset_y
    pygame.draw.circle(
        surface,
        app.projectile_color,
        (int(px), int(py)),
        max(3, app.cell_size // 4),
    )


def draw_trails(app) -> None:
    if not app.effects.trail_particles:
        return
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    duration = app.effects.trail_duration
    for (x, y), timer in app.effects.trail_particles:
        intensity = max(0.0, min(timer / duration, 1.0))
        radius = max(2, int(app.cell_size * 0.25 * intensity + 1))
        alpha = int(180 * intensity)
        blob = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            blob,
            (255, 240, 150, alpha),
            (radius, radius),
            radius,
        )
        screen_x = offset_x + x * app.cell_size - radius
        screen_y = y * app.cell_size + offset_y - radius
        surface.blit(blob, (screen_x, screen_y))


def draw_particles(app) -> None:
    if not app.effects.particles:
        return
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    for particle in app.effects.particles:
        alpha = max(0, min(255, int(255 * (particle.life / particle.max_life))))
        if alpha <= 0:
            continue
        color = pygame.Color(*particle.color, alpha)
        px = int(offset_x + particle.x * app.cell_size)
        py = int(particle.y * app.cell_size + offset_y)
        radius = max(1, int(particle.radius))
        pygame.draw.circle(surface, color, (px, py), radius)


def draw_debris(app) -> None:
    if not app.effects.debris:
        return
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    for chunk in app.effects.debris:
        alpha = max(0, min(255, int(255 * (chunk.life / chunk.max_life))))
        if alpha <= 0:
            continue
        sprite = pygame.Surface((chunk.width, chunk.height), pygame.SRCALPHA)
        sprite.fill((*chunk.color, alpha))
        rotated = pygame.transform.rotate(sprite, math.degrees(chunk.angle))
        rect = rotated.get_rect()
        rect.center = (
            offset_x + chunk.x * app.cell_size,
            chunk.y * app.cell_size + offset_y,
        )
        surface.blit(rotated, rect)


def draw_explosions(app) -> None:
    if not app.effects.explosions:
        return
    surface = app.screen
    offset_y = app.ui_height
    offset_x = app.playfield_offset_x
    duration = app.effects.explosion_duration
    for (x, y), timer, scale in app.effects.explosions:
        progress = 1 - min(max(timer / duration, 0.0), 1.0)
        radius = app.cell_size * (1.2 + progress * 1.3) * scale
        alpha = int(200 * (1 - progress))
        overlay = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            overlay,
            (255, 160, 64, max(60, alpha)),
            (int(radius), int(radius)),
            int(radius),
        )
        pygame.draw.circle(
            overlay,
            (255, 230, 120, 220),
            (int(radius), int(radius)),
            max(2, int(radius * 0.6)),
        )
        screen_x = offset_x + x * app.cell_size - radius
        screen_y = y * app.cell_size + offset_y - radius
        surface.blit(overlay, (screen_x, screen_y))


__all__ = [
    "draw_background",
    "draw_world",
    "draw_tanks",
    "draw_projectile",
    "draw_trails",
    "draw_particles",
    "draw_debris",
    "draw_explosions",
]
