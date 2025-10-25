"""Keybinding management for the Tanx pygame client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import pygame


@dataclass
class KeyBindings:
    move_left: int
    move_right: int
    turret_up: int
    turret_down: int
    fire: int
    power_decrease: int
    power_increase: int


class KeybindingManager:
    """Track and manipulate per-player key bindings."""

    def __init__(self) -> None:
        self.binding_fields: List[tuple[str, str]] = [
            ("Move Left", "move_left"),
            ("Move Right", "move_right"),
            ("Turret Up", "turret_up"),
            ("Turret Down", "turret_down"),
            ("Fire", "fire"),
            ("Power -", "power_decrease"),
            ("Power +", "power_increase"),
        ]
        self.default_bindings: List[KeyBindings] = [
            KeyBindings(
                move_left=pygame.K_a,
                move_right=pygame.K_d,
                turret_up=pygame.K_w,
                turret_down=pygame.K_s,
                fire=pygame.K_SPACE,
                power_decrease=pygame.K_q,
                power_increase=pygame.K_e,
            ),
            KeyBindings(
                move_left=pygame.K_LEFT,
                move_right=pygame.K_RIGHT,
                turret_up=pygame.K_UP,
                turret_down=pygame.K_DOWN,
                fire=pygame.K_RETURN,
                power_decrease=pygame.K_COMMA,
                power_increase=pygame.K_PERIOD,
            ),
        ]
        self.player_bindings: List[KeyBindings] = [
            KeyBindings(**vars(binding)) for binding in self.default_bindings
        ]
        self.rebinding_target: Optional[tuple[int, str]] = None

    # ------------------------------------------------------------------
    def to_config(self) -> List[dict[str, int]]:
        """Return a serialisable snapshot of the current bindings."""
        result: List[dict[str, int]] = []
        for binding in self.player_bindings:
            entry = {field: int(getattr(binding, field)) for _, field in self.binding_fields}
            result.append(entry)
        return result

    def load_from_config(self, data: List[dict]) -> None:
        """Restore bindings from a persisted configuration."""
        if not isinstance(data, list):
            return
        restored: List[KeyBindings] = []
        for idx, entry in enumerate(data):
            if not isinstance(entry, dict):
                continue
            template = self.default_bindings[idx % len(self.default_bindings)]
            values = {}
            for _, field in self.binding_fields:
                raw = entry.get(field, getattr(template, field))
                try:
                    values[field] = int(raw)
                except (TypeError, ValueError):
                    values[field] = getattr(template, field)
            restored.append(KeyBindings(**values))
        if restored:
            # Ensure we maintain exactly two players worth of bindings.
            while len(restored) < len(self.default_bindings):
                restored.append(KeyBindings(**vars(self.default_bindings[len(restored)])))
            self.player_bindings = restored[: len(self.default_bindings)]

    # ------------------------------------------------------------------
    def format_key(self, key: int) -> str:
        name = pygame.key.name(key)
        return name.upper()

    def start_rebinding(self, player_idx: int, field: str) -> str:
        self.rebinding_target = (player_idx, field)
        label = self._field_label(field)
        return f"Press a key for Player {player_idx + 1} {label} (Esc to cancel)"

    def finish_rebinding(self, key: int) -> str:
        if self.rebinding_target is None:
            return "Select an action to rebind."
        player_idx, field = self.rebinding_target
        current_value = getattr(self.player_bindings[player_idx], field)
        if key == current_value:
            self.rebinding_target = None
            label = self._field_label(field)
            return (
                f"Player {player_idx + 1} {label} remains bound to {self.format_key(key)}"
            )
        for bind_idx, bindings in enumerate(self.player_bindings):
            for _, other_field in self.binding_fields:
                if bind_idx == player_idx and other_field == field:
                    continue
                if getattr(bindings, other_field) == key:
                    other_label = self._field_label(other_field)
                    return (
                        f"{self.format_key(key)} already bound to "
                        f"Player {bind_idx + 1} {other_label}. "
                        "Choose another key or press Esc to cancel."
                    )
        setattr(self.player_bindings[player_idx], field, key)
        self.rebinding_target = None
        label = self._field_label(field)
        return (
            f"Player {player_idx + 1} {label} bound to {self.format_key(key)}"
        )

    def cancel_rebinding(self) -> str:
        self.rebinding_target = None
        return "Rebinding cancelled."

    def reset_to_defaults(self) -> str:
        self.player_bindings = [
            KeyBindings(**vars(binding)) for binding in self.default_bindings
        ]
        self.rebinding_target = None
        return "Key bindings reset to defaults."

    def build_menu_options(
        self,
        select_field: Callable[[int, str], None],
        reset_callback: Callable[[], None],
        back_callback: Callable[[], None],
    ) -> List[tuple[str, Callable[[], None]]]:
        options: List[tuple[str, Callable[[], None]]] = []
        for player_idx, prefix in enumerate(["Player 1", "Player 2"]):
            bindings = self.player_bindings[player_idx]
            for label, field in self.binding_fields:
                key_code = getattr(bindings, field)
                options.append(
                    (
                        f"{prefix} {label}: {self.format_key(key_code)}",
                        lambda pi=player_idx, f=field: select_field(pi, f),
                    )
                )
        options.append(("Reset to Defaults", reset_callback))
        options.append(("Back to Settings", back_callback))
        return options

    def menu_message(self) -> str:
        if self.rebinding_target is None:
            return "Select an action to rebind."
        player_idx, field = self.rebinding_target
        label = self._field_label(field)
        return f"Press a key for Player {player_idx + 1} {label} (Esc to cancel)"

    # ------------------------------------------------------------------
    def _field_label(self, field: str) -> str:
        for label, attr in self.binding_fields:
            if attr == field:
                return label
        return field


__all__ = ["KeyBindings", "KeybindingManager"]
