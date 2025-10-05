import pygame
from typing import Tuple, List, Union

def draw_squad(surface: pygame.Surface,
               center: Tuple[int, int],
               spacing: int = 72,
               scale: float = 1.0,
               mortar_unfolded: Union[bool, Tuple[bool, bool]] = False,
               facing_left: bool = False) -> List[dict]:
    """
    Draw a squad of 6 simple soldiers using primitive shapes.
    Order (left->right): 2x Panzerfaust, 2x Mortar, 2x Assault rifle.
    - surface: pygame surface to draw on
    - center: (x,y) center position of the squad
    - spacing: horizontal spacing between soldiers (base 72px)
    - scale: global scale factor
    - mortar_unfolded: either single bool (applies to both mortars) or tuple(bool,bool)
    - facing_left: if True soldiers face left; otherwise face right
    Returns: list of dicts with info for each soldier: {'role','rect','pos'}.
    """

    # normalize mortar_unfolded
    if isinstance(mortar_unfolded, bool):
        mortar_unfolded = (mortar_unfolded, mortar_unfolded)
    elif isinstance(mortar_unfolded, (list, tuple)) and len(mortar_unfolded) >= 2:
        mortar_unfolded = (bool(mortar_unfolded[0]), bool(mortar_unfolded[1]))
    else:
        mortar_unfolded = (False, False)

    cx, cy = center
    count = 6
    total_width = (count - 1) * spacing * scale
    start_x = cx - total_width / 2

    # Colors (tweak as needed)
    color_body = (60, 110, 80)
    color_helmet = (80, 130, 90)
    color_rifle = (40, 40, 48)
    color_panzerfaust = (30, 30, 32)
    color_mortar = (45, 45, 50)
    color_detail = (200, 200, 200)

    results = []

    def draw_soldier_at(surf, x, y, role: str, mortar_open=False):
        """Draw one stylized soldier centered at (x,y). Returns pygame.Rect bounds."""
        S = scale
        head_r = max(3, int(6 * S))
        body_w = int(14 * S)
        body_h = int(20 * S)
        body_rect = pygame.Rect(0, 0, body_w, body_h)
        body_rect.center = (int(x), int(y + 4 * S))

        # head
        head_pos = (int(x), int(y - int(6 * S)))
        pygame.draw.circle(surf, color_helmet, head_pos, head_r)
        pygame.draw.circle(surf, color_detail, head_pos, max(1, head_r//3))  # visor dot

        # torso
        pygame.draw.rect(surf, color_body, body_rect, border_radius=max(2, int(3*S)))

        # legs (two lines)
        leg_off = int(6 * S)
        pygame.draw.line(surf, color_body, (x - int(3*S), y + int(14*S)), (x - int(3*S), y + int(24*S)), max(1, int(2*S)))
        pygame.draw.line(surf, color_body, (x + int(3*S), y + int(14*S)), (x + int(3*S), y + int(24*S)), max(1, int(2*S)))

        # simple backpack
        pack_rect = pygame.Rect(0,0, int(8*S), int(12*S))
        pack_rect.center = (int(x - 0.6*body_w), int(y + int(3*S)))
        pygame.draw.rect(surf, (50,80,60), pack_rect, border_radius=max(1,int(2*S)))

        # arms and weapon - facing handling
        dir_mul = -1 if facing_left else 1

        shoulder_y = y + int(0*S)
        shoulder_x = x + dir_mul * int(6 * S)

        if role == "panzerfaust":
            # arm holding long tube on shoulder
            # draw supporting arm
            pygame.draw.line(surf, color_body, (x, shoulder_y), (x + dir_mul*int(8*S), shoulder_y), max(1, int(2*S)))
            # panzerfaust tube (cylinder polygon)
            tube_len = int(30 * S)
            tube_w = max(3, int(5 * S))
            tx0 = int(x + dir_mul * (8*S))
            ty0 = shoulder_y - int(3*S)
            tube = [
                (tx0, ty0),
                (tx0 + dir_mul*tube_len, ty0 - tube_w//2),
                (tx0 + dir_mul*tube_len, ty0 + tube_w//2)
            ]
            pygame.draw.polygon(surf, color_panzerfaust, tube)
            # rocket back / sight
            muzzle = (tx0 + dir_mul*(tube_len + int(4*S)), ty0)
            pygame.draw.circle(surf, color_detail, muzzle, max(1, int(2*S)))

        elif role == "mortar":
            # two modes: folded (transport) or unfolded (deployed)
            if mortar_open:
                # draw mortar tube on small tripod in front of soldier
                base_x = int(x + dir_mul * int(18 * S))
                base_y = int(y + int(10 * S))
                # tripod legs
                leg_len = int(12 * S)
                pygame.draw.line(surf, color_mortar, (base_x, base_y), (base_x - dir_mul*leg_len, base_y + int(10*S)), max(1, int(2*S)))
                pygame.draw.line(surf, color_mortar, (base_x, base_y), (base_x + dir_mul*leg_len, base_y + int(10*S)), max(1, int(2*S)))
                # tube angled upward
                tube_len = int(28 * S)
                tube_w = max(3, int(5 * S))
                tube_end = (base_x + dir_mul * int(tube_len*0.8), base_y - int(14 * S))
                pygame.draw.line(surf, color_mortar, (base_x, base_y - int(2*S)), tube_end, tube_w)
                # small sight/rounds box
                pygame.draw.rect(surf, (80,80,85), (base_x - int(4*S), base_y - int(2*S), int(8*S), int(6*S)))
            else:
                # folded: show mortar as a compact box or tube on back/side
                folded_x = int(x - dir_mul * int(10 * S))
                folded_y = int(y + int(0 * S))
                pygame.draw.rect(surf, color_mortar, (folded_x - int(10*S), folded_y - int(4*S), int(20*S), int(6*S)), border_radius=max(1,int(2*S)))
                # straps
                pygame.draw.line(surf, color_detail, (folded_x - int(8*S), folded_y - int(2*S)), (x - int(3*S), folded_y + int(2*S)), max(1,int(1*S)))

        elif role == "rifle":
            # both hands support a rifle
            hand_x = int(x + dir_mul * int(8 * S))
            hand_y = int(y + int(2 * S))
            barrel_len = int(28 * S)
            barrel_w = max(2, int(3 * S))
            # stock
            stock = (x - dir_mul*int(6*S), hand_y + int(2*S))
            pygame.draw.line(surf, color_rifle, stock, (int(hand_x), hand_y), max(1, int(2*S)))
            # barrel
            bx0 = int(hand_x)
            by0 = hand_y - int(1*S)
            bx1 = int(bx0 + dir_mul*barrel_len)
            pygame.draw.line(surf, color_rifle, (bx0, by0), (bx1, by0), barrel_w)
            # sight dot
            pygame.draw.circle(surf, color_detail, (int(bx0 + dir_mul*int(8*S)), by0), max(1,int(1.5*S)))

        # simple shadow under soldier
        shadow_w = int(body_w * 1.2)
        shadow_h = int(6 * S)
        shadow_rect = pygame.Rect(0,0, shadow_w, shadow_h)
        shadow_rect.center = (int(x), int(y + int(26*S)))
        s_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
        pygame.draw.ellipse(s_surf, (10,10,10,100), (0,0,shadow_rect.width, shadow_rect.height))
        surf.blit(s_surf, shadow_rect.topleft)

        # return bounds (approx)
        bounds = pygame.Rect(int(x - body_w), int(y - int(12*S)), int(body_w*2), int(body_h*2 + int(10*S)))
        return bounds

    roles = ["panzerfaust", "panzerfaust", "mortar", "mortar", "rifle", "rifle"]
    mortar_flags = list(mortar_unfolded)  # tuple of two bools
    for i, role in enumerate(roles):
        x = start_x + i * spacing * scale
        y = cy
        m_open = False
        if role == "mortar":
            # map the two mortar soldiers to mortar_flags in order
            # mortar soldiers are at indices 2 and 3 in roles
            m_index = 0 if i == 2 else 1
            m_open = mortar_flags[m_index]
        rect = draw_soldier_at(surface, x, y, role, mortar_open=m_open)
        results.append({"role": role, "rect": rect, "pos": (x,y)})

    return results
