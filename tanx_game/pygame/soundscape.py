"""Soundscape helpers wrapping pygame.mixer with category-aware playback."""

from __future__ import annotations

import math
import os
from array import array
from pathlib import Path
from typing import Dict, Optional

import pygame


class Soundscape:
    """High-level mixer facade that groups sounds by category."""

    def __init__(
        self,
        base_path: Path,
        *,
        enabled: bool = True,
        frequency: int = 44_100,
        size: int = -16,
        channels: int = 2,
        buffer: int = 512,
    ) -> None:
        self.base_path = Path(base_path)
        self.enabled = enabled
        self._mixer_ready = False
        self._registry: Dict[str, pygame.mixer.Sound] = {}
        self._categories: Dict[str, str] = {}
        self._volumes: Dict[str, float] = {
            "master": 1.0,
            "effects": 1.0,
            "ambient": 0.8,
            "ui": 0.8,
        }
        self._missing_assets_reported: set[str] = set()
        self._ambient_channel: Optional[pygame.mixer.Channel] = None
        self._ensure_base_path()

        if not enabled:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(
                    frequency=frequency, size=size, channels=channels, buffer=buffer
                )
            self._mixer_ready = True
            self._ambient_channel = pygame.mixer.Channel(7)
        except pygame.error:
            # Mixer failed (e.g., no audio device). Run silently.
            self.enabled = False
            self._mixer_ready = False

    # ------------------------------------------------------------------
    # Loading & playback
    def load(self, key: str, filename: str, *, category: str = "effects") -> None:
        if not self._mixer_ready:
            return
        path = self.base_path / filename
        sound: Optional[pygame.mixer.Sound]
        try:
            if path.is_file():
                sound = pygame.mixer.Sound(path.as_posix())
            else:
                sound = None
        except pygame.error:
            sound = None

        if sound is None:
            sound = self._create_placeholder_sound(key, category)
            if sound is None:
                return
            self._report_missing_asset(filename)

        self._registry[key] = sound
        self._categories[key] = category

    def play(self, key: str, *, loops: int = 0, volume: Optional[float] = None) -> None:
        if not self._mixer_ready:
            return
        sound = self._registry.get(key)
        if sound is None:
            return
        category = self._categories.get(key, "effects")
        vol = self._volumes.get("master", 1.0) * self._volumes.get(category, 1.0)
        if volume is not None:
            vol *= volume
        sound.set_volume(max(0.0, min(1.0, vol)))
        sound.play(loops=loops)

    def play_loop(self, key: str) -> None:
        if not self._mixer_ready:
            return
        sound = self._registry.get(key)
        if sound is None:
            return
        channel = self._ambient_channel
        if channel is None:
            channel = pygame.mixer.find_channel()
            if channel is None:
                return
            self._ambient_channel = channel
        category = self._categories.get(key, "ambient")
        vol = self._volumes.get("master", 1.0) * self._volumes.get(category, 1.0)
        clamped = max(0.0, min(1.0, vol))
        sound.set_volume(clamped)
        channel.set_volume(clamped)
        channel.play(sound, loops=-1)

    def stop_loop(self) -> None:
        if self._ambient_channel is not None:
            self._ambient_channel.stop()

    # ------------------------------------------------------------------
    # Volume management
    def set_volume(self, category: str, value: float) -> None:
        self._volumes[category] = max(0.0, min(1.0, value))
        if (
            category in {"master", "ambient"}
            and self._ambient_channel
            and self._ambient_channel.get_sound()
        ):
            key = self._current_ambient_key()
            if key:
                category_key = self._categories.get(key, "ambient")
                vol = self._volumes.get("master", 1.0) * self._volumes.get(
                    category_key, 1.0
                )
                clamped = max(0.0, min(1.0, vol))
                self._ambient_channel.set_volume(clamped)
                sound = self._registry.get(key)
                if sound is not None:
                    sound.set_volume(clamped)

    def get_volume(self, category: str) -> float:
        return self._volumes.get(category, 1.0)

    # ------------------------------------------------------------------
    def _ensure_base_path(self) -> None:
        if not self.base_path.exists():
            try:
                os.makedirs(self.base_path, exist_ok=True)
            except OSError:
                pass

    def _current_ambient_key(self) -> Optional[str]:
        if not self._ambient_channel:
            return None
        current = self._ambient_channel.get_sound()
        if current is None:
            return None
        for key, sound in self._registry.items():
            if sound == current:
                return key
        return None

    def _report_missing_asset(self, filename: str) -> None:
        if filename in self._missing_assets_reported:
            return
        self._missing_assets_reported.add(filename)
        print(f"[Soundscape] Missing audio asset '{filename}', using placeholder tone.")

    def _create_placeholder_sound(
        self, key: str, category: str
    ) -> Optional[pygame.mixer.Sound]:
        init = pygame.mixer.get_init()
        if not init:
            return None
        sample_rate, size, channels = init
        width = abs(size)
        if width != 16:
            return None

        duration = self._placeholder_duration(category)
        base_freq = self._placeholder_frequency(key, category)
        harmonics = self._placeholder_harmonics(category)
        amplitude = self._placeholder_amplitude(category)

        total_samples = max(1, int(sample_rate * duration))
        attack = max(1, int(total_samples * 0.03))
        release = max(1, int(total_samples * 0.08))
        scale = int(32767 * amplitude)

        wave = array("h")
        for index in range(total_samples):
            t = index / sample_rate
            envelope = 1.0
            if index < attack:
                envelope = index / attack
            elif index > total_samples - release:
                envelope = max(0.0, (total_samples - index) / release)

            sample_value = 0.0
            for harmonic, weight in harmonics:
                sample_value += weight * math.sin(2.0 * math.pi * base_freq * harmonic * t)
            sample_value = max(-1.0, min(1.0, sample_value)) * envelope
            wave.append(int(scale * sample_value))

        if channels == 2:
            stereo = array("h")
            for sample in wave:
                stereo.extend([sample, sample])
            data = stereo.tobytes()
        else:
            data = wave.tobytes()

        try:
            return pygame.mixer.Sound(buffer=data)
        except pygame.error:
            return None

    def _placeholder_frequency(self, key: str, category: str) -> float:
        key = key.lower()
        if "ambient" in key or category == "ambient":
            return 170.0
        if "menu" in key or category == "ui":
            return 660.0 if "select" in key else 520.0
        if "collapse" in key:
            return 240.0
        if "hit_tank" in key:
            return 380.0
        if "impact" in key:
            return 320.0
        if "explosion_large" in key:
            return 180.0
        if "explosion" in key:
            return 220.0
        return 440.0

    def _placeholder_duration(self, category: str) -> float:
        if category == "ambient":
            return 1.8
        if category == "ui":
            return 0.15
        return 0.35

    def _placeholder_amplitude(self, category: str) -> float:
        if category == "ambient":
            return 0.25
        if category == "ui":
            return 0.3
        return 0.6

    def _placeholder_harmonics(self, category: str) -> list[tuple[float, float]]:
        if category == "ambient":
            return [(1.0, 0.7), (0.5, 0.3)]
        if category == "ui":
            return [(1.0, 1.0)]
        return [(1.0, 0.8), (1.5, 0.2)]


__all__ = ["Soundscape"]
