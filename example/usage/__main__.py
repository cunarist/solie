from solie import SolieConfig, bring_to_life

from usage import ExampleStrategy, SilentStrategy

if __name__ == "__main__":
    # Optionally provide configuration.
    config = SolieConfig()

    # Add a strategy.
    strategy = SilentStrategy(
        code_name="SILENT",
        readable_name="A Silent Strategy that Does Nothing",
    )
    config.add_strategy(strategy)

    # Add a strategy.
    strategy = ExampleStrategy(
        code_name="EXAMPL",
        readable_name="A Fixed Strategy for Demonstration",
    )
    config.add_strategy(strategy)

    # Run Solie and bring out the window.
    bring_to_life(config)
