# Solie

[![PyPI - Python Version](https://img.shields.io/pypi/v/solie)](https://pypi.org/project/solie/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

![Preview](https://github.com/cunarist/solie/assets/66480156/8521df2b-a315-4e00-8963-1db287e0c8ce)

**Solie** is a GUI trading bot designed for targeting the futures markets of Binance.

It enables you to create and customize your own trading strategies, simulating them using real historical data from Binance with the power of Python.

Please note that while this solution provides tools for strategy development, profitability is not guaranteed as success depends on individual decision-making.

Solie connects to Binance, retrieves real-time market and account data, saves it on disk, and presents it as intuitive charts to assist users in strategy development.

## 🛞 Usage

### Preparation

You can install Solie via `pip`. It is recommended to use [`uv`](https://docs.astral.sh/uv/) for modern Python package management and virtual environments.

```shell
pip install solie
```

### Running With a Script File

Make a Python script file that has the extension `.py`. Just copy and paste the content below in the file. Solie will start working once you execute the Python script file.

```python
import solie

if __name__ == "__main__":
    solie.bring_to_life()
```

For advanced usage, see the `example` folder in the repository.

> Note that on Windows, giving the extension `.pyw` to the file allows you to hide the terminal window and only leave the GUI.

## 🖥️ Available Platforms

- ✅ Windows: Fully supported
- ✅ Linux: Fully supported
- ⏸️ macOS: [Currently unstable](https://github.com/cunarist/solie/issues/87)

## 📖 Documentation

Read the [documentation](https://solie-docs.cunarist.com) to understand how to turn on auto-trading, make your own strategies with the internal API, and get involved in Solie development.
