"""Menu and HUD rendering helpers for the pygame client."""

from __future__ import annotations

import pygame


def draw_ui(app) -> None:
    surface = app.screen
    tank_panel = " | ".join(tank.info_line() for tank in app.logic.tanks)
    panel_surface = app.font_regular.render(tank_panel, True, pygame.Color("white"))
    message_surface = app.font_regular.render(app.message, True, pygame.Color("white"))

    panel_bg = pygame.Rect(0, 0, surface.get_width(), app.ui_height)
    pygame.draw.rect(surface, pygame.Color(0, 0, 0, 180), panel_bg)

    surface.blit(panel_surface, (16, 16))
    surface.blit(message_surface, (16, 48))

    instructions = [
        "Player 1: A/D move, W/S aim, Space fire, Q/E power",
        "Player 2: ←/→ move, ↑/↓ aim, Enter fire, [/ ] power",
        "Esc opens the pause menu",
    ]
    if app.cheat_enabled:
        instructions.append("F1 toggles the cheat console")
    for idx, line in enumerate(instructions):
        text_surface = app.font_small.render(line, True, pygame.Color(200, 200, 200))
        surface.blit(text_surface, (16, 76 + idx * 18))

    bar_start_y = 76 + len(instructions) * 18 + 16
    bar_width = 180
    bar_height = 12
    for idx, tank in enumerate(app.logic.tanks):
        label_surface = app.font_small.render(
            f"{tank.name} Superpower", True, pygame.Color(220, 220, 220)
        )
        label_y = bar_start_y + idx * 28
        surface.blit(label_surface, (16, label_y))

        bar_rect = pygame.Rect(16, label_y + 14, bar_width, bar_height)
        pygame.draw.rect(surface, pygame.Color(60, 60, 60), bar_rect, border_radius=6)
        fill_width = int(bar_width * max(0.0, min(1.0, tank.super_power)))
        if fill_width > 0:
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_height)
            color = app.tank_colors[idx % len(app.tank_colors)]
            pygame.draw.rect(surface, color, fill_rect, border_radius=6)
        pygame.draw.rect(surface, pygame.Color(20, 20, 20), bar_rect, width=1, border_radius=6)

        if tank.super_power >= 1.0:
            ready_text = "Ready: B bomber, N squad"
            ready_color = pygame.Color(255, 235, 140) if idx == app.current_player else pygame.Color(210, 210, 210)
            ready_surface = app.font_small.render(ready_text, True, ready_color)
            surface.blit(ready_surface, (bar_rect.right + 16, bar_rect.top - 2))

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
