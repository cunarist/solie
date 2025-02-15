from solie import bring_to_life

from usage import create_solie_config

if __name__ == "__main__":
    # Optionally provide configuration.
    config = create_solie_config()

    # Run Solie and show the window.
    bring_to_life(config)
