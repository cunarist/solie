"""Example usage entry point."""

from solie import SolieConfig, bring_to_life

from usage import ExampleStrategy, SilentStrategy


def main() -> None:
    """Run Solie with example strategies."""
    # Optionally provide configuration.
    config = SolieConfig()
    config.add_strategy(SilentStrategy())
    config.add_strategy(ExampleStrategy())
    # Run Solie and show the window.
    bring_to_life(config)


# Remember to guard the entry point for proper multiprocessing.
if __name__ == "__main__":
    main()
