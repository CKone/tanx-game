"""Effects system for particles, debris, and explosions."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

from tanx_game.core.game import ShotResult
from tanx_game.core.tank import Tank


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    radius: float
    color: Tuple[int, int, int]
    kind: str = "generic"


@dataclass
class Debris:
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    angular_velocity: float
    life: float
    max_life: float
    width: float
    height: float
    color: Tuple[int, int, int]


@dataclass
class WeatherDrop:
    x: float
    y: float
    vx: float
    vy: float
    length: float
    life: float
    max_life: float


class EffectsSystem:
    """Encapsulates simulation state for particles, debris, and explosions."""

    def __init__(
        self,
        cell_size: int,
        ui_height: int,
        particle_gravity: float = 18.0,
        explosion_duration: float = 0.45,
        trail_duration: float = 0.25,
    ) -> None:
        self.cell_size = cell_size
        self.ui_height = ui_height
        self.particle_gravity = particle_gravity
        self.explosion_duration = explosion_duration
        self.trail_duration = trail_duration
        self.reset()

    def reset(self) -> None:
        self.explosions: List[Tuple[tuple[float, float], float, float]] = []
        self.trail_particles: List[Tuple[tuple[float, float], float]] = []
        self.particles: List[Particle] = []
        self.debris: List[Debris] = []
        self.smoke: List[Particle] = []
        self.embers: List[Particle] = []
        self.weather_drops: List[WeatherDrop] = []
        self.weather_type: str = "clear"
        self.wind: float = 0.0

    # ------------------------------------------------------------------
    # Spawning helpers
    def spawn_explosion(self, position: tuple[float, float], scale: float = 1.0) -> None:
        self.explosions.append((position, self.explosion_duration, scale))
        self.spawn_smoke_plume(position, intensity=scale)
        self.spawn_embers(position, intensity=scale)

    def spawn_trail(self, position: tuple[float, float]) -> None:
        self.trail_particles.append((position, self.trail_duration))

    def spawn_dust_column(self, position: tuple[float, float], scale: float = 1.0) -> None:
        base_x, base_y = position
        particle_count = max(12, int(36 * max(0.5, scale)))
        max_radius = max(2.5, 4.5 * max(0.5, scale))
        for _ in range(particle_count):
            angle = random.uniform(-math.pi * 0.55, -math.pi * 0.1)
            speed = random.uniform(0.6, 1.8) * max(0.6, scale)
            vx = math.cos(angle) * speed * random.uniform(0.4, 1.0)
            vy = math.sin(angle) * speed
            life = random.uniform(0.8, 1.6) * max(0.7, scale)
            radius = random.uniform(1.2, max_radius)
            color = (
                random.randint(120, 150),
                random.randint(110, 135),
                random.randint(96, 115),
            )
            self.particles.append(
                Particle(
                    x=base_x + random.uniform(-0.6, 0.6),
                    y=base_y + random.uniform(-0.1, 0.2),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=color,
                )
            )
        if len(self.particles) > 260:
            self.particles = self.particles[-260:]

    def spawn_impact_particles(self, result: ShotResult) -> None:
        if result.impact_x is None or result.impact_y is None:
            return
        base_x = result.impact_x
        base_y = result.impact_y
        self.spawn_smoke_plume((base_x, base_y), intensity=0.6)

        fatal = result.fatal_hit
        if result.hit_tank:
            dirt_particles = 32
            spark_particles = 18
        else:
            dirt_particles = 24
            spark_particles = 8

        if fatal:
            dirt_particles = int(dirt_particles * 1.6)
            spark_particles = int(spark_particles * 1.5) + 6

        for _ in range(dirt_particles):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            speed = random.uniform(1.2, 3.2)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.5, 1.0)
            radius = random.uniform(2.0, 4.5)
            self.particles.append(
                Particle(
                    x=base_x + random.uniform(-0.2, 0.2),
                    y=base_y + random.uniform(-0.1, 0.1),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(138, 96, 60),
                )
            )

        for _ in range(spark_particles):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(2.5, 5.5)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.35, 0.65)
            radius = random.uniform(1.0, 2.4)
            self.particles.append(
                Particle(
                    x=base_x,
                    y=base_y,
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(255, 214, 120),
                    kind="spark",
                )
            )

        if fatal:
            for _ in range(6):
                angle = random.uniform(-math.pi * 0.8, -math.pi * 0.2)
                speed = random.uniform(1.0, 2.2)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                life = random.uniform(1.0, 1.6)
                radius = random.uniform(3.5, 6.0)
                self.particles.append(
                    Particle(
                        x=base_x + random.uniform(-0.3, 0.3),
                        y=base_y,
                        vx=vx,
                        vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(80, 78, 74),
                    kind="smoke_seed",
                )
            )

        if len(self.particles) > 240:
            self.particles = self.particles[-240:]

    def spawn_fatal_debris(
        self,
        result: ShotResult,
        tanks: List[Tank],
        tank_colors: List[pygame.Color],
    ) -> None:
        if result.fatal_tank is None:
            return
        base_x = result.impact_x if result.impact_x is not None else result.fatal_tank.x
        base_y = result.impact_y if result.impact_y is not None else result.fatal_tank.y
        tank_color = tank_colors[0]
        for idx, tank in enumerate(tanks):
            if tank is result.fatal_tank:
                tank_color = tank_colors[idx % len(tank_colors)]
                break

        for _ in range(8):
            angle = random.uniform(-math.pi * 0.9, -math.pi * 0.1)
            speed = random.uniform(1.0, 3.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(1.4, 2.2)
            width = int(random.uniform(8, 18))
            height = int(random.uniform(4, 12))
            width = max(6, width)
            height = max(3, height)
            self.debris.append(
                Debris(
                    x=base_x + random.uniform(-0.3, 0.3),
                    y=base_y + random.uniform(-0.2, 0.2),
                    vx=vx,
                    vy=vy,
                    angle=random.uniform(0, math.tau),
                    angular_velocity=random.uniform(-4.0, 4.0),
                    life=life,
                    max_life=life,
                    width=width,
                    height=height,
                    color=(
                        max(0, tank_color.r - 40),
                        max(0, tank_color.g - 40),
                        max(0, tank_color.b - 40),
                    ),
                )
            )

        turret_speed = random.uniform(2.5, 3.6)
        turret_angle = random.uniform(-math.pi * 0.8, -math.pi * 0.2)
        self.debris.append(
            Debris(
                x=base_x,
                y=base_y,
                vx=math.cos(turret_angle) * turret_speed,
                vy=math.sin(turret_angle) * turret_speed,
                angle=random.uniform(0, math.tau),
                angular_velocity=random.uniform(-2.5, 2.5),
                life=2.8,
                max_life=2.8,
                width=int(max(12, self.cell_size * 1.1)),
                height=int(max(6, self.cell_size * 0.5)),
                color=(tank_color.r, tank_color.g, tank_color.b),
            )
        )

        if len(self.debris) > 48:
            self.debris = self.debris[-48:]

    def spawn_smoke_plume(self, position: tuple[float, float], intensity: float = 1.0) -> None:
        base_x, base_y = position
        count = max(8, int(24 * intensity))
        for _ in range(count):
            vx = random.uniform(-0.25, 0.25)
            vy = -random.uniform(0.4, 1.4) * max(0.6, intensity)
            life = random.uniform(1.5, 3.4) * max(0.6, intensity)
            radius = random.uniform(0.4, 1.2) * max(0.8, intensity)
            gray = random.randint(120, 180)
            self.smoke.append(
                Particle(
                    x=base_x + random.uniform(-0.35, 0.35),
                    y=base_y + random.uniform(-0.2, 0.15),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(gray, gray, gray),
                    kind="smoke",
                )
            )
        if len(self.smoke) > 320:
            self.smoke = self.smoke[-320:]

    def spawn_embers(self, position: tuple[float, float], intensity: float = 1.0) -> None:
        base_x, base_y = position
        count = max(6, int(18 * intensity))
        for _ in range(count):
            angle = random.uniform(-math.pi * 0.8, -math.pi * 0.2)
            speed = random.uniform(0.6, 1.6) * max(0.6, intensity)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.8, 1.6)
            radius = random.uniform(0.12, 0.35) * max(1.0, intensity)
            self.embers.append(
                Particle(
                    x=base_x,
                    y=base_y,
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=life,
                    radius=radius,
                    color=(255, random.randint(120, 180), 40),
                    kind="ember",
                )
            )
        if len(self.embers) > 120:
            self.embers = self.embers[-120:]

    def spawn_rubble_chunks(self, position: tuple[float, float], width: float, *, color: Tuple[int, int, int] | None = None) -> None:
        base_x, base_y = position
        chunk_count = max(12, int(width * 4))
        base_color = color or (140, 108, 88)
        for _ in range(chunk_count):
            angle = random.uniform(-math.pi * 0.5, math.pi * 0.2)
            speed = random.uniform(0.8, 2.6)
            vx = math.cos(angle) * speed + self.wind * 0.4
            vy = math.sin(angle) * speed - random.uniform(0.6, 1.2)
            life = random.uniform(1.4, 2.6)
            width_px = random.uniform(6.0, 14.0)
            height_px = random.uniform(4.0, 10.0)
            tinted = (
                max(30, min(200, int(base_color[0] + random.randint(-10, 8)))),
                max(30, min(200, int(base_color[1] + random.randint(-12, 12)))),
                max(30, min(200, int(base_color[2] + random.randint(-18, 6)))),
            )
            self.debris.append(
                Debris(
                    x=base_x + random.uniform(-width * 0.35, width * 0.35),
                    y=base_y - random.uniform(0.1, 0.4),
                    vx=vx,
                    vy=vy,
                    angle=random.uniform(0, math.tau),
                    angular_velocity=random.uniform(-5.0, 5.0),
                    life=life,
                    max_life=life,
                    width=int(width_px),
                    height=int(height_px),
                    color=tinted,
                )
            )
        if len(self.debris) > 96:
            self.debris = self.debris[-96:]

    # ------------------------------------------------------------------
    # Update helpers
    def update(self, dt: float, world) -> None:
        self._update_explosions(dt)
        self._update_trails(dt)
        self._update_particles(dt, world)
        self._update_debris(dt, world)
        self._update_smoke(dt, world)
        self._update_embers(dt, world)

    def _update_explosions(self, dt: float) -> None:
        if not self.explosions:
            return
        updated: List[Tuple[tuple[float, float], float, float]] = []
        for pos, timer, scale in self.explosions:
            timer -= dt
            if timer > 0:
                updated.append((pos, timer, scale))
        self.explosions = updated

    def _update_trails(self, dt: float) -> None:
        if not self.trail_particles:
            return
        updated: List[Tuple[tuple[float, float], float]] = []
        for pos, timer in self.trail_particles:
            timer -= dt
            if timer > 0:
                updated.append((pos, timer))
        self.trail_particles = updated

    def _update_particles(self, dt: float, world) -> None:
        if not self.particles:
            return
        alive: List[Particle] = []
        for particle in self.particles:
            particle.life -= dt
            if particle.life <= 0:
                continue
            particle.vy += self.particle_gravity * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            if -2 <= particle.x <= world.width + 2:
                surface = world.ground_height(particle.x)
                if surface is not None and particle.y >= surface - 0.05:
                    gradient = 0.0
                    left = world.ground_height(particle.x - 0.25)
                    right = world.ground_height(particle.x + 0.25)
                    if left is not None and right is not None:
                        gradient = (right - left) * 0.3
                    particle.y = surface - 0.05
                    if particle.vy > 0:
                        particle.vy = -particle.vy * 0.25
                    particle.vx = (particle.vx + gradient) * 0.65
                    if abs(particle.vx) < 0.04:
                        particle.vx = 0.0
                    if abs(particle.vy) < 0.04:
                        particle.vy = 0.0
            alive.append(particle)
        self.particles = alive

    def _update_debris(self, dt: float, world) -> None:
        if not self.debris:
            return
        alive: List[Debris] = []
        for chunk in self.debris:
            chunk.life -= dt
            if chunk.life <= 0:
                continue
            chunk.vy += (self.particle_gravity * 0.6) * dt
            chunk.x += chunk.vx * dt
            chunk.y += chunk.vy * dt
            chunk.angle += chunk.angular_velocity * dt
            if -4 <= chunk.x <= world.width + 4:
                surface = world.ground_height(chunk.x)
                if surface is not None and chunk.y >= surface - 0.1:
                    gradient = 0.0
                    left = world.ground_height(chunk.x - 0.4)
                    right = world.ground_height(chunk.x + 0.4)
                    if left is not None and right is not None:
                        gradient = (right - left) * 0.4
                    chunk.y = surface - 0.1
                    if chunk.vy > 0:
                        chunk.vy = -chunk.vy * 0.35
                    chunk.vx = (chunk.vx + gradient) * 0.8
                    if abs(chunk.vx) < 0.05:
                        chunk.vx = 0.0
                    if abs(chunk.vy) < 0.05:
                        chunk.vy = 0.0
            alive.append(chunk)
        self.debris = alive

    def _update_smoke(self, dt: float, world) -> None:
        if not self.smoke:
            return
        alive: List[Particle] = []
        for particle in self.smoke:
            particle.life -= dt
            if particle.life <= 0:
                continue
            particle.vx += self.wind * 0.25 * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.radius = min(particle.radius * 1.02, particle.radius + 0.02)
            alive.append(particle)
        self.smoke = alive

    def _update_embers(self, dt: float, world) -> None:
        if not self.embers:
            return
        alive: List[Particle] = []
        for ember in self.embers:
            ember.life -= dt
            if ember.life <= 0:
                continue
            ember.vy += self.particle_gravity * 0.15 * dt
            ember.x += ember.vx * dt
            ember.y += ember.vy * dt
            alive.append(ember)
        self.embers = alive

    # ------------------------------------------------------------------
    # Weather helpers
    def set_weather(self, weather: str) -> None:
        if weather != self.weather_type:
            self.weather_type = weather
            self.weather_drops.clear()

    def update_weather(self, dt: float, width: float, height: float) -> None:
        if self.weather_type == "clear":
            self.weather_drops.clear()
            return
        drops = self.weather_drops
        target_count = 160 if self.weather_type == "rain" else 220
        spawn_batch = max(4, target_count // 12)
        if len(drops) < target_count:
            for _ in range(spawn_batch):
                if self.weather_type == "rain":
                    vx = self.wind * 0.8 + random.uniform(-0.6, 0.6)
                    vy = random.uniform(10.0, 14.0)
                    length = random.uniform(0.35, 0.55)
                else:  # snow
                    vx = self.wind * 0.4 + random.uniform(-0.4, 0.4)
                    vy = random.uniform(1.6, 2.8)
                    length = random.uniform(0.28, 0.42)
                drops.append(
                    WeatherDrop(
                        x=random.uniform(-1.0, width + 1.0),
                        y=random.uniform(-1.0, 0.0),
                        vx=vx,
                        vy=vy,
                        length=length,
                        life=0.0,
                        max_life=height / max(vy, 0.1),
                    )
                )

        alive: List[WeatherDrop] = []
        for drop in drops:
            drop.life += dt
            drop.x += drop.vx * dt
            drop.y += drop.vy * dt
            if drop.y > height + 1.0 or drop.x < -1.5 or drop.x > width + 1.5:
                continue
            alive.append(drop)
        self.weather_drops = alive

    def set_wind(self, wind: float) -> None:
        self.wind = wind


__all__ = ["EffectsSystem", "Particle", "Debris", "WeatherDrop"]
