"""Procedural texture helpers for the Tanx pygame client."""

from __future__ import annotations

import random
from typing import Tuple

import pygame


def generate_noise_texture(
    size: int,
    *,
    alpha: int = 28,
    seed: int = 0,
    brightness: Tuple[int, int] = (215, 255),
) -> pygame.Surface:
    """Create a tileable grayscale noise texture."""

    rng = random.Random(seed)
    small_size = max(8, size // 4)
    small = pygame.Surface((small_size, small_size), pygame.SRCALPHA)
    min_b, max_b = brightness
    for y in range(small_size):
        for x in range(small_size):
            tone = rng.randint(min_b, max_b)
            small.set_at((x, y), (tone, tone, tone, alpha))

    surface = pygame.transform.smoothscale(small, (size, size))
    overlay = pygame.transform.smoothscale(small, (size, size))
    surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surface.convert_alpha()


def generate_cloud_layer(
    width: int,
    height: int,
    *,
    blobs: int = 10,
    seed: int = 0,
    base_alpha: int = 180,
) -> pygame.Surface:
    """Generate a soft cloud layer surface."""

    rng = random.Random(seed)
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    colors = [
        pygame.Color(255, 255, 255, int(base_alpha * 0.9)),
        pygame.Color(238, 244, 255, int(base_alpha * 0.75)),
        pygame.Color(220, 224, 240, int(base_alpha * 0.6)),
    ]

    for _ in range(blobs):
        blob_w = rng.randint(width // 4, width // 2)
        blob_h = rng.randint(height // 3, height // 2)
        x = rng.randint(-blob_w // 3, width)
        y = rng.randint(-blob_h // 2, height // 2)
        color = random.choice(colors)
        ellipse_rect = pygame.Rect(x, y, blob_w, blob_h)
        pygame.draw.ellipse(surface, color, ellipse_rect)

    # Feather the edges very slightly
    feather = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(feather, (255, 255, 255, 40), feather.get_rect(), border_radius=width // 3)
    surface.blit(feather, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surface.convert_alpha()


__all__ = ["generate_noise_texture", "generate_cloud_layer"]
