"""Rendering helpers for Tanx pygame client."""

from __future__ import annotations

import math
from typing import List, Tuple

import pygame
import pygame.gfxdraw

from ...game import Game
from ...tank import Tank
from ..effects import Debris, Particle


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
    turret_length = app.cell_size * 0.8
    for idx, tank in enumerate(app.logic.tanks):
        if not tank.alive:
            continue
        color = app.tank_colors[idx % len(app.tank_colors)]
        x = offset_x + tank.x * app.cell_size
        y = tank.y * app.cell_size + offset_y
        body_rect = pygame.Rect(x, y, app.cell_size, app.cell_size)
        pygame.draw.rect(surface, color, body_rect, border_radius=6)

        center_x = x + app.cell_size / 2
        center_y = y + app.cell_size / 2
        angle = math.radians(tank.turret_angle)
        dx = math.cos(angle) * turret_length * tank.facing
        dy = -math.sin(angle) * turret_length
        end_pos = (center_x + dx, center_y + dy)
        pygame.draw.line(
            surface,
            pygame.Color("black"),
            (center_x, center_y - app.cell_size * 0.25),
            end_pos,
            4,
        )


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
