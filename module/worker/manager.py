import asyncio
import json
import logging
import os
import platform
import statistics
import subprocess
import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone

import aiofiles
import timesetter

from module import core, introduction
from module.instrument.api_requester import ApiRequester
from module.recipe import (
    check_internet,
    datalocks,
    find_updates,
    remember_task_durations,
    simply_format,
    user_settings,
    value_to,
)
from module.worker import collector

WINDOW_LOCK_OPTIONS = (
    "NEVER",
    "10_SECOND",
    "1_MINUTE",
    "10_MINUTE",
    "1_HOUR",
)


class Manager:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/manager"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.executed_time = datetime.now(timezone.utc).replace(microsecond=0)

        self.online_status = {
            "ping": 0,
            "server_time_differences": deque(maxlen=120),
        }
        self.binance_limits = {}

        self.settings = {
            "match_system_time": True,
            "disable_system_update": False,
            "lock_window": "NEVER",
        }

        # ■■■■■ repetitive schedules ■■■■■

        core.window.scheduler.add_job(
            self.lock_board,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.check_online_status,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.display_system_status,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.display_internal_status,
            trigger="cron",
            second="*",
        )
        core.window.scheduler.add_job(
            self.disable_system_auto_update,
            trigger="cron",
            minute="*",
        )
        core.window.scheduler.add_job(
            self.match_system_time,
            trigger="cron",
            minute="*/10",
        )
        core.window.scheduler.add_job(
            self.check_for_update,
            trigger="cron",
            minute="*/10",
        )
        core.window.scheduler.add_job(
            self.check_binance_limits,
            trigger="cron",
            hour="*",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    async def load(self, *args, **kwargs):
        # settings
        filepath = self.workerpath + "/settings.json"
        if os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                self.settings = json.loads(content)
        core.window.checkBox_12.setChecked(self.settings["match_system_time"])
        core.window.checkBox_13.setChecked(self.settings["disable_system_update"])
        core.window.comboBox_3.setCurrentIndex(
            value_to.indexes(WINDOW_LOCK_OPTIONS, self.settings["lock_window"])[0]
        )

        # python script
        filepath = self.workerpath + "/python_script.txt"
        if os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()
        else:
            script = ""
        core.window.plainTextEdit.setPlainText(script)

    async def change_settings(self, *args, **kwargs):
        is_checked = core.window.checkBox_12.isChecked()
        self.settings["match_system_time"] = True if is_checked else False

        is_checked = core.window.checkBox_13.isChecked()
        self.settings["disable_system_update"] = True if is_checked else False

        current_index = core.window.comboBox_3.currentIndex()
        self.settings["lock_window"] = WINDOW_LOCK_OPTIONS[current_index]

        filepath = self.workerpath + "/settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(self.settings, indent=4)
            await file.write(content)

    async def open_datapath(self, *args, **kwargs):
        os.startfile(user_settings.get_app_settings()["datapath"])

    async def deselect_log_output(self, *args, **kwargs):
        core.window.listWidget.clearSelection()

    async def add_log_output(self, *args, **kwargs):
        # get the data
        summarization = args[0]
        log_content = args[1]

        # add to log list
        core.window.listWidget.addItem(summarization, log_content)

        # save to file
        task_start_time = datetime.now(timezone.utc)
        filepath = str(self.executed_time)
        filepath = filepath.replace(":", "_")
        filepath = filepath.replace(" ", "_")
        filepath = filepath.replace("-", "_")
        filepath = filepath.replace("+", "_")
        filepath = self.workerpath + "/log_outputs_" + filepath + ".txt"
        async with aiofiles.open(filepath, "a", encoding="utf8") as file:
            await file.write(f"{summarization}\n")
            await file.write(f"{log_content}\n\n")
        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
        remember_task_durations.add("write_log", duration)

    async def display_internal_status(self, *args, **kwargs):
        def job():
            texts = []
            texts.append("Limits")
            for limit_type, limit_value in self.binance_limits.items():
                text = f"{limit_type}: {limit_value}"
                texts.append(text)

            used_rates = self.api_requester.used_rates
            if len(used_rates) > 0:
                texts.append("")
                texts.append("Usage")
                for used_type, used_tuple in used_rates.items():
                    time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                    text = f"{used_type}: {used_tuple[0]}({time_string})"
                    texts.append(text)

            text = "\n".join(texts)
            core.window.label_35.setText(text)

            texts = []

            task_durations = remember_task_durations.get()
            for data_name, deque_data in task_durations.items():
                if len(deque_data) > 0:
                    text = data_name
                    text += "\n"
                    data_value = sum(deque_data) / len(deque_data)
                    text += f"Average {simply_format.fixed_float(data_value,6)}s "
                    data_value = statistics.median(deque_data)
                    text += f"Middle {simply_format.fixed_float(data_value,6)}s "
                    text += "\n"
                    data_value = min(deque_data)
                    text += f"Minimum {simply_format.fixed_float(data_value,6)}s "
                    data_value = max(deque_data)
                    text += f"Maximum {simply_format.fixed_float(data_value,6)}s "
                    texts.append(text)

            text = "\n\n".join(texts)
            core.window.label_33.setText(text)

            block_sizes = collector.me.aggtrade_candle_sizes
            lines = (f"{symbol} {count}" for (symbol, count) in block_sizes.items())
            text = "\n".join(lines)
            core.window.label_36.setText(text)

            texts = []
            for key, lock in datalocks.object_locks.items():
                is_locked = lock.locked()
                locked_text = "Locked" if is_locked else "Unlocked"
                texts.append(f"{key}: {locked_text}")
            text = "\n".join(texts)
            core.window.label_34.setText(text)

        for _ in range(10):
            job()
            await asyncio.sleep(0.1)

    async def run_script(self, *args, **kwargs):
        script_text = core.window.plainTextEdit.toPlainText()
        filepath = self.workerpath + "/python_script.txt"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(script_text)
        namespace = {"window": core.window, "logger": logging.getLogger("solie")}
        exec(script_text, namespace)

    async def check_online_status(self, *args, **kwargs):
        if not check_internet.connected():
            return

        request_time = datetime.now(timezone.utc)
        payload = {}
        response = await self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/time",
            payload=payload,
        )
        response_time = datetime.now(timezone.utc)
        ping = (response_time - request_time).total_seconds()
        self.online_status["ping"] = ping

        server_timestamp = response["serverTime"] / 1000
        server_time = datetime.fromtimestamp(server_timestamp, tz=timezone.utc)
        local_time = datetime.now(timezone.utc)
        time_difference = (local_time - server_time).total_seconds() - ping / 2
        self.online_status["server_time_differences"].append(time_difference)

    async def display_system_status(self, *args, **kwargs):
        time = datetime.now(timezone.utc)
        time_text = time.strftime("%Y-%m-%d %H:%M:%S")
        internet_connected = check_internet.connected()
        ping = self.online_status["ping"]
        board_enabled = core.window.board.isEnabled()

        deque_data = self.online_status["server_time_differences"]
        if len(deque_data) > 0:
            mean_difference = sum(deque_data) / len(deque_data)
        else:
            mean_difference = 0

        text = ""
        text += f"Current time UTC {time_text}"
        text += "  ⦁  "
        if internet_connected:
            text += "Connected to the internet"
        else:
            text += "Not connected to the internet"
        text += "  ⦁  "
        text += f"Ping {ping:.3f}s"
        text += "  ⦁  "
        text += f"Time difference with server {mean_difference:+.3f}s"
        text += "  ⦁  "
        text += f"Board {('unlocked' if board_enabled else 'locked')}"
        core.window.gauge.setText(text)

    async def match_system_time(self, *args, **kwargs):
        if not self.settings["match_system_time"]:
            return

        server_time_differences = self.online_status["server_time_differences"]
        if len(server_time_differences) < 60:
            return
        mean_difference = sum(server_time_differences) / len(server_time_differences)
        new_time = datetime.now(timezone.utc) - timedelta(seconds=mean_difference)
        timesetter.set(new_time)
        server_time_differences.clear()
        server_time_differences.append(0)

    async def check_binance_limits(self, *args, **kwargs):
        if not check_internet.connected():
            return

        payload = {}
        response = await self.api_requester.binance(
            http_method="GET",
            path="/fapi/v1/exchangeInfo",
            payload=payload,
        )
        for about_rate_limit in response["rateLimits"]:
            limit_type = about_rate_limit["rateLimitType"]
            limit_value = about_rate_limit["limit"]
            interval_unit = about_rate_limit["interval"]
            interval_value = about_rate_limit["intervalNum"]
            limit_name = f"{limit_type}({interval_value}{interval_unit})"
            self.binance_limits[limit_name] = limit_value

    async def reset_datapath(self, *args, **kwargs):
        question = [
            "Are you sure you want to change the data folder?",
            "Solie will shut down shortly. You will get to choose the new data folder"
            " when you start Solie again. Previous data folder does not get deleted.",
            ["No", "Yes"],
        ]
        answer = await core.window.ask(question)

        if answer in (0, 1):
            return

        await user_settings.apply_app_settings({"datapath": None})

        core.window.should_confirm_closing = False
        core.window.close()

    async def check_for_update(self, *args, **kwargs):
        should_update = find_updates.is_newer_version_available()

        if should_update:
            latest_version = find_updates.get_latest_version()
            question = [
                "Update is ready",
                "Shut down Solie and fetch the latest commits via Git."
                + f" The latest version is {latest_version},"
                + f" while the current version is {introduction.CURRENT_VERSION}.",
                ["Okay"],
            ]
            await core.window.ask(question)

    async def open_documentation(self, *args, **kwargs):
        webbrowser.open("https://solie-docs.cunarist.com")

    async def disable_system_auto_update(self, *args, **kwargs):
        if not self.settings["disable_system_update"]:
            return

        if platform.system() == "Windows":
            commands = ["sc", "stop", "wuauserv"]
            subprocess.run(commands)
            commands = ["sc", "config", "wuauserv", "start=disabled"]
            subprocess.run(commands)

        elif platform.system() == "Linux":
            pass
        elif platform.system() == "Darwin":  # macOS
            pass

    async def lock_board(self, *args, **kwargs):
        lock_window_setting = self.settings["lock_window"]

        if lock_window_setting == "NEVER":
            return
        elif lock_window_setting == "10_SECOND":
            wait_time = timedelta(seconds=10)
        elif lock_window_setting == "1_MINUTE":
            wait_time = timedelta(minutes=1)
        elif lock_window_setting == "10_MINUTE":
            wait_time = timedelta(minutes=10)
        elif lock_window_setting == "1_HOUR":
            wait_time = timedelta(hours=1)
        else:
            raise ValueError("Invalid duration value for locking the window")

        last_interaction_time = core.window.last_interaction
        if datetime.now(timezone.utc) < last_interaction_time + wait_time:
            return

        is_enabled = core.window.board.isEnabled()
        if is_enabled:
            core.window.board.setEnabled(False)


me = None


def bring_to_life():
    global me
    me = Manager()
