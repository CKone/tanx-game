"""Display and resolution management for the pygame client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

from tanx_game.core.world import TerrainSettings


@dataclass(frozen=True)
class ResolutionPreset:
    """Single resolution entry rendered in the settings menu."""

    cell_size: int
    label: str
    size: Tuple[int, int]


class DisplayManager:
    """Encapsulate pygame display surfaces and resolution handling."""

    def __init__(self, *, cell_size: int, ui_height: int, caption: str) -> None:
        self.caption = caption
        self.cell_size = cell_size
        self.ui_height = ui_height

        self.world_width = 0
        self.world_height = 0

        self._supported_cell_sizes: List[int] = [20, 24, 28, 32, 36]
        if cell_size not in self._supported_cell_sizes:
            self._supported_cell_sizes.append(cell_size)
            self._supported_cell_sizes.sort()

        self.windowed_fullscreen = False
        self.windowed_fullscreen_size: Optional[Tuple[int, int]] = None

        info = pygame.display.Info()
        initial_size = (
            info.current_w or 640,
            info.current_h or 480,
        )
        self._display_flags = pygame.FULLSCREEN
        self.display_surface = pygame.display.set_mode(initial_size, self._display_flags)
        self.fullscreen_size = self.display_surface.get_size()
        pygame.display.set_caption(self.caption)

        self.render_surface: Optional[pygame.Surface] = None
        self._screen: pygame.Surface = self.display_surface
        self.playfield_offset_x = 0

        self.resolution_presets: List[ResolutionPreset] = []
        self.resolution_index = 0

    # ------------------------------------------------------------------
    @property
    def screen(self) -> pygame.Surface:
        return self._screen

    def configure_world(self, world_width: int, world_height: int) -> None:
        self.world_width = world_width
        self.world_height = world_height
        width = self.world_width * self.cell_size
        height = self.world_height * self.cell_size + self.ui_height
        if self.windowed_fullscreen and self.windowed_fullscreen_size:
            self._set_display_mode(self.windowed_fullscreen_size, pygame.NOFRAME)
        elif self._display_flags & pygame.FULLSCREEN:
            self.fullscreen_size = self.display_surface.get_size()
            self._set_display_mode(self.fullscreen_size, pygame.FULLSCREEN)
        else:
            self._set_display_mode((width, height))
        self._update_render_target()
        self._sync_resolution_presets()

    def _set_display_mode(self, size: Tuple[int, int], flags: int = 0) -> None:
        if self._display_flags != flags or self.display_surface.get_size() != size:
            self.display_surface = pygame.display.set_mode(size, flags)
            self._display_flags = flags
            pygame.display.set_caption(self.caption)

    def _update_render_target(self) -> None:
        if self.windowed_fullscreen:
            width = self.world_width * self.cell_size
            height = self.world_height * self.cell_size + self.ui_height
            desired = (width, height)
            if self.render_surface is None or self.render_surface.get_size() != desired:
                surface = pygame.Surface(desired).convert_alpha()
                surface.fill((0, 0, 0))
                self.render_surface = surface
            self._screen = self.render_surface
        elif self._display_flags & pygame.FULLSCREEN:
            width = self.world_width * self.cell_size
            height = self.world_height * self.cell_size + self.ui_height
            desired = (width, height)
            if self.render_surface is None or self.render_surface.get_size() != desired:
                surface = pygame.Surface(desired).convert_alpha()
                surface.fill((0, 0, 0))
                self.render_surface = surface
            self._screen = self.render_surface
        else:
            self.render_surface = None
            self._screen = self.display_surface
        self._update_playfield_offset()

    def _update_playfield_offset(self) -> None:
        if self.world_width <= 0 or self.cell_size <= 0:
            self.playfield_offset_x = 0
            return
        playfield_width = self.world_width * self.cell_size
        screen_width = self._screen.get_width()
        self.playfield_offset_x = max(0, (screen_width - playfield_width) // 2)

    def _sync_resolution_presets(self) -> None:
        if self.world_width <= 0 or self.world_height <= 0:
            return
        unique_sizes = sorted(set(self._supported_cell_sizes + [self.cell_size]))
        presets: List[ResolutionPreset] = []
        for size in unique_sizes:
            width = self.world_width * size
            height = self.world_height * size + self.ui_height
            presets.append(
                ResolutionPreset(
                    cell_size=size,
                    label=f"{width}×{height}",
                    size=(width, height),
                )
            )
        self.resolution_presets = presets
        self.resolution_index = 0
        for idx, preset in enumerate(presets):
            if preset.cell_size == self.cell_size:
                self.resolution_index = idx
                break

    # ------------------------------------------------------------------
    def resolution_option_label(self) -> str:
        if not self.resolution_presets:
            self._sync_resolution_presets()
        if not self.resolution_presets:
            return "Resolution: unavailable"
        preset = self.resolution_presets[self.resolution_index]
        return f"Resolution: {preset.label}"

    def windowed_fullscreen_label(self) -> str:
        label = "Windowed Fullscreen"
        if self.windowed_fullscreen_size:
            width, height = self.windowed_fullscreen_size
            label = f"{label} ({width}×{height})"
        return label

    def enter_windowed_fullscreen(
        self, base_settings: TerrainSettings
    ) -> tuple[Optional[TerrainSettings], Optional[str]]:
        try:
            desktops = pygame.display.get_desktop_sizes()
        except AttributeError:
            desktops = []
        if not desktops:
            info = pygame.display.Info()
            desktops = (
                [(info.current_w, info.current_h)]
                if info.current_w and info.current_h
                else []
            )
        if not desktops:
            return None, "Desktop size unavailable"

        width, height = desktops[0]
        if width <= 0 or height <= 0:
            return None, "Desktop size unavailable"

        available_height = max(1, height - self.ui_height)
        height_cells = max(1, base_settings.height)
        cell_from_height = max(4, available_height // height_cells)
        cell_size = min(max(self._supported_cell_sizes), cell_from_height)
        if cell_size not in self._supported_cell_sizes:
            self._supported_cell_sizes.append(cell_size)
            self._supported_cell_sizes.sort()

        width_cells = max(base_settings.width, max(1, width // max(1, cell_size)))
        new_settings = TerrainSettings(**vars(base_settings))
        new_settings.width = width_cells

        self.windowed_fullscreen = True
        self.windowed_fullscreen_size = (width, height)
        self.cell_size = cell_size
        return new_settings, f"Windowed fullscreen {width}×{height}"

    def apply_resolution(self, cell_size: int) -> bool:
        updated = cell_size != self.cell_size or self.windowed_fullscreen
        self.windowed_fullscreen = False
        self.windowed_fullscreen_size = None
        if updated:
            self.cell_size = cell_size
        return updated

    def change_resolution(self, direction: int) -> Optional[ResolutionPreset]:
        if not self.resolution_presets:
            self._sync_resolution_presets()
        if not self.resolution_presets:
            return None
        self.resolution_index = (self.resolution_index + direction) % len(self.resolution_presets)
        return self.resolution_presets[self.resolution_index]


__all__ = ["DisplayManager", "ResolutionPreset"]
