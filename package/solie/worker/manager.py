import asyncio
import logging
import os
import statistics
import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone

import aiofiles
import aiofiles.os
import time_machine
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from solie.common import PROCESS_COUNT, go, outsource, spawn
from solie.utility import (
    ApiRequester,
    BoardLockOptions,
    ManagementSettings,
    get_task_duration,
    internet_connected,
    save_datapath,
)
from solie.widget import ask
from solie.window import Window

from .united import team

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler):
        # ■■■■■ for data management ■■■■■

        self.window = window
        self.scheduler = scheduler
        self.workerpath = window.datapath / "manager"

        # ■■■■■ internal memory ■■■■■

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.ping = 0
        self.server_time_differences = deque[float](maxlen=60)
        self.binance_limits = {}

        self.management_settings = ManagementSettings()

        time_traveller = time_machine.travel(datetime.now(timezone.utc))
        time_traveller.start()
        self.time_traveller = time_traveller

        # ■■■■■ repetitive schedules ■■■■■

        self.scheduler.add_job(
            self.lock_board,
            trigger="cron",
            second="*",
        )
        self.scheduler.add_job(
            self.display_system_status,
            trigger="cron",
            second="*",
        )
        self.scheduler.add_job(
            self.check_online_status,
            trigger="cron",
            second="*",
        )
        self.scheduler.add_job(
            self.correct_time,
            trigger="cron",
            minute="*",
        )
        self.scheduler.add_job(
            self.check_binance_limits,
            trigger="cron",
            hour="*",
        )

        # ■■■■■ websocket streamings ■■■■■

        # ■■■■■ invoked by the internet connection status change ■■■■■

        # ■■■■■ connect UI events ■■■■■

        job = self.run_script
        outsource(window.pushButton.clicked, job)
        job = self.open_datapath
        outsource(window.pushButton_8.clicked, job)
        job = self.deselect_log_output
        outsource(window.pushButton_6.clicked, job)
        job = self.reset_datapath
        outsource(window.pushButton_22.clicked, job)
        job = self.open_documentation
        outsource(window.pushButton_7.clicked, job)
        job = self.change_settings
        outsource(window.comboBox_3.currentIndexChanged, job)

    async def load(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        # settings
        filepath = self.workerpath / "management_settings.json"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                self.management_settings = ManagementSettings.from_json(content)
        board_lock_index = self.management_settings.lock_board.value
        self.window.comboBox_3.setCurrentIndex(board_lock_index)

        # python script
        filepath = self.workerpath / "python_script.txt"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                script = await file.read()
        else:
            script = "from solie.worker import team\n\nlogger.info(team)"
        self.window.plainTextEdit.setPlainText(script)

    async def change_settings(self):
        current_index = self.window.comboBox_3.currentIndex()
        self.management_settings.lock_board = BoardLockOptions(current_index)

        filepath = self.workerpath / "management_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(self.management_settings.to_json(indent=2))

    async def open_datapath(self):
        if os.name == "nt":
            await go(os.startfile, self.window.datapath)
        else:
            await ask(
                "Opening explorer is not supported on this platform.",
                "Please open the folder manually.",
                ["Okay"],
            )

    async def deselect_log_output(self):
        self.window.listWidget.clearSelection()

    async def display_internal_status(self):
        while True:
            texts = []
            all_tasks = asyncio.all_tasks()
            tasks_not_done = 0
            for task in all_tasks:
                if not task.done():
                    tasks_not_done += 1
                    text = task.get_name()
                    texts.append(text)
            max_tasks_shown = 8
            if len(texts) <= max_tasks_shown:
                list_text = "\n".join(texts)
            else:
                list_text = "\n".join(texts[:max_tasks_shown]) + "\n..."
            self.window.label_12.setText(f"{tasks_not_done} total\n\n{list_text}")

            self.window.label_32.setText(f"Process count: {PROCESS_COUNT}")

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
            self.window.label_35.setText(text)

            texts = []
            task_durations = get_task_duration()
            for data_name, deque_data in task_durations.items():
                if len(deque_data) > 0:
                    text = data_name
                    text += "\n"
                    data_value = sum(deque_data) / len(deque_data)
                    text += f"Mean {data_value:.6f}s "
                    data_value = statistics.median(deque_data)
                    text += f"Median {data_value:.6f}s "
                    text += "\n"
                    data_value = min(deque_data)
                    text += f"Minimum {data_value:.6f}s "
                    data_value = max(deque_data)
                    text += f"Maximum {data_value:.6f}s "
                    texts.append(text)
            text = "\n\n".join(texts)
            self.window.label_33.setText(text)

            texts = []
            async with team.collector.candle_data.read_lock as cell:
                candle_data_len = len(cell.data)
            texts.append(f"candle_data {candle_data_len}")
            texts.append(f"realtime_data {len(team.collector.realtime_data)}")
            texts.append(f"aggregate_trades {len(team.collector.aggregate_trades)}")
            text = "\n".join(texts)
            self.window.label_34.setText(text)

            block_sizes = team.collector.aggtrade_candle_sizes
            lines = (f"{symbol} {count}" for (symbol, count) in block_sizes.items())
            text = "\n".join(lines)
            self.window.label_36.setText(text)

            await asyncio.sleep(0.1)

    async def run_script(self):
        script_text = self.window.plainTextEdit.toPlainText()
        filepath = self.workerpath / "python_script.txt"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(script_text)
        namespace = {"logger": logger}
        exec(script_text, namespace)

    async def check_online_status(self):
        if not internet_connected():
            return

        async def job():
            request_time = datetime.now(timezone.utc)
            payload = {}
            response = await self.api_requester.binance(
                http_method="GET",
                path="/fapi/v1/time",
                payload=payload,
            )
            response_time = datetime.now(timezone.utc)
            ping = (response_time - request_time).total_seconds()
            self.ping = ping

            server_timestamp = response["serverTime"] / 1000
            server_time = datetime.fromtimestamp(server_timestamp, tz=timezone.utc)
            local_time = datetime.now(timezone.utc)
            time_difference = (server_time - local_time).total_seconds() - ping / 2
            self.server_time_differences.append(time_difference)

        spawn(job())

    async def display_system_status(self):
        time = datetime.now(timezone.utc)
        time_text = time.strftime("%Y-%m-%d %H:%M:%S")
        is_internet_connected = internet_connected()
        ping = self.ping
        board_enabled = self.window.board.isEnabled()

        deque_data = self.server_time_differences
        if len(deque_data) > 0:
            mean_difference = sum(deque_data) / len(deque_data)
        else:
            mean_difference = 0.0

        text = ""
        text += f"Current time UTC {time_text}"
        text += "  ⦁  "
        if is_internet_connected:
            text += "Connected to the internet"
        else:
            text += "Not connected to the internet"
        text += "  ⦁  "
        text += f"Ping {ping:.3f}s"
        text += "  ⦁  "
        text += f"Server time difference {mean_difference:+.3f}s"
        text += "  ⦁  "
        text += f"Board {('unlocked' if board_enabled else 'locked')}"
        self.window.gauge.setText(text)

    async def correct_time(self):
        server_time_differences = self.server_time_differences
        if len(server_time_differences) < 30:
            return
        mean_difference = sum(server_time_differences) / len(server_time_differences)
        new_time = datetime.now(timezone.utc) + timedelta(seconds=mean_difference)

        self.time_traveller.stop()
        time_traveller = time_machine.travel(new_time)
        time_traveller.start()
        self.time_traveller = time_traveller

    async def check_binance_limits(self):
        if not internet_connected():
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

    async def reset_datapath(self):
        answer = await ask(
            "Are you sure you want to change the data folder?",
            "Solie will shut down shortly. You will get to choose the new data folder"
            " when you start Solie again. Previous data folder does not get deleted.",
            ["No", "Yes"],
        )

        if answer in (0, 1):
            return

        await save_datapath(None)

        self.window.should_confirm_closing = False
        self.window.close()

    async def open_documentation(self):
        await go(webbrowser.open, "https://solie-docs.cunarist.com")

    async def lock_board(self):
        lock_board = self.management_settings.lock_board

        if lock_board == BoardLockOptions.NEVER:
            return
        elif lock_board == BoardLockOptions.SECONDS_10:
            wait_time = timedelta(seconds=10)
        elif lock_board == BoardLockOptions.MINUTE_1:
            wait_time = timedelta(minutes=1)
        elif lock_board == BoardLockOptions.MINUTE_10:
            wait_time = timedelta(minutes=10)
        elif lock_board == BoardLockOptions.HOUR_1:
            wait_time = timedelta(hours=1)
        else:
            raise ValueError("Invalid duration value for locking the window")

        last_interaction_time = self.window.last_interaction
        if datetime.now(timezone.utc) < last_interaction_time + wait_time:
            return

        is_enabled = self.window.board.isEnabled()
        if is_enabled:
            self.window.board.setEnabled(False)
