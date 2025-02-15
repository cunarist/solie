from solie import SolieConfig, bring_to_life

from usage import create_solie_config

# Remember to guard the entry point for proper multiprocessing.
if __name__ == "__main__":
    # Optionally provide configuration.
    config: SolieConfig = create_solie_config()

    # Run Solie and show the window.
    bring_to_life(config)
