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

    # ------------------------------------------------------------------
    # Spawning helpers
    def spawn_explosion(self, position: tuple[float, float], scale: float = 1.0) -> None:
        self.explosions.append((position, self.explosion_duration, scale))

    def spawn_trail(self, position: tuple[float, float]) -> None:
        self.trail_particles.append((position, self.trail_duration))

    def spawn_impact_particles(self, result: ShotResult) -> None:
        if result.impact_x is None or result.impact_y is None:
            return
        base_x = result.impact_x
        base_y = result.impact_y

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

    # ------------------------------------------------------------------
    # Update helpers
    def update(self, dt: float, world) -> None:
        self._update_explosions(dt)
        self._update_trails(dt)
        self._update_particles(dt, world)
        self._update_debris(dt, world)

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


__all__ = ["EffectsSystem", "Particle", "Debris"]
