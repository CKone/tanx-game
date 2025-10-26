"""Rendering helpers for Tanx pygame client."""

from __future__ import annotations

import math
import random
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


def _camera_offset_px(app, parallax: float = 1.0) -> Tuple[int, int]:
    cam_x, cam_y = app.camera_offset
    return int(round(cam_x * parallax)), int(round(cam_y * parallax))


def _playfield_origin(app, parallax: float = 1.0) -> Tuple[int, int]:
    cam_dx, cam_dy = _camera_offset_px(app, parallax)
    return app.playfield_offset_x + cam_dx, app.ui_height + cam_dy


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
    offset_x, offset_y = _playfield_origin(app)

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
    style = app.terrain_style
    cam_x, cam_y = app.camera_offset

    sky_top = app.sky_color_top
    sky_bottom = app.sky_color_bottom
    gradient_shift = cam_y * 0.25
    for y in range(height):
        mix = (y + gradient_shift) / max(height - 1, 1)
        mix = max(0.0, min(1.0, mix))
        color = pygame.Color(
            int(sky_top.r * (1 - mix) + sky_bottom.r * mix),
            int(sky_top.g * (1 - mix) + sky_bottom.g * mix),
            int(sky_top.b * (1 - mix) + sky_bottom.b * mix),
        )
        surface.fill(color, pygame.Rect(0, y, width, 1))

    world_width_px = app.world_width * app.cell_size
    playfield_left = app.playfield_offset_x
    playfield_right = playfield_left + world_width_px

    # Distant hills for the classic map style
    if style == "classic" and app._distant_hills:
        hill_points = []
        origin_x, origin_y = _playfield_origin(app, parallax=0.15)
        base_line = origin_y + int(world_width_px * 0.08)
        for x_world, elevation in app._distant_hills:
            x = origin_x + int(round(x_world * app.cell_size))
            y = base_line - int(round(elevation * app.cell_size * 0.3))
            hill_points.append((x, y))
        if hill_points:
            hill_points.append((playfield_right + _camera_offset_px(app, 0.15)[0], height))
            hill_points.append((playfield_left + _camera_offset_px(app, 0.15)[0], height))
            pygame.draw.polygon(surface, pygame.Color(62, 94, 82), hill_points)

    # Skyline silhouettes (primarily for urban maps)
    skyline = getattr(app, "_skyline_shapes", [])
    if skyline:
        parallax = 0.22 if style == "urban" else 0.18
        offset_x, offset_y = _playfield_origin(app, parallax=parallax)
        base_line = offset_y + int(app.world_height * app.cell_size * 0.28)
        for shape in skyline:
            x_world = shape["x"]
            width_world = shape["width"]
            height_world = shape["height"]
            color = shape["color"]
            x = offset_x + int(round(x_world * app.cell_size))
            w = int(round(width_world * app.cell_size))
            h = int(round(height_world * app.cell_size))
            if x + w < -64 or x > width + 64 or h <= 2:
                continue
            rect = pygame.Rect(x, base_line - h, w, h)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, _blend_color(color, pygame.Color(10, 10, 16), 0.5), rect, 1)
            lights = shape.get("lights") if isinstance(shape, dict) else None
            if style == "urban" and lights:
                for entry in lights:
                    rx = entry["rx"]
                    ry = entry["ry"]
                    size = entry["size"]
                    intensity = entry["intensity"] * (0.7 + 0.3 * math.sin(app.time_elapsed * 2.3 + rx * 8.0))
                    lw = max(2, int(rect.width * size * 0.6))
                    lh = max(2, int(rect.height * size * 0.6))
                    lx = rect.left + int(rect.width * rx) - lw // 2
                    ly = rect.top + int(rect.height * ry)
                    window_rect = pygame.Rect(lx, ly, lw, lh)
                    pygame.draw.rect(surface, pygame.Color(255, 220, 140, int(180 * intensity)), window_rect)

    # Cloud layers with parallax drift
    cloud_base_y = app.ui_height - int(app.cell_size * 3)
    for idx, layer in enumerate(app._cloud_layers):
        cloud_surface: pygame.Surface = layer["surface"]
        parallax = layer["parallax"]
        cam_dx, cam_dy = _camera_offset_px(app, parallax)
        offset = layer["offset"]
        tile_width = cloud_surface.get_width()
        y_pos = cloud_base_y + idx * int(app.cell_size * 1.8) + cam_dy
        start_x = playfield_left + cam_dx - int(offset)
        for x in range(start_x - tile_width, width + tile_width, tile_width):
            surface.blit(cloud_surface, (x, y_pos))


def draw_world(app) -> None:
    game: Game = app.logic
    world = game.world
    detail = world.detail
    surface = app.screen
    cell = app.cell_size
    width_px = world.width * cell
    height_px = world.height * cell
    scale_factor = 2

    hi_size = (width_px * scale_factor, height_px * scale_factor)
    if app._terrain_hi_surface is None or app._terrain_hi_surface.get_size() != hi_size:
        app._terrain_hi_surface = pygame.Surface(hi_size, pygame.SRCALPHA)
    if app._terrain_surface is None or app._terrain_surface.get_size() != (width_px, height_px):
        app._terrain_surface = pygame.Surface((width_px, height_px), pygame.SRCALPHA)

    hi_surface = app._terrain_hi_surface
    hi_surface.fill((0, 0, 0, 0))

    surface_points_hi: List[tuple[int, int]] = []
    surface_points: List[tuple[int, int]] = []
    for hx in range(world.grid_width):
        x_world = hx / detail
        height_value = world.height_map[hx]
        surface_points_hi.append(
            (
                int(round(x_world * cell * scale_factor)),
                int(round(height_value * cell * scale_factor)),
            )
        )
        surface_points.append(
            (
                int(round(x_world * cell)),
                int(round(height_value * cell)),
            )
        )

    if not surface_points_hi:
        return

    light = pygame.math.Vector2(-0.35, -1.0)
    if light.length_squared() > 0:
        light = light.normalize()
    rock_color = pygame.Color(110, 112, 118)
    soil_color = pygame.Color(165, 126, 76)
    grass_color = pygame.Color(104, 164, 92)
    grass_thickness_hi = int(cell * scale_factor * 0.45)
    soil_thickness_hi = int(cell * scale_factor * 1.6)
    bottom_hi = height_px * scale_factor

    def shade(col: pygame.Color, factor: float) -> Tuple[int, int, int, int]:
        return (
            min(255, max(0, int(col.r * factor))),
            min(255, max(0, int(col.g * factor))),
            min(255, max(0, int(col.b * factor))),
            255,
        )

    for idx in range(len(surface_points_hi) - 1):
        x0, y0 = surface_points_hi[idx]
        x1, y1 = surface_points_hi[idx + 1]
        if x0 == x1:
            continue
        h0 = world.height_map[idx]
        h1 = world.height_map[min(idx + 1, len(world.height_map) - 1)]
        dx = 1.0 / detail
        dy = h1 - h0
        tangent = pygame.math.Vector2(dx, dy)
        if tangent.length_squared() == 0:
            tangent = pygame.math.Vector2(0.0, 1.0)
        normal = pygame.math.Vector2(-tangent.y, tangent.x)
        if normal.length_squared() == 0:
            normal = pygame.math.Vector2(0.0, 1.0)
        normal = normal.normalize()
        shade_factor = 0.35 + 0.65 * max(0.0, normal.dot(light))

        rock_poly = [(x0, y0), (x1, y1), (x1, bottom_hi), (x0, bottom_hi)]
        rock_col = shade(rock_color, shade_factor)
        pygame.gfxdraw.filled_polygon(hi_surface, rock_poly, rock_col)
        pygame.gfxdraw.aapolygon(hi_surface, rock_poly, rock_col)

        soil_poly = [
            (x0, y0),
            (x1, y1),
            (x1, min(bottom_hi, y1 + soil_thickness_hi)),
            (x0, min(bottom_hi, y0 + soil_thickness_hi)),
        ]
        soil_col = shade(soil_color, shade_factor)
        pygame.gfxdraw.filled_polygon(hi_surface, soil_poly, soil_col)
        pygame.gfxdraw.aapolygon(hi_surface, soil_poly, soil_col)

        grass_poly = [
            (x0, y0),
            (x1, y1),
            (x1, min(bottom_hi, y1 + grass_thickness_hi)),
            (x0, min(bottom_hi, y0 + grass_thickness_hi)),
        ]
        grass_col = shade(grass_color, shade_factor)
        pygame.gfxdraw.filled_polygon(hi_surface, grass_poly, grass_col)
        pygame.gfxdraw.aapolygon(hi_surface, grass_poly, grass_col)

    pygame.draw.aalines(hi_surface, app.crater_rim_color, False, surface_points_hi, blend=1)

    terrain_surface = pygame.transform.smoothscale(hi_surface, (width_px, height_px))
    app._terrain_surface = terrain_surface
    texture = getattr(app, "terrain_texture", None)
    if texture is not None:
        tex_w, tex_h = texture.get_size()
        for x in range(0, width_px, tex_w):
            for y in range(0, height_px, tex_h):
                terrain_surface.blit(texture, (x, y), special_flags=pygame.BLEND_MULT)

    offset_x, offset_y = _playfield_origin(app)
    surface.blit(terrain_surface, (offset_x, offset_y))

    outline_points = [
        (offset_x + x, offset_y + y) for x, y in surface_points
    ]
    pygame.draw.aalines(surface, app.crater_rim_color, False, outline_points, blend=1)


def draw_rubble(app) -> None:
    world = app.logic.world
    rubble = getattr(world, "rubble_segments", None)
    if not rubble:
        return

    surface = app.screen
    cell = app.cell_size
    offset_x, offset_y = _playfield_origin(app)
    clip_rect = pygame.Rect(0, offset_y, surface.get_width(), surface.get_height() - offset_y)

    base_color = pygame.Color(118, 105, 94)
    highlight_base = pygame.Color(170, 158, 146)
    shadow = pygame.Color(74, 64, 56)

    for segment in rubble:
        if segment.destroyed or segment.height <= 0:
            continue
        left_px = offset_x + int(round(segment.left * cell))
        right_px = offset_x + int(round(segment.right * cell))
        width_px = max(2, right_px - left_px)
        ground_left = world.ground_height(segment.left)
        ground_right = world.ground_height(segment.right)
        draw_base = segment.base
        if ground_left is not None and ground_right is not None:
            draw_base = min(draw_base, (ground_left + ground_right) * 0.5)
        top_world = draw_base - segment.height
        bottom_world = draw_base
        rect_top = offset_y + int(round(top_world * cell))
        rect_bottom = offset_y + int(round(bottom_world * cell))
        rect_height = rect_bottom - rect_top
        if rect_height <= 0:
            continue
        rect = pygame.Rect(left_px, rect_top, width_px, rect_height)
        if not rect.colliderect(clip_rect):
            continue
        rect = rect.clip(clip_rect)
        integrity = segment.hp / segment.max_hp if segment.max_hp else 0.0
        fill = _blend_color(base_color, pygame.Color(90, 72, 60), 1.0 - integrity)
        pygame.draw.rect(surface, fill, rect)
        pygame.draw.rect(surface, shadow, rect, 1)
        groove_count = max(1, width_px // max(6, int(cell * 0.5)))
        for groove in range(1, groove_count):
            x = rect.left + int(round(groove * (rect.width / groove_count)))
            pygame.draw.line(surface, shadow, (x, rect.top), (x, rect.bottom), 1)
        if integrity < 0.95:
            collapse_depth = int(rect.height * (1.0 - integrity) * 0.5)
            if collapse_depth > 0:
                pygame.draw.rect(
                    surface,
                    shadow,
                    pygame.Rect(rect.left, rect.top, rect.width, collapse_depth),
                    0,
                )
        highlight_rect = rect.inflate(-rect.width * 0.3, -rect.height * 0.4)
        highlight = _blend_color(highlight_base, pygame.Color(200, 190, 176), integrity)
        if highlight_rect.width > 0 and highlight_rect.height > 0:
            pygame.draw.rect(surface, highlight, highlight_rect, 1)


def draw_buildings(app) -> None:
    world = app.logic.world
    buildings = getattr(world, "buildings", None)
    if not buildings:
        return

    surface = app.screen
    cell = app.cell_size
    offset_x = app.playfield_offset_x
    offset_y = app.ui_height

    style_colors = {
        "block": pygame.Color(92, 104, 120),
        "loft": pygame.Color(136, 120, 108),
        "tower": pygame.Color(86, 108, 150),
    }
    rubble_color = pygame.Color(124, 92, 72)
    unstable_color = pygame.Color(215, 178, 72)

    clip_rect = pygame.Rect(0, offset_y, surface.get_width(), surface.get_height() - offset_y)

    height_map = world.height_map
    detail = world.detail

    for building in sorted(buildings, key=lambda b: b.base, reverse=True):
        if building.collapsed:
            continue
        base_color = style_colors.get(building.style, pygame.Color(102, 112, 128))
        left_px = offset_x + int(round(building.left * cell))
        right_px = offset_x + int(round(building.right * cell))
        width_px = max(3, right_px - left_px)

        column = int(round(((building.left + building.right) * 0.5) * detail))
        column = max(0, min(len(height_map) - 1, column))
        ground_height = height_map[column]
        floor_bottom = min(building.base, ground_height)
        first_intact = building.first_intact_floor_index()
        for idx, floor in enumerate(building.floors):
            floor_top = floor_bottom - floor.height
            top_world = min(floor_top, floor_bottom)
            bottom_world = max(floor_top, floor_bottom)

            rect_top = offset_y + int(round(top_world * cell))
            rect_bottom = offset_y + int(round(bottom_world * cell))
            rect_height = rect_bottom - rect_top
            if rect_height <= 0:
                floor_bottom = floor_top
                continue

            rect = pygame.Rect(left_px, rect_top, width_px, rect_height)
            if not rect.colliderect(clip_rect):
                floor_bottom = floor_top
                continue
            rect = rect.clip(clip_rect)

            integrity = floor.hp / floor.max_hp if floor.max_hp else 0.0

            if floor.destroyed:
                fill_color = rubble_color
            else:
                brightness = max(0.55, 1.0 - 0.08 * idx)
                damaged_tone = _blend_color(base_color, pygame.Color(150, 120, 90), 1.0 - integrity)
                fill_color = _scale_color(_blend_color(damaged_tone, pygame.Color("white"), 0.18 * idx), brightness)

            pygame.draw.rect(surface, fill_color, rect)

            if floor.destroyed:
                rubble_rng = random.Random((building.id << 8) + idx)
                debris_rows = max(2, rect.height // max(6, int(cell * 0.45)))
                for row in range(debris_rows):
                    y = rect.bottom - 1 - row * max(3, rect.height // (debris_rows + 4))
                    if y <= rect.top:
                        break
                    x_start = rect.left + rubble_rng.randint(0, max(1, rect.width // 6))
                    x_end = rect.right - rubble_rng.randint(0, max(1, rect.width // 6))
                    pygame.draw.line(surface, _blend_color(rubble_color, pygame.Color(90, 72, 60), 0.3), (x_start, y), (x_end, y), 2)
            elif rect.width > 10 and rect.height > 10:
                window_cols = max(1, rect.width // max(7, int(cell * 0.75)))
                window_rows = max(1, rect.height // max(12, int(cell * 1.1)))
                window_w = max(3, (rect.width - (window_cols + 1) * 3) // window_cols)
                window_h = max(3, (rect.height - (window_rows + 1) * 3) // window_rows)
                glass_color = _blend_color(fill_color, pygame.Color(220, 230, 240), 0.65)
                sill_color = _blend_color(fill_color, pygame.Color(40, 40, 40), 0.55)
                for row in range(window_rows):
                    for col in range(window_cols):
                        wx = rect.left + 3 + col * (window_w + 3)
                        wy = rect.top + 3 + row * (window_h + 3)
                        window_rect = pygame.Rect(wx, wy, window_w, window_h)
                        pygame.draw.rect(surface, glass_color, window_rect)
                        pygame.draw.line(surface, sill_color, window_rect.bottomleft, window_rect.bottomright, 1)

                if integrity < 0.65:
                    crack_rng = random.Random((building.id << 6) ^ idx)
                    crack_count = max(2, rect.width // max(18, int(cell)))
                    crack_color = _blend_color(pygame.Color(30, 24, 20), fill_color, 0.4)
                    for _ in range(crack_count):
                        start_x = crack_rng.randint(rect.left + 2, rect.right - 2)
                        start_y = crack_rng.randint(rect.top + 2, rect.bottom - 4)
                        end_x = start_x + crack_rng.randint(-rect.width // 4, rect.width // 4)
                        end_y = start_y + crack_rng.randint(4, rect.height // 2)
                        pygame.draw.line(surface, crack_color, (start_x, start_y), (max(rect.left + 1, min(rect.right - 1, end_x)), min(rect.bottom - 1, end_y)), 1)

            border_color = _blend_color(fill_color, pygame.Color(24, 24, 28), 0.6)
            pygame.draw.rect(surface, border_color, rect, 1)

            if building.unstable and first_intact is not None and not floor.destroyed and idx == first_intact:
                hazard = rect.inflate(-6, -6)
                if hazard.width > 4 and hazard.height > 4:
                    pygame.draw.rect(surface, unstable_color, hazard, 2)

            floor_bottom = floor_top

        roof_world = min(building.top, building.base)
        roof_y = offset_y + int(round(roof_world * cell))
        roof_rect = pygame.Rect(left_px - 1, roof_y - 4, width_px + 2, 5)
        roof_rect = roof_rect.clip(clip_rect)
        if roof_rect.height > 0:
            roof_color = _blend_color(base_color, pygame.Color("white"), 0.35)
            pygame.draw.rect(surface, roof_color, roof_rect)
            pygame.draw.line(surface, _blend_color(roof_color, pygame.Color(18, 18, 26), 0.6), roof_rect.topleft, roof_rect.topright, 1)


def draw_tanks(app) -> None:
    surface = app.screen
    offset_x, offset_y = _playfield_origin(app)
    cell = app.cell_size
    track_height = cell * 0.28
    hull_height = cell * 0.52
    turret_radius = cell * 0.28
    barrel_length = cell * 0.9
    barrel_width = cell * 0.16

    dark_grey = pygame.Color(32, 36, 42)
    steel = pygame.Color(180, 190, 204)
    recoil_duration = getattr(app, "_recoil_duration", 0.18)

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
        suspension_offset = math.sin(tank.suspension_phase) * tank.suspension_amplitude * cell
        base_y = offset_y + ground * cell + suspension_offset
        facing = tank.facing
        recoil_progress = min(1.0, tank.recoil_timer / max(0.01, recoil_duration))
        recoil_offset = -facing * cell * 0.22 * recoil_progress

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
        wheel_y = track_rect.bottom - wheel_radius * 1.05
        for i in range(4):
            wheel_x = track_rect.left + wheel_radius + wheel_spacing * i
            wobble = math.sin(tank.suspension_phase + i * 0.6) * cell * 0.02
            pygame.draw.circle(surface, wheel_color, (int(wheel_x), int(wheel_y + wobble)), int(wheel_radius))
            pygame.draw.circle(surface, dark_grey, (int(wheel_x), int(wheel_y + wobble)), int(wheel_radius * 0.55))

        # Hull --------------------------------------------------------------------
        hull_height_px = max(4, int(round(hull_height)))
        hull_width_px = max(4, int(round(cell * 1.1)))
        hull_left = int(round(x - cell * 0.05))
        hull_top = track_rect.top - hull_height_px
        hull_rect = pygame.Rect(hull_left, hull_top - int(suspension_offset * 0.25), hull_width_px, hull_height_px)
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
        turret_center_x = x + cell * 0.5 + facing * cell * 0.05 + recoil_offset
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
        end_x = pivot[0] + dir_x * barrel_length + recoil_offset
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

        if recoil_progress > 0.0:
            flash_radius = max(2, int(cell * 0.18 * recoil_progress))
            flash_color = pygame.Color(255, 220, 120, int(200 * recoil_progress))
            angle_vec = pygame.math.Vector2(math.cos(angle) * facing, -math.sin(angle))
            tip = pygame.math.Vector2(end_x, end_y) + angle_vec * cell * 0.12
            pygame.draw.circle(surface, flash_color, (int(tip.x), int(tip.y)), flash_radius)


def draw_projectile(app, position: tuple[float, float]) -> None:
    surface = app.screen
    offset_x, offset_y = _playfield_origin(app)
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
    offset_x, offset_y = _playfield_origin(app)
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
    offset_x, offset_y = _playfield_origin(app)
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
    offset_x, offset_y = _playfield_origin(app)
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


def draw_smoke(app) -> None:
    if not app.effects.smoke:
        return
    surface = app.screen
    offset_x, offset_y = _playfield_origin(app, parallax=0.98)
    cell = app.cell_size
    for particle in app.effects.smoke:
        life_ratio = max(0.0, min(particle.life / particle.max_life, 1.0))
        alpha = int(160 * life_ratio)
        if alpha <= 8:
            continue
        radius_px = max(2, int(particle.radius * cell))
        color = pygame.Color(*particle.color, alpha)
        px = int(offset_x + particle.x * cell)
        py = int(offset_y + particle.y * cell)
        pygame.draw.circle(surface, color, (px, py), radius_px)

    if app.effects.embers:
        for ember in app.effects.embers:
            life_ratio = max(0.0, min(ember.life / ember.max_life, 1.0))
            alpha = int(255 * life_ratio)
            if alpha <= 0:
                continue
            color = pygame.Color(*ember.color, alpha)
            px = int(offset_x + ember.x * cell)
            py = int(offset_y + ember.y * cell)
            radius = max(1, int(ember.radius * cell))
            pygame.draw.circle(surface, color, (px, py), radius)


def draw_explosions(app) -> None:
    if not app.effects.explosions:
        return
    surface = app.screen
    offset_x, offset_y = _playfield_origin(app)
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


def draw_weather(app) -> None:
    effects = app.effects
    if not effects.weather_drops:
        return
    surface = app.screen
    weather = effects.weather_type
    if weather == "clear":
        return
    offset_x, offset_y = _playfield_origin(app, parallax=0.9)
    cell = app.cell_size
    if weather == "rain":
        color = pygame.Color(170, 190, 220, 170)
        for drop in effects.weather_drops:
            start_x = offset_x + drop.x * cell
            start_y = offset_y + drop.y * cell
            end_x = start_x - drop.vx * cell * 0.08
            end_y = start_y - drop.vy * cell * 0.08
            pygame.draw.line(surface, color, (start_x, start_y), (end_x, end_y), 1)
    else:  # snow
        for drop in effects.weather_drops:
            fade = max(0.2, min(1.0, 1.0 - drop.y / (app.world_height + 2.0)))
            alpha = int(220 * fade)
            color = pygame.Color(255, 255, 255, alpha)
            radius = max(1, int(drop.length * cell * 0.6))
            cx = int(offset_x + drop.x * cell)
            cy = int(offset_y + drop.y * cell)
            pygame.draw.circle(surface, color, (cx, cy), radius)


__all__ = [
    "draw_background",
    "draw_world",
    "draw_rubble",
    "draw_buildings",
    "draw_tanks",
    "draw_aim_indicator",
    "draw_projectile",
    "draw_trails",
    "draw_particles",
    "draw_debris",
    "draw_explosions",
    "draw_smoke",
    "draw_weather",
]
