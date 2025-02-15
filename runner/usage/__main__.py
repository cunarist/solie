from solie import SolieConfig, bring_to_life

from . import MyStrategy

if __name__ == "__main__":
    config = SolieConfig()
    config.add_strategy(MyStrategy(code_name="AABBCC"))
    bring_to_life(config)
