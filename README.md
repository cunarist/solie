# Solie

[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v1.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

![Preview](https://github.com/cunarist/solie/assets/66480156/8521df2b-a315-4e00-8963-1db287e0c8ce)

**Solie** is a solution for automatically trading cryptocurrency contracts in the futures markets of Binance. It allows you to create and customize your own trading strategies and simulate them using historical data with the power of Python.

Please note that this solution does not guarantee profitability, as the success of your strategies depends on your decision-making. Solie connects to Binance, retrieves real-time market and account data, saves it on disk, and presents it as an intuitive chart to assist you in developing your strategies.

## 📖 Documentation

Read the [documentation](https://solie-docs.cunarist.com) to understand how to turn on auto-trading, make your own strategies with the interal API, and get involved in Solie development.

## 🛞 How to Use This Thing

> When using terminal commands from the following steps, always make sure that your current working directory is the folder of this project. Also, you might need to replace `python` with `python3`, `pip` with `pip3` on some platforms from the commands below.

Running Solie is easy, but you need to install some components on your system first. It won't be as hard as you think if you adhere to the following instructions.

First, install [Python](https://www.python.org/). We recommend using the official installer provided from the website to ensure stability. Don't forget to add `python` command to PATH during the installation. You can check that Python is ready with the command below.

```bash
python --version
```

Also, make sure [Poetry](https://python-poetry.org/) is installed on your system.

```bash
pip install pipx
python -m pipx ensurepath
# You might need to restart the terminal here
pipx install poetry
```

Install the dependencies. You only have to do this once.

```bash
poetry install
```

Activate the Poetry shell and run the code.

```bash
poetry shell
# Once you've activated the shell, you don't need to do it again
python solie
```

## 📖 Available Platforms

- ✅ Windows: Working fine
- ✅ Linux: Working fine
- ⏸️ macOS: [Partially working](https://github.com/cunarist/solie/issues/87)

## 🚪 Development Support

If you are benefiting from Solie's features and find it helpful, why not consider supporting the Solie project? Your generous donations contribute to the growth and development of Solie. 😉

If you feel like so, please consider using the BUSD(BSC) wallet address written below.

```
0xF9A7E35254cc8A9A9C811849CAF672F10fAB7366
```
