# bomber_demo.py
import pygame
import math
import random
from dataclasses import dataclass

pygame.init()

# --- Config ---
SCREEN_W, SCREEN_H = 1000, 600
GRAVITY = 0.45   # gravity applied to bombs (px/frame^2)
BOMB_RADIUS = 4
EXPLOSION_RADIUS = 24
BOMB_COLOR = (40, 40, 45)
EXPLOSION_COLOR = (255, 160, 40)

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
clock = pygame.time.Clock()

# --- Helper dataclasses ---
@dataclass
class Bomb:
    x: float
    y: float
    vx: float
    vy: float
    radius: int = BOMB_RADIUS
    alive: bool = True

@dataclass
class Explosion:
    x: float
    y: float
    radius: float = 0.0
    max_radius: float = EXPLOSION_RADIUS
    life: int = 18  # frames

# --- Bomber class ---
class Bomber:
    """
    Simple bomber that flies horizontally and drops multiple bombs over a target x-position.
    - It will move from left to right or right to left depending on start/end.
    - drop_bomb_run(target_x, count, spread_px) will schedule `count` bombs to be released
      such that they fall approximately over the target +/- spread_px.
    """
    def __init__(self, start_pos, end_pos, speed=2.0, y_offset=80, color=(160, 40, 40)):
        self.start_x, self.start_y = start_pos
        self.end_x, self.end_y = end_pos
        self.x = float(self.start_x)
        self.y = float(self.start_y + y_offset)
        self.speed = float(speed)
        self.color = color
        # direction normalized toward end_x
        self.dir = 1.0 if self.end_x >= self.start_x else -1.0
        self.finished = False
        # scheduling bombs: list of (release_x, release_count, spread_px)
        self.drop_schedule = []

        # visual sizes
        self.w, self.h = 64, 22

    def update(self, dt=1.0):
        """
        Move bomber. dt is time-step multiplier (frames).
        Returns list of bombs to spawn this frame (usually 0 or >0).
        """
        if self.finished:
            return []

        move = self.speed * dt * self.dir
        self.x += move

        # check schedule for any release points near current x
        bombs_to_release = []
        remaining = []
        for release_x, count, spread in self.drop_schedule:
            # if we've passed the release_x (depending on direction) -> release
            if (self.dir > 0 and self.x >= release_x) or (self.dir < 0 and self.x <= release_x):
                # compute individual initial vx so bombs have slight horizontal velocity
                for i in range(count):
                    # add slight random horizontal velocity based on bomber direction
                    vx = 0.15 * self.dir * random.uniform(0.7, 1.3)
                    # vertical velocity initial (small downward push)
                    vy = 0.6 * random.uniform(0.0, 0.6)
                    # drop position jitter so bombs aren't all at exact same x
                    jx = self.x + random.uniform(-6, 6)
                    bombs_to_release.append(Bomb(jx, self.y + self.h//2 + 2, vx, vy))
            else:
                remaining.append((release_x, count, spread))
        self.drop_schedule = remaining

        # check finished (passed end_x)
        if (self.dir > 0 and self.x > self.end_x + 50) or (self.dir < 0 and self.x < self.end_x - 50):
            self.finished = True

        return bombs_to_release

    def schedule_bomb_run(self, target_x, count=5, spread_px=40):
        """
        Schedule multiple releases so bombs approximate falling over target_x.
        Strategy:
        - Estimate time-to-fall from bomber altitude to ground using s = 0.5 * g * t^2
        - Given bomber horizontal speed, compute where bomber will be when the bomb hits ground.
        - Release bombs earlier/later distributed around that release point so final impacts spread over `spread_px`.
        """
        # approximate fall time from current altitude to ground:
        height = SCREEN_H - (self.y + self.h//2)  # px
        if height <= 0:
            # already at ground-level, just drop now
            release_x = self.x
            self.drop_schedule.append((release_x, count, spread_px))
            return

        # t = sqrt(2*h/g)
        t_fall = math.sqrt(2.0 * height / GRAVITY)
        # horizontal distance bomber travels in that time:
        dist = abs(self.speed * t_fall)
        # expected impact x if dropped right now:
        expected_impact_if_now = self.x + self.dir * dist

        # we want bombs to land around target_x, so compute where bomber should be when dropping
        # solve for drop_x so: drop_x + dir * dist_at_drop = target_x
        # dist_at_drop depends on t_fall which is roughly same if altitude not changing, but bomber y is constant here
        # We'll approximate dist_at_drop ~ dist (since bomber altitude constant), so drop_x ~ target_x - dir*dist
        drop_x_center = target_x - self.dir * dist

        # distribute several release points around drop_x_center to achieve spread on impact
        # spread at impact roughly maps to similar spread at release (since horizontal velocity small), so we spread release points
        for i in range(count):
            frac = i / max(1, count - 1)  # 0..1
            # cover spread_px in release coordinates
            rel = (frac - 0.5) * (spread_px)
            # convert to release point (a small correction)
            rel_release_x = drop_x_center + rel
            # append schedule tuple
            self.drop_schedule.append((rel_release_x, 1, spread_px / count))

    def draw(self, surf):
        # simple bomber silhouette using primitives
        x = int(self.x)
        y = int(self.y)
        body = pygame.Rect(x - self.w//2, y - self.h//2, self.w, self.h)
        # body
        pygame.draw.ellipse(surf, self.color, body)
        # cockpit
        cockpit = pygame.Rect(x - 6, y - self.h//2 + 2, 26, 10)
        pygame.draw.ellipse(surf, (220, 220, 230), cockpit)
        # tail
        tail = [(x - self.w//2 + 6, y), (x - self.w//2 - 8, y - 8), (x - self.w//2 - 8, y + 8)]
        pygame.draw.polygon(surf, self.color, tail)

# --- Bomb / physics update function ---
def update_bombs(bombs, explosions, dt=1.0, target_rects=None, on_hit=None):
    """
    Update bombs with gravity and simple collisions.
    - bombs: list of Bomb
    - explosions: list of Explosion
    - target_rects: list of pygame.Rect (if any) to test collisions against
    - on_hit: optional callback (bomb, hit_rect) -> None
    """
    if target_rects is None:
        target_rects = []

    for b in bombs:
        if not b.alive:
            continue
        # integrate physics
        b.vy += GRAVITY * dt
        b.x += b.vx * dt * 60  # scale horizontal speed to px/frame (visually tuned)
        b.y += b.vy * dt * 60

        # out of bounds check
        if b.y > SCREEN_H + 100 or b.x < -200 or b.x > SCREEN_W + 200:
            b.alive = False
            continue

        # check collision with any target rect
        for tr in target_rects:
            if tr.collidepoint(int(b.x), int(b.y)):
                b.alive = False
                # create explosion at impact
                explosions.append(Explosion(b.x, b.y))
                if on_hit:
                    on_hit(b, tr)
                break

        # hit ground
        if b.y >= SCREEN_H - 8:
            b.alive = False
            explosions.append(Explosion(b.x, SCREEN_H - 8))

    # update explosions
    to_remove = []
    for ex in explosions:
        ex.life -= 1
        ex.radius = ex.max_radius * (1 - ex.life / 18)  # simple grow effect
        if ex.life <= 0:
            to_remove.append(ex)
    for ex in to_remove:
        explosions.remove(ex)

    # remove dead bombs
    bombs[:] = [b for b in bombs if b.alive]

# --- Rendering helpers ---
def draw_bombs(surf, bombs):
    for b in bombs:
        pygame.draw.circle(surf, BOMB_COLOR, (int(b.x), int(b.y)), b.radius)

def draw_explosions(surf, explosions):
    for ex in explosions:
        alpha = max(40, int(220 * (ex.life / 18)))
        surf_ex = pygame.Surface((int(ex.max_radius*2), int(ex.max_radius*2)), pygame.SRCALPHA)
        pygame.draw.circle(surf_ex, (*EXPLOSION_COLOR, alpha), (int(ex.max_radius), int(ex.max_radius)), int(ex.radius))
        surf.blit(surf_ex, (int(ex.x - ex.max_radius), int(ex.y - ex.max_radius)))

# --- Demo main loop ---
def main():
    bomber = Bomber(start_pos=( -100, 0 ), end_pos=( SCREEN_W + 100, 0 ), speed=2.6, y_offset=120, color=(100, 130, 180))
    # example target rect (you can replace this with the tank's bounds from draw_tank)
    target = pygame.Rect(540, SCREEN_H - 70, 80, 70)

    bombs = []
    explosions = []

    # schedule bomber to drop bombs over target after a short delay
    # We'll call schedule_bomb_run once bomber is near left side so release points make sense
    scheduled = False

    running = True
    while running:
        dt = clock.tick(60) / 60.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

        # update bomber and maybe spawn bombs
        new_bombs = bomber.update(dt)
        if new_bombs:
            bombs.extend(new_bombs)

        # schedule one run when bomber crosses some x (so calculation of drop positions works)
        if not scheduled and ((bomber.dir > 0 and bomber.x > 50) or (bomber.dir < 0 and bomber.x < SCREEN_W - 50)):
            bomber.schedule_bomb_run(target_x=target.centerx, count=8, spread_px=120)
            scheduled = True

        # keep bombs updated
        update_bombs(bombs, explosions, dt, target_rects=[target], on_hit=lambda b, tr: print(f"Bomb hit target at {b.x:.1f},{b.y:.1f}"))

        # draw
        screen.fill((230, 240, 245))
        # ground
        pygame.draw.rect(screen, (80, 200, 100), (0, SCREEN_H - 8, SCREEN_W, 8))

        # target (draw before explosions so explosions overlay)
        pygame.draw.rect(screen, (80, 80, 180), target)

        # bomber and bomblets
        bomber.draw(screen)
        draw_bombs(screen, bombs)
        draw_explosions(screen, explosions)

        # HUD text
        font = pygame.font.get_default_font()
        f = pygame.font.Font(font, 16)
        screen.blit(f.render("Bomber demo - press ESC to quit", True, (20, 20, 20)), (10, 8))

        pygame.display.flip()

        # simple input
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

    pygame.quit()

if __name__ == "__main__":
    main()
