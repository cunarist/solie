from solie import SolieConfig, bring_to_life

from usage import ExampleStrategy, SilentStrategy

if __name__ == "__main__":
    config = SolieConfig()  # Optional

    strategy = SilentStrategy(
        code_name="SILENT",
        readable_name="A silent strategy that does nothing",
    )
    config.add_strategy(strategy)
    strategy = ExampleStrategy(
        code_name="EXAMPL",
        readable_name="A fixed strategy for demonstration",
    )
    config.add_strategy(strategy)

    bring_to_life(config)
