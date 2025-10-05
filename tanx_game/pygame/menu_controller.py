"""Menu state management for the pygame client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class MenuOption:
    """Entry rendered in a menu overlay."""

    label: str
    action: Callable[[], None]


MessageProvider = Callable[[], Optional[str]]
OptionBuilder = Callable[[], List[MenuOption]]


@dataclass
class MenuDefinition:
    """Declarative description of a menu screen."""

    title: str
    build_options: OptionBuilder
    default_message: Optional[MessageProvider] = None


@dataclass
class MenuController:
    """Track active menu, selection, and status messaging."""

    definitions: Dict[str, MenuDefinition] = field(default_factory=dict)
    state: Optional[str] = None
    title: str = "Tanx"
    message: Optional[str] = None
    selection: int = 0
    options: List[MenuOption] = field(default_factory=list)

    def register(self, name: str, definition: MenuDefinition) -> None:
        self.definitions[name] = definition

    def activate(self, name: str, *, message: Optional[str] = None) -> None:
        if name not in self.definitions:
            raise KeyError(f"Unknown menu '{name}'")
        self.state = name
        definition = self.definitions[name]
        self.title = definition.title
        self.options = definition.build_options()
        self.selection = 0 if self.options else 0
        if message is not None:
            self.message = message
        else:
            self.message = definition.default_message() if definition.default_message else None

    def update_options(self) -> None:
        if self.state is None:
            return
        definition = self.definitions[self.state]
        current_selection = min(self.selection, max(len(self.options) - 1, 0))
        self.options = definition.build_options()
        self.selection = min(current_selection, len(self.options) - 1)
        # Preserve the current informational message whenever possible.

    def set_message(self, text: Optional[str]) -> None:
        self.message = text

    def change_selection(self, delta: int) -> None:
        if not self.options:
            return
        self.selection = (self.selection + delta) % len(self.options)

    def execute_current(self) -> None:
        if not self.options:
            return
        self.current_option.action()

    @property
    def current_option(self) -> MenuOption:
        return self.options[self.selection]


__all__ = ["MenuController", "MenuDefinition", "MenuOption"]
