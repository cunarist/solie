# Introduction

[![PyPI - Python Version](https://img.shields.io/pypi/v/solie)](https://pypi.org/project/solie/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

![Preview](https://github.com/cunarist/solie/assets/66480156/8521df2b-a315-4e00-8963-1db287e0c8ce)

**Solie** is a trading bot designed for targeting the futures markets of Binance.

It enables you to create and customize your own trading strategies, simulating them using real historical data from Binance with the power of Python.

Please note that while this solution provides tools for strategy development, profitability is not guaranteed as success depends on individual decision-making.

Solie connects to Binance, retrieves real-time market and account data, saves it on disk, and presents it as intuitive charts to assist users in strategy development.

## 🛞 How to Run This Thing

Running Solie is very easy.

First, install [Python](https://www.python.org/). Don't forget to add `python` command to PATH during the installation. You can check that Python is ready with the command below.

```bash
python --version
```

Next, open a terminal window and install Solie.

```
pip install solie
```

Finally, run Solie.

```
python -m solie
```

> We recommend using the official Python installer provided from the website to ensure stability. Also, you might need to replace `python` with `python3`, `pip` with `pip3` on some platforms from the commands above.

## 🖥️ Available Platforms

- ✅ Windows: Working fine
- ✅ Linux: Working fine
- ⏸️ macOS: [Partially working](https://github.com/cunarist/solie/issues/87)
