"""Entry point for playing the Tanx artillery game."""

from tanx_game.game import Game


def main() -> None:
    game = Game()
    game.play()


if __name__ == "__main__":
    main()
