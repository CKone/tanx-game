"""Menu and HUD rendering helpers for the pygame client."""

from __future__ import annotations

import math

import pygame


def draw_ui(app) -> None:
    surface = app.screen
    width, height = surface.get_size()
    panel_height = app.ui_height
    panel_top = height - panel_height

    # Draw a translucent panel at the bottom of the screen
    overlay = pygame.Surface((width, panel_height), pygame.SRCALPHA)
    overlay.fill((10, 12, 20, 235))
    surface.blit(overlay, (0, panel_top))

    stats_top = panel_top + 16
    section_padding = 20
    bar_height = 16
    bar_spacing = 6
    text_color = pygame.Color(230, 230, 230)
    text_muted = pygame.Color(180, 188, 200)

    def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))

    def angle_to_screen(angle_deg: float, facing: int) -> float:
        if facing >= 0:
            return math.radians(angle_deg)
        return math.radians(180 - angle_deg)

    def draw_angle_dial(center: tuple[int, int], radius: int, tank, tank_index: int) -> None:
        base_color = pygame.Color(30, 34, 48)
        ring_color = pygame.Color(80, 86, 110)
        guide_color = pygame.Color(55, 62, 84)
        accent = pygame.Color(app.tank_colors[tank_index % len(app.tank_colors)])
        if tank_index == app.current_player:
            accent = pygame.Color(
                min(255, accent.r + 40),
                min(255, accent.g + 40),
                min(255, accent.b + 40),
            )

        pygame.draw.circle(surface, base_color, center, radius)
        pygame.draw.circle(surface, ring_color, center, radius, width=2)

        arc_rect = pygame.Rect(
            center[0] - radius + 3,
            center[1] - radius + 3,
            (radius - 3) * 2,
            (radius - 3) * 2,
        )
        min_angle = angle_to_screen(tank.min_angle, tank.facing)
        max_angle = angle_to_screen(tank.max_angle, tank.facing)
        start_angle, end_angle = sorted((min_angle, max_angle))
        pygame.draw.arc(surface, ring_color, arc_rect, start_angle, end_angle, 2)

        zero_angle = angle_to_screen(0, tank.facing)
        zero_end = (
            center[0] + int(math.cos(zero_angle) * (radius - 6)),
            center[1] - int(math.sin(zero_angle) * (radius - 6)),
        )
        pygame.draw.line(surface, guide_color, center, zero_end, 2)

        turret_angle = angle_to_screen(tank.turret_angle, tank.facing)
        pointer_end = (
            center[0] + int(math.cos(turret_angle) * (radius - 6)),
            center[1] - int(math.sin(turret_angle) * (radius - 6)),
        )
        pygame.draw.line(surface, accent, center, pointer_end, 3)
        pygame.draw.circle(surface, accent, pointer_end, 4)

        angle_surface = app.font_small.render(f"{tank.turret_angle}°", True, text_color)
        angle_rect = angle_surface.get_rect(center=center)
        surface.blit(angle_surface, angle_rect)

    def draw_progress_bar(
        bar_rect: pygame.Rect,
        ratio: float,
        label: str,
        value_text: str,
        fill_color: pygame.Color,
    ) -> None:
        pygame.draw.rect(surface, pygame.Color(36, 40, 54), bar_rect, border_radius=6)
        fill_width = int(bar_rect.width * clamp(ratio))
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_rect.height)
            pygame.draw.rect(surface, fill_color, fill_rect, border_radius=6)
        pygame.draw.rect(surface, pygame.Color(14, 16, 24), bar_rect, width=1, border_radius=6)

        label_surface = app.font_small.render(label, True, text_color)
        label_rect = label_surface.get_rect(left=bar_rect.left + 8, centery=bar_rect.centery)
        surface.blit(label_surface, label_rect)

        value_surface = app.font_small.render(value_text, True, text_muted)
        value_rect = value_surface.get_rect(right=bar_rect.right - 8, centery=bar_rect.centery)
        surface.blit(value_surface, value_rect)

    tanks = list(app.logic.tanks)
    if not tanks:
        return

    section_width = width // len(tanks)

    for idx, tank in enumerate(tanks):
        section_left = idx * section_width
        section_right = (
            section_left + section_width if idx < len(tanks) - 1 else width
        )
        inner_left = section_left + section_padding
        inner_right = section_right - section_padding
        available_width = max(1, inner_right - inner_left)
        dial_radius = clamp(available_width / 6, 18, 28)
        dial_radius = int(dial_radius)
        name_surface = app.font_regular.render(tank.name, True, text_color)
        name_y = stats_top
        name_x = inner_left if idx == 0 else max(inner_left, inner_right - name_surface.get_width())
        surface.blit(name_surface, (name_x, name_y))

        center_layout = False
        if idx == 0:
            dial_center_x = inner_right - dial_radius
            bar_area_left = inner_left
            bar_area_right = dial_center_x - dial_radius - 12
        else:
            dial_center_x = inner_left + dial_radius
            bar_area_left = dial_center_x + dial_radius + 12
            bar_area_right = inner_right

        if bar_area_right - bar_area_left < 120:
            # Fallback to a centered layout if the screen is too narrow
            bar_area_left = inner_left
            bar_area_right = inner_right
            dial_center_x = (inner_left + inner_right) // 2
            center_layout = True

        bar_left = int(bar_area_left)
        bar_right = int(bar_area_right)
        if bar_right <= bar_left:
            bar_left = inner_left
            bar_right = inner_right
        max_bar_width = max(1, inner_right - inner_left)
        bar_width = max(60, min(bar_right - bar_left, max_bar_width))
        bar_right = bar_left + bar_width
        if bar_right > inner_right:
            bar_right = inner_right
            bar_left = bar_right - bar_width
        if bar_left < inner_left:
            bar_left = inner_left
            bar_right = min(inner_right, bar_left + bar_width)
        bar_width = bar_right - bar_left
        if bar_width <= 0:
            bar_width = max(60, max_bar_width // 2)
            bar_left = inner_left
            bar_right = min(inner_right, bar_left + bar_width)

        bar_total_height = bar_height * 3 + bar_spacing * 2
        if center_layout:
            dial_center_y = name_y + name_surface.get_height() + dial_radius + 6
            bar_top = dial_center_y + dial_radius + 10
        else:
            bar_top = name_y + name_surface.get_height() + 6
            dial_center_y = bar_top + bar_total_height // 2

        bar_rects = []
        current_y = bar_top
        for _ in range(3):
            rect = pygame.Rect(bar_left, current_y, bar_width, bar_height)
            bar_rects.append(rect)
            current_y += bar_height + bar_spacing

        max_hp = getattr(tank, "max_hp", 100)
        health_ratio = clamp(tank.hp / max_hp if max_hp else 0)
        health_color = pygame.Color(210, 80, 80)
        if tank.hp > max_hp * 0.6:
            health_color = pygame.Color(120, 200, 120)
        elif tank.hp > max_hp * 0.3:
            health_color = pygame.Color(230, 180, 90)
        draw_progress_bar(
            bar_rects[0],
            health_ratio,
            "Health",
            f"{int(tank.hp)}/{max_hp}",
            health_color,
        )

        power_range = max(0.001, tank.max_power - tank.min_power)
        power_ratio = clamp((tank.shot_power - tank.min_power) / power_range)
        power_color = pygame.Color(90, 160, 230)
        draw_progress_bar(
            bar_rects[1],
            power_ratio,
            "Power",
            f"{tank.shot_power:.2f}x",
            power_color,
        )

        super_ratio = clamp(tank.super_power)
        super_ready = super_ratio >= 1.0 - 1e-3
        super_color = pygame.Color(240, 200, 90) if super_ready else pygame.Color(200, 120, 230)
        super_value = "Ready" if super_ready else f"{int(super_ratio * 100):02d}%"
        draw_progress_bar(
            bar_rects[2],
            super_ratio,
            "Super",
            super_value,
            super_color,
        )

        draw_angle_dial((dial_center_x, dial_center_y), dial_radius, tank, idx)

    message = app.message or ""
    if message:
        message_surface = app.font_regular.render(message, True, text_color)
        message_rect = message_surface.get_rect(center=(width // 2, panel_top + 28))
        surface.blit(message_surface, message_rect)

    instruction_parts = [
        "P1: A/D move, W/S aim, Space fire, Q/E power",
        "P2: ←/→ move, ↑/↓ aim, Enter fire, [/ ] power",
        "Esc: pause menu",
    ]
    if app.cheat_enabled:
        instruction_parts.append("F1: cheat console")
    instructions_text = "   |   ".join(instruction_parts)
    instructions_surface = app.font_small.render(instructions_text, True, text_muted)
    instructions_rect = instructions_surface.get_rect(centerx=width // 2)
    bottom_margin = max(20, panel_height // 4)
    instructions_rect.bottom = panel_top + panel_height - bottom_margin
    if instructions_rect.bottom < panel_top + instructions_surface.get_height() + 12:
        instructions_rect.bottom = panel_top + instructions_surface.get_height() + 12
    surface.blit(instructions_surface, instructions_rect)

    if app.cheat_enabled and app.cheat_menu_visible:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        menu_lines = [
            "Cheat Console",
            "1 - Detonate Player 1",
            "2 - Detonate Player 2",
            "3 - Max Superpower",
            "F1 / Esc - Close",
        ]
        for idx, line in enumerate(menu_lines):
            font = app.font_large if idx == 0 else app.font_regular
            text_surface = font.render(line, True, pygame.Color("white"))
            rect = text_surface.get_rect(
                center=(surface.get_width() / 2, surface.get_height() / 2 + idx * 36)
            )
            surface.blit(text_surface, rect)


def draw_menu_overlay(app) -> None:
    if app.state not in {"main_menu", "pause_menu", "post_game_menu", "settings_menu", "keybind_menu"}:
        return
    surface = app.screen
    alpha = 200 if app.state in {"main_menu", "settings_menu"} else 160
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, alpha))
    surface.blit(overlay, (0, 0))

    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2

    title_lines = app.menu.title.splitlines() or [app.menu.title]
    line_spacing = max(6, app.font_large.get_height() // 6)
    title_surfaces = [
        app.font_large.render(line, True, pygame.Color("white"))
        for line in title_lines
    ]
    total_height = sum(s.get_height() for s in title_surfaces)
    if len(title_surfaces) > 1:
        total_height += line_spacing * (len(title_surfaces) - 1)
    block_top = center_y - 120 - total_height // 2
    current_top = block_top
    title_bottom = center_y - 120
    for title_surface in title_surfaces:
        line_height = title_surface.get_height()
        line_center_y = current_top + line_height // 2
        title_rect = title_surface.get_rect(center=(center_x, line_center_y))
        surface.blit(title_surface, title_rect)
        title_bottom = title_rect.bottom
        current_top = title_rect.bottom + line_spacing

    if app.menu.message:
        message_surface = app.font_regular.render(
            app.menu.message, True, pygame.Color(220, 220, 220)
        )
        message_rect = message_surface.get_rect(center=(center_x, title_bottom + 36))
        surface.blit(message_surface, message_rect)
        options_start_y = message_rect.bottom + 24
    else:
        options_start_y = title_bottom + 32

    option_spacing = 40
    option_font = app.font_regular
    option_height = option_font.get_height()
    if app.state == "keybind_menu":
        option_spacing = max(option_height + 8, 28)

    total_options_height = len(app.menu.options) * option_spacing
    max_start = surface.get_height() - 80 - total_options_height
    options_start_y = min(options_start_y, max_start)
    options_start_y = max(options_start_y, title_bottom + 16)

    for idx, option in enumerate(app.menu.options):
        is_selected = idx == app.menu.selection
        color = pygame.Color("white") if is_selected else pygame.Color(200, 200, 200)
        text_surface = option_font.render(option.label, True, color)
        text_rect = text_surface.get_rect(center=(center_x, options_start_y + idx * option_spacing))
        if is_selected:
            highlight = pygame.Surface((text_rect.width + 36, text_rect.height + 12), pygame.SRCALPHA)
            highlight.fill((255, 255, 255, 50))
            highlight_rect = highlight.get_rect(center=text_rect.center)
            surface.blit(highlight, highlight_rect)
        surface.blit(text_surface, text_rect)

    footer_text = None
    if app.state == "main_menu":
        footer_text = "Esc exits the game"
    elif app.state == "pause_menu":
        footer_text = "Esc resumes"
    elif app.state in {"settings_menu", "post_game_menu", "keybind_menu"}:
        footer_text = "Esc returns to the start menu" if app.state != "keybind_menu" else "Esc returns to Settings"

    if footer_text:
        footer_surface = app.font_small.render(footer_text, True, pygame.Color(180, 180, 180))
        footer_rect = footer_surface.get_rect(center=(center_x, surface.get_height() - 36))
        surface.blit(footer_surface, footer_rect)


__all__ = ["draw_ui", "draw_menu_overlay"]
