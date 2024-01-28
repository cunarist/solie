# Solie

[![PyPI - Python Version](https://img.shields.io/pypi/v/solie)](https://pypi.org/project/solie/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

![Preview](https://github.com/cunarist/solie/assets/66480156/8521df2b-a315-4e00-8963-1db287e0c8ce)

**Solie** is a GUI trading bot designed for targeting the futures markets of Binance.

It enables you to create and customize your own trading strategies, simulating them using real historical data from Binance with the power of Python.

Please note that while this solution provides tools for strategy development, profitability is not guaranteed as success depends on individual decision-making.

Solie connects to Binance, retrieves real-time market and account data, saves it on disk, and presents it as intuitive charts to assist users in strategy development.

## 🛞 How to Run This Thing

Running Solie is very easy.

First, install [Python](https://www.python.org/). Don't forget to add `python` command to PATH during the installation. You can check that Python is ready with the terminal command below.

```bash
python --version
```

Next, install Solie.

```
pip install pipx
python -m pipx ensurepath
pipx install solie
```

Finally, run Solie.

```
solie
```

> We recommend using the official Python installer provided from the website to ensure stability. Also, you might need to replace `python` with `python3`, `pip` with `pip3` on some platforms from the commands above.

## 🖥️ Available Platforms

- ✅ Windows: Working fine
- ✅ Linux: Working fine
- ⏸️ macOS: [Currently unstable](https://github.com/cunarist/solie/issues/87)

## 📖 Documentation

Read the [documentation](https://solie-docs.cunarist.com) to understand how to turn on auto-trading, make your own strategies with the internal API, and get involved in Solie development.

## 🤲 Development Support

If you are benefiting from Solie's features and find it helpful, why not consider supporting the Solie project? Your generous donations contribute to the growth and development of Solie. 😉

If you feel like so, please consider using the BUSD(BSC) wallet address written below.

```
0xF9A7E35254cc8A9A9C811849CAF672F10fAB7366
```
