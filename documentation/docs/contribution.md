# Contribution Guide

Guides below will help you dive into the Solie codebase.

When using terminal commands from the following sections, always make sure that your current working directory is the root folder of the cloned repository.

## 🧮 Preparing the Repository

You need to install some components on your system first.

First, install [Python](https://www.python.org/). We recommend using the official Python installer provided from the website to ensure stability. Don't forget to add `python` command to PATH during the installation.

Then, make sure [Poetry](https://python-poetry.org/) is installed on your system.

```bash
pip install pipx
python -m pipx ensurepath
pipx install poetry
```

Install the dependencies. You only have to do this once.

```bash
poetry install
```

Activate the Poetry shell and run the code.

```bash
poetry shell
python -m solie
```

## 🧰 Debugging

If there is Python code that you want to run, you can run it in the `Logs` of the `Manage` tab. After writing the code in the `Python script` input field, you can press `Run script` button to get the result. The `print` function won't help you because it prints to the terminal rather than the log list.

Note that what you're running here is a real Python code. Therefore, you can import various modules including `solie` from the script.

![](assets/example_005.png)

To output something as a log, you can use the default `logger`. When you run this code, you will see a new record being added to the log list in the `debugger`. `logger` can show anything of any type.

```python
logger.debug("Something you want to know about")
```

You can also choose the importance of the log. There are 5 log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. Our `logger` provided here will output all the levels.

```python
my_dictionary = {"a": "yahoo", "b": "hi"}
logger.info(my_dictionary)
```

![](assets/example_032.png)

You can also access workers. Direct modification of internal data is possible.

```python
from solie.worker import team

logger.debug(team.transactor.account_state)
```

If the type of the variable you want to output is `list` or `dict`, you can log it with better readability using the `json` standard library.

```python
import json

log_data = json.dumps(
    team.transactor.account_state,
    indent=2,
    default=str
)
logger.debug(log_data)
```

![](assets/example_034.png)

In the `Log output`, all logs that occur during execution are stacked. If an error occurs, it is also logged. If you're writing a strategy script and something doesn't work, visit here to figure out the cause.

## 🕹️ User Interface

The user interface can be modified by editing the `./craft/window.ui` file with `Qt Designer`. Run the designer app with the terminal command below.

```bash
poetry shell
pyside6-designer
```

After editing the UI file, you should compile it into a Python module.

```bash
pyside6-uic craft/window.ui -o package/solie/window/compiled.py
```

## 🚦 Rules

- Solie is made purely in Python and uses Poetry as the default package management tool.
- Use Ruff formatter for formatting and linting.
- Use Pyright's basic type checking. If you're using Visual Studio Code, Pylance will provide a superset of Pyright’s functionality.
- It should be easy for general users to use with just a few clicks.
- It should be developed with the goal of working on both `Windows`, `Linux`, and `macOS`. Do not use platform-dependent packages such as `win32api`.
- The `print` command is only for development purposes only and should not be included in the final code. If there is information to be shown, it must be displayed in the user interface.
- When a value is added to data that has a table form, it should be occupied by `datalocks` and then written at once so that one row can always be assumed to be completely intact. Be careful that there is no instantaneous blank space after a new row is added.
- Time zone information must be included in UTC in `datetime.datetime` object. In addition to this, please include UTC time zone information wherever possible, such as `pandas.DatetimeIndex`.
