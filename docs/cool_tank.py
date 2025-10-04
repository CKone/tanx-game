# tank_draw.py
import math
import pygame
from dataclasses import dataclass

@dataclass
class TankStyle:
    hull=(60, 110, 80)        # hull color
    hull_shadow=(40, 80, 58)  # lower shadow part of hull
    tracks=(30, 30, 30)       # tracks
    wheels=(70, 70, 70)       # road wheels
    turret=(50, 95, 70)       # turret
    barrel=(25, 25, 25)       # gun barrel
    details=(25, 25, 25)      # bolts, hatches etc.

def _rot(pt, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return (pt[0]*ca - pt[1]*sa, pt[0]*sa + pt[1]*ca)

def _add(a, b): return (a[0]+b[0], a[1]+b[1])

def draw_tank(surface: pygame.Surface,
              position: tuple[int, int],
              hull_angle_deg: float = 0.0,
              turret_angle_deg: float = None,   # None => turret follows hull
              scale: float = 1.0,
              style: TankStyle = TankStyle()) -> dict:
    """
    Draws a 2D tank composed of primitive shapes on 'surface'.
    - position: world position (x, y) of tank center
    - hull_angle_deg: orientation of the hull (0° points to the right)
    - turret_angle_deg: orientation of turret/barrel; None = same as hull
    - scale: size factor (1.0 = base size ~120x70 px)
    - style: color style
    Returns a dict with helpful points (like 'gun_tip').
    """

    if turret_angle_deg is None:
        turret_angle_deg = hull_angle_deg

    # base dimensions in “design units”
    W, H = 120, 70             # overall dimensions including tracks
    HULL_W, HULL_H = 100, 52   # hull dimensions
    TRACK_W = (W - HULL_W) / 2
    BARREL_L, BARREL_W = 70, 10
    TURRET_R = 20
    WHEEL_R = 6
    WHEEL_GAP = 14

    # apply scale
    S  = scale
    W, H = int(W*S), int(H*S)
    HULL_W, HULL_H = int(HULL_W*S), int(HULL_H*S)
    TRACK_W = int(TRACK_W*S)
    BARREL_L, BARREL_W = int(BARREL_L*S), int(BARREL_W*S)
    TURRET_R = int(TURRET_R*S)
    WHEEL_R = max(2, int(WHEEL_R*S))
    WHEEL_GAP = int(WHEEL_GAP*S)

    # draw on a temporary surface and rotate at the end
    temp = pygame.Surface((W, H), pygame.SRCALPHA)
    cx, cy = W//2, H//2  # local center of the temp surface

    # tracks left/right
    left_track_rect  = pygame.Rect(cx - HULL_W//2 - TRACK_W, cy - HULL_H//2, TRACK_W, HULL_H)
    right_track_rect = pygame.Rect(cx + HULL_W//2,          cy - HULL_H//2, TRACK_W, HULL_H)
    pygame.draw.rect(temp, style.tracks, left_track_rect, border_radius=int(6*S))
    pygame.draw.rect(temp, style.tracks, right_track_rect, border_radius=int(6*S))

    # road wheels (just decorative)
    wheel_span = HULL_W
    wheels_per_side = max(3, (wheel_span // WHEEL_GAP))
    start_x = cx - HULL_W//2 + int(WHEEL_GAP*0.75)
    y_top  = cy - HULL_H//2 + int(0.8*WHEEL_R)
    y_bot  = cy + HULL_H//2 - int(0.8*WHEEL_R)
    for i in range(int(wheels_per_side)):
        x = start_x + i*WHEEL_GAP
        if x > cx + HULL_W//2 - int(WHEEL_GAP*0.75):
            break
        pygame.draw.circle(temp, style.wheels, (x, y_top), WHEEL_R)
        pygame.draw.circle(temp, style.wheels, (x, y_bot), WHEEL_R)

    # hull (rounded rectangle)
    hull_rect = pygame.Rect(cx - HULL_W//2, cy - HULL_H//2, HULL_W, HULL_H)
    pygame.draw.rect(temp, style.hull, hull_rect, border_radius=int(14*S))
    # lower shadow part
    hull_shadow = hull_rect.copy()
    hull_shadow.height = int(HULL_H*0.45)
    hull_shadow.top = cy
    pygame.draw.rect(temp, style.hull_shadow, hull_shadow, border_radius=int(10*S))

    # top plate (detail rectangle)
    top_plate = pygame.Rect(0, 0, int(HULL_W*0.65), int(HULL_H*0.25))
    top_plate.center = (cx, cy - int(HULL_H*0.22))
    pygame.draw.rect(temp, style.details, top_plate, width=1, border_radius=int(8*S))

    # turret (circle)
    turret_center = (cx, cy - int(HULL_H*0.05))
    pygame.draw.circle(temp, style.turret, turret_center, TURRET_R)
    pygame.draw.circle(temp, style.details, turret_center, TURRET_R, width=1)

    # barrel (rectangle, separately rotated around turret center)
    barrel_len_inner = BARREL_L - TURRET_R  # out of turret
    barrel_surf = pygame.Surface((barrel_len_inner, BARREL_W), pygame.SRCALPHA)
    pygame.draw.rect(barrel_surf, style.barrel, pygame.Rect(0, 0, barrel_len_inner, BARREL_W), border_radius=int(BARREL_W*0.35))
    # muzzle brake (small block)
    muzzle_w = int(BARREL_W*1.2)
    muzzle_h = BARREL_W
    muzzle = pygame.Surface((muzzle_w, muzzle_h), pygame.SRCALPHA)
    pygame.draw.rect(muzzle, style.barrel, pygame.Rect(0, 0, muzzle_w, muzzle_h), border_radius=int(muzzle_h*0.25))

    # position the barrel with rotation
    ta = math.radians(turret_angle_deg)
    # offset at turret edge
    start_offset = (TURRET_R*math.cos(ta), TURRET_R*math.sin(ta))
    barrel_pos = (
        turret_center[0] + start_offset[0],
        turret_center[1] + start_offset[1]
    )
    # rotate barrel surface
    barrel_rot = pygame.transform.rotate(barrel_surf, -turret_angle_deg)
    barrel_rect = barrel_rot.get_rect()
    barrel_rect.center = (barrel_pos[0] + math.cos(ta)*barrel_len_inner/2,
                          barrel_pos[1] + math.sin(ta)*barrel_len_inner/2)
    temp.blit(barrel_rot, barrel_rect)

    # muzzle at barrel tip
    muzzle_rot = pygame.transform.rotate(muzzle, -turret_angle_deg)
    muzzle_rect = muzzle_rot.get_rect()
    muzzle_rect.center = (barrel_pos[0] + math.cos(ta)*barrel_len_inner + muzzle_w*0.5*math.cos(ta),
                          barrel_pos[1] + math.sin(ta)*barrel_len_inner + muzzle_w*0.5*math.sin(ta))
    temp.blit(muzzle_rot, muzzle_rect)

    # small bolts (optional)
    for dx in (-int(HULL_W*0.28), 0, int(HULL_W*0.28)):
        pygame.draw.circle(temp, style.details, (cx+dx, cy - int(HULL_H*0.02)), max(1, int(2*S)))

    # rotate the entire tank hull and blit on the world surface
    rot = pygame.transform.rotate(temp, -hull_angle_deg)
    rrect = rot.get_rect(center=position)
    surface.blit(rot, rrect)

    gun_tip = (muzzle_rect.centerx - rrect.left, muzzle_rect.centery - rrect.top)  # local in rot surface
    gun_tip_world = (rrect.left + gun_tip[0], rrect.top + gun_tip[1])

    return {
        "bounds": rrect,            # pygame.Rect in world coordinates
        "center": position,
        "gun_tip": gun_tip_world    # world coordinate of barrel tip
    }

# --- Mini demo ---
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((900, 600))
    clock = pygame.time.Clock()
    angle = 0
    turret = 0

    style = TankStyle(
        hull=(72, 132, 94),
        hull_shadow=(50, 96, 70),
        tracks=(25, 25, 28),
        wheels=(85, 85, 90),
        turret=(64, 118, 88),
        barrel=(22, 22, 22),
        details=(28, 28, 28)
    )

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

        # Controls: Left/Right = rotate hull, A/D = rotate turret
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]: angle += 2
        if keys[pygame.K_RIGHT]: angle -= 2
        if keys[pygame.K_a]: turret += 3
        if keys[pygame.K_d]: turret -= 3

        screen.fill((235, 235, 240))
        info = draw_tank(screen, (450, 300), hull_angle_deg=angle, turret_angle_deg=turret, scale=1.15, style=style)

        # visualize barrel tip
        pygame.draw.circle(screen, (200, 60, 60), info["gun_tip"], 3)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
