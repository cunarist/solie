"""Application manager worker."""

import os
import statistics
import webbrowser
from asyncio import all_tasks, sleep
from collections import deque
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any

import aiofiles
import aiofiles.os
import time_machine
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from solie.common import PROCESS_COUNT, outsource, spawn, spawn_blocking
from solie.utility import (
    MIN_SERVER_TIME_SAMPLES,
    ApiRequester,
    BoardLockOptions,
    DurationRecorder,
    ManagementSettings,
    internet_connected,
    save_datapath,
)
from solie.widget import ask
from solie.window import Window

from .united import team

logger = getLogger(__name__)


class Manager:
    """Worker for managing application state and UI."""

    def __init__(self, window: Window, scheduler: AsyncIOScheduler) -> None:
        """Initialize application manager."""
        self._window = window
        self._scheduler = scheduler
        self._workerpath = window.datapath / "manager"

        self._api_requester = ApiRequester()

        self._ping = 0
        self._server_time_differences = deque[float](maxlen=60)
        self._binance_limits: dict[str, int] = {}

        self._management_settings = ManagementSettings()

        time_traveller = time_machine.travel(datetime.now(UTC))
        time_traveller.start()
        self._time_traveller = time_traveller

        self._scheduler.add_job(
            self._lock_board,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._display_system_status,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._check_online_status,
            trigger="cron",
            second="*",
        )
        self._scheduler.add_job(
            self._correct_time,
            trigger="cron",
            minute="*",
        )
        self._scheduler.add_job(
            self.check_binance_limits,
            trigger="cron",
            hour="*",
        )

        self._connect_ui_events()

    def _connect_ui_events(self) -> None:
        window = self._window

        job = self._run_script
        outsource(window.pushButton.clicked, job)
        job = self._open_datapath
        outsource(window.pushButton_8.clicked, job)
        job = self._deselect_log_output
        outsource(window.pushButton_6.clicked, job)
        job = self._reset_datapath
        outsource(window.pushButton_22.clicked, job)
        job = self._open_documentation
        outsource(window.pushButton_7.clicked, job)
        job = self._change_settings
        outsource(window.comboBox_3.currentIndexChanged, job)

    async def load_work(self) -> None:
        """Load management settings from disk."""
        await aiofiles.os.makedirs(self._workerpath, exist_ok=True)

        filepath = self._workerpath / "management_settings.json"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, encoding="utf8") as file:
                self._management_settings = ManagementSettings.model_validate_json(
                    await file.read(),
                )
        board_lock_index = self._management_settings.lock_board.value
        self._window.comboBox_3.setCurrentIndex(board_lock_index)

        filepath = self._workerpath / "python_script.txt"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, encoding="utf8") as file:
                script = await file.read()
        else:
            script = "from solie.worker import team\n\nlogger.info(team)"
        self._window.plainTextEdit.setPlainText(script)

    async def dump_work(self) -> None:
        """Save management settings to disk."""

    async def _change_settings(self) -> None:
        current_index = self._window.comboBox_3.currentIndex()
        self._management_settings.lock_board = BoardLockOptions(current_index)

        filepath = self._workerpath / "management_settings.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(self._management_settings.model_dump_json(indent=2))

    async def _open_datapath(self) -> None:
        if os.name == "nt":
            await spawn_blocking(os.startfile, self._window.datapath)
        else:
            await ask(
                "Opening explorer is not supported on this platform.",
                "Please open the folder manually.",
                ["Okay"],
            )

    async def _deselect_log_output(self) -> None:
        self._window.listWidget.clearSelection()

    async def display_internal_status(self) -> None:
        """Display internal status information on the UI."""
        while True:
            self._display_task_status()
            self._display_process_count()
            self._display_api_limits_and_usage()
            self._display_task_durations()
            await self._display_data_sizes()
            self._display_block_sizes()
            await sleep(0.1)

    def _display_task_status(self) -> None:
        """Display current task status."""
        texts: list[str] = []
        tasks = all_tasks()
        tasks_not_done = 0

        for task in tasks:
            if not task.done():
                tasks_not_done += 1
                text = task.get_name()
                texts.append(text)

        max_tasks_shown = 8
        if len(texts) <= max_tasks_shown:
            list_text = "\n".join(texts)
        else:
            list_text = "\n".join(texts[:max_tasks_shown]) + "\n..."

        self._window.label_12.setText(f"{tasks_not_done} total\n\n{list_text}")

    def _display_process_count(self) -> None:
        """Display process count."""
        self._window.label_32.setText(f"Process count: {PROCESS_COUNT}")

    def _display_api_limits_and_usage(self) -> None:
        """Display API limits and usage information."""
        texts: list[str] = []
        texts.append("Limits")

        for limit_type, limit_value in self._binance_limits.items():
            text = f"{limit_type}: {limit_value}"
            texts.append(text)

        used_rates = self._api_requester.used_rates
        if len(used_rates) > 0:
            texts.append("")
            texts.append("Usage")
            for used_type, used_tuple in used_rates.items():
                time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                text = f"{used_type}: {used_tuple[0]}({time_string})"
                texts.append(text)

        text = "\n".join(texts)
        self._window.label_35.setText(text)

    def _display_task_durations(self) -> None:
        """Display task duration statistics."""
        texts: list[str] = []
        task_durations = DurationRecorder.task_durations

        for data_name, deque_data in task_durations.items():
            if len(deque_data) > 0:
                text = data_name
                text += "\n"
                data_value = sum(d.duration for d in deque_data) / len(deque_data)
                text += f"Mean {data_value:.6f}s "
                data_value = statistics.median(d.duration for d in deque_data)
                text += f"Median {data_value:.6f}s "
                text += "\n"
                data_value = min(deque_data).duration
                text += f"Minimum {data_value:.6f}s "
                data_value = max(deque_data).duration
                text += f"Maximum {data_value:.6f}s "
                texts.append(text)

        text = "\n\n".join(texts)
        self._window.label_33.setText(text)

    async def _display_data_sizes(self) -> None:
        """Display data structure sizes."""
        texts: list[str] = []

        async with team.collector.candle_data.read_lock as cell:
            candle_data_len = len(cell.data)

        texts.append(f"CANDLE_DATA {candle_data_len}")
        texts.append(f"REALTIME_DATA {len(team.collector.realtime_data)}")
        texts.append(f"AGGREGATE_TRADES {len(team.collector.aggregate_trades)}")

        text = "\n".join(texts)
        self._window.label_34.setText(text)

    def _display_block_sizes(self) -> None:
        """Display block sizes for each symbol."""
        block_sizes = team.collector.aggtrade_candle_sizes
        lines = (f"{symbol} {count}" for (symbol, count) in block_sizes.items())
        text = "\n".join(lines)
        self._window.label_36.setText(text)

    async def _run_script(self) -> None:
        script_text = self._window.plainTextEdit.toPlainText()
        filepath = self._workerpath / "python_script.txt"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(script_text)
        namespace = {"logger": logger}
        exec(script_text, namespace)

    async def _check_online_status(self) -> None:
        if not internet_connected():
            return

        async def job() -> None:
            request_time = datetime.now(UTC)
            payload: dict[str, Any] = {}
            response = await self._api_requester.binance(
                http_method="GET",
                path="/fapi/v1/time",
                payload=payload,
            )
            response_time = datetime.now(UTC)
            ping = (response_time - request_time).total_seconds()
            self._ping = ping

            server_timestamp = response["serverTime"] / 1000
            server_time = datetime.fromtimestamp(server_timestamp, tz=UTC)
            local_time = datetime.now(UTC)
            time_difference = (server_time - local_time).total_seconds() - ping / 2
            self._server_time_differences.append(time_difference)

        spawn(job())

    async def _display_system_status(self) -> None:
        time = datetime.now(UTC)
        time_text = time.strftime("%Y-%m-%d %H:%M:%S")
        is_internet_connected = internet_connected()
        ping = self._ping
        board_enabled = self._window.board.isEnabled()

        deque_data = self._server_time_differences
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
        self._window.gauge.setText(text)

    async def _correct_time(self) -> None:
        server_time_differences = self._server_time_differences
        if len(server_time_differences) < MIN_SERVER_TIME_SAMPLES:
            return
        mean_difference = sum(server_time_differences) / len(server_time_differences)
        new_time = datetime.now(UTC) + timedelta(seconds=mean_difference)

        self._time_traveller.stop()
        time_traveller = time_machine.travel(new_time)
        time_traveller.start()
        self._time_traveller = time_traveller

    async def check_binance_limits(self) -> None:
        """Check Binance API rate limits."""
        if not internet_connected():
            return

        payload: dict[str, Any] = {}
        response = await self._api_requester.binance(
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
            self._binance_limits[limit_name] = limit_value

    async def _reset_datapath(self) -> None:
        answer = await ask(
            "Are you sure you want to change the data folder?",
            "Solie will shut down shortly. You will get to choose the new data folder"
            " when you start Solie again. Previous data folder does not get deleted.",
            ["No", "Yes"],
        )

        if answer in (0, 1):
            return

        await save_datapath(None)

        self._window.should_confirm_closing = False
        self._window.close()

    async def _open_documentation(self) -> None:
        await spawn_blocking(webbrowser.open, "https://solie-docs.cunarist.com")

    async def _lock_board(self) -> None:
        lock_board = self._management_settings.lock_board

        if lock_board == BoardLockOptions.NEVER:
            return
        if lock_board == BoardLockOptions.SECONDS_10:
            wait_time = timedelta(seconds=10)
        elif lock_board == BoardLockOptions.MINUTE_1:
            wait_time = timedelta(minutes=1)
        elif lock_board == BoardLockOptions.MINUTE_10:
            wait_time = timedelta(minutes=10)
        elif lock_board == BoardLockOptions.HOUR_1:
            wait_time = timedelta(hours=1)
        else:
            msg = "Invalid duration value for locking the window"
            raise ValueError(msg)

        last_interaction_time = self._window.last_interaction
        if datetime.now(UTC) < last_interaction_time + wait_time:
            return

        is_enabled = self._window.board.isEnabled()
        if is_enabled:
            self._window.board.setEnabled(False)
