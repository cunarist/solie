from solie import RiskLevel, SolieConfig, bring_to_life

from usage import ExampleStrategy, SilentStrategy

if __name__ == "__main__":
    # Optionally provide configuration.
    config = SolieConfig()

    # Add a strategy.
    strategy = SilentStrategy(
        code_name="SILENT",
        readable_name="Silent Strategy",
        version="1.0",
        description="A silent strategy that does nothing",
        risk_level=RiskLevel.LOW,
    )
    config.add_strategy(strategy)

    # Add a strategy.
    strategy = ExampleStrategy(
        code_name="EXAMPL",
        readable_name="Fixed Strategy",
        version="1.1",
        description="A fixed strategy for demonstration",
        risk_level=RiskLevel.HIGH,
    )
    config.add_strategy(strategy)

    # Run Solie and bring out the window.
    bring_to_life(config)
