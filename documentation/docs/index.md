# Introduction

[![PyPI - Python Version](https://img.shields.io/pypi/v/solie)](https://pypi.org/project/solie/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

![Preview](https://github.com/cunarist/solie/assets/66480156/8521df2b-a315-4e00-8963-1db287e0c8ce)

**Solie** is a solution for automatically trading cryptocurrency contracts in the futures markets of Binance. It allows you to create and customize your own trading strategies and simulate them using historical data with the power of Python.

Please note that this solution does not guarantee profitability, as the success of your strategies depends on your decision-making. Solie connects to Binance, retrieves real-time market and account data, saves it on disk, and presents it as an intuitive chart to assist you in developing your strategies.

## 🛞 How to Run This Thing

Running Solie is very easy.

First, install [Python](https://www.python.org/). We recommend using the official installer provided from the website to ensure stability. Don't forget to add `python` command to PATH during the installation. You can check that Python is ready with the command below.

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

> You might need to replace `python` with `python3`, `pip` with `pip3` on some platforms from the commands above.

## 🖥️ Available Platforms

- ✅ Windows: Working fine
- ✅ Linux: Working fine
- ⏸️ macOS: [Partially working](https://github.com/cunarist/solie/issues/87)
