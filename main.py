"""Entry point for playing the Tanx artillery game."""

import argparse

from tanx_game import run_pygame


def main() -> None:
    parser = argparse.ArgumentParser(description="Tanx arcade duel")
    parser.add_argument("--cheat", action="store_true", help="enable cheat console")
    args = parser.parse_args()
    run_pygame(cheat_enabled=args.cheat)


if __name__ == "__main__":
    main()
