from datetime import datetime, timedelta, timezone
import threading
import os
from collections import deque
import time
import statistics
import logging
import webbrowser

import timesetter
import getmac

from module import introduction
from module import core
from module import process_toss
from module import thread_toss
from module.worker import collector
from module.instrument.api_requester import ApiRequester
from module.instrument.api_request_error import ApiRequestError
from module.recipe import simply_format
from module.recipe import check_internet
from module.recipe import user_settings
from module.recipe import find_goodies
from module.recipe import remember_task_durations


class Manager:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/manager"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        self.api_requester = ApiRequester()

        self.executed_time = datetime.now(timezone.utc).replace(microsecond=0)
        self.is_terminal_visible = False

        self.online_status = {
            "ping": 0,
            "server_time_differences": deque(maxlen=120),
        }
        self.binance_limits = {}

        filepath = self.workerpath + "/python_script.txt"
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()
        else:
            script = ""
        core.window.undertake(
            lambda s=script: core.window.plainTextEdit.setPlainText(s), False
        )

        # ■■■■■ default executions ■■■■■

        core.window.initialize_functions.append(
            lambda: self.check_binance_limits(),
        )
        core.window.initialize_functions.append(
            lambda: self.occupy_license_key(),
        )

        # ■■■■■ repetitive schedules ■■■■■

        core.window.scheduler.add_job(
            self.check_online_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.display_system_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.display_internal_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.match_system_time,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.check_license_key,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.prepare_update,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.check_binance_limits,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.occupy_license_key,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        core.window.scheduler.add_job(
            self.notify_update,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def open_datapath(self, *args, **kwargs):
        os.startfile(user_settings.get_app_settings()["datapath"])

    def deselect_log_output(self, *args, **kwargs):
        def job():
            core.window.listWidget.clearSelection()

        core.window.undertake(job, False)

    def add_log_output(self, *args, **kwargs):
        # get the data
        log_text = args[0]

        # add to log list
        job = core.window.listWidget.addItem
        payload = (job, log_text)
        core.window.undertake(lambda p=payload: p[0](p[1]), False)

        # save to file
        task_start_time = datetime.now(timezone.utc)
        filepath = str(self.executed_time)
        filepath = filepath.replace(":", "_")
        filepath = filepath.replace(" ", "_")
        filepath = filepath.replace("-", "_")
        filepath = filepath.replace("+", "_")
        filepath = self.workerpath + "/log_outputs_" + filepath + ".txt"
        with open(filepath, "a", encoding="utf8") as file:
            file.write(f"{log_text}\n\n")
        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
        remember_task_durations.add("write_log", duration)

    def display_internal_status(self, *args, **kwargs):
        def job():
            active_count = 0
            texts = []
            task_presences = thread_toss.get_task_presences()
            for thread_name, is_task_present in task_presences.items():
                if is_task_present:
                    active_count += 1
                text = thread_name
                text += f": {'Active' if is_task_present else 'Inactive'}"
                texts.append(text)
            text = f"{active_count} active"
            text += "\n\n" + "\n".join(texts)
            core.window.undertake(lambda t=text: core.window.label_12.setText(t), False)

            active_count = 0
            texts = []
            task_presences = process_toss.get_task_presences()
            for process_id, is_task_present in task_presences.items():
                if is_task_present:
                    active_count += 1
                text = f"PID {process_id}"
                text += f": {'Active' if is_task_present else 'Inactive'}"
                texts.append(text)
            text = f"{active_count} active"
            text += "\n\n" + "\n".join(texts)
            core.window.undertake(lambda t=text: core.window.label_32.setText(t), False)

            texts = []
            texts.append("Limits")
            for limit_type, limit_value in self.binance_limits.items():
                text = f"{limit_type}: {limit_value}"
                texts.append(text)

            used_rates = self.api_requester.used_rates["real"]
            if len(used_rates) > 0:
                texts.append("")
                texts.append("Real server usage")
                for used_type, used_tuple in used_rates.items():
                    time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                    text = f"{used_type}: {used_tuple[0]}({time_string})"
                    texts.append(text)

            used_rates = self.api_requester.used_rates["testnet"]
            if len(used_rates) > 0:
                texts.append("")
                texts.append("Testnet server usage")
                for used_type, used_tuple in used_rates.items():
                    time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                    text = f"{used_type}: {used_tuple[0]}({time_string})"
                    texts.append(text)

            text = "\n".join(texts)
            core.window.undertake(lambda t=text: core.window.label_35.setText(t), False)

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
            core.window.undertake(lambda t=text: core.window.label_33.setText(t), False)

            block_sizes = collector.me.aggtrade_candle_sizes
            lines = (f"{symbol} {count}" for (symbol, count) in block_sizes.items())
            text = "\n".join(lines)
            core.window.undertake(lambda t=text: core.window.label_36.setText(t), False)

        for _ in range(10):
            job()
            time.sleep(0.1)

    def make_small_exception(self, *args, **kwargs):
        variable_1 = "text"
        variable_2 = 5
        variable_3 = variable_1 + variable_2
        return variable_3

    def run_script(self, *args, **kwargs):
        widget = core.window.plainTextEdit
        script_text = core.window.undertake(lambda w=widget: w.toPlainText(), True)
        if "# long live cunarist" not in script_text:
            question = [
                "Execution condition is not fulfilled",
                "Fulfill the condition first to run the script",
                ["Okay"],
                False,
            ]
            core.window.ask(question)
            return
        filepath = self.workerpath + "/python_script.txt"
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script_text)
        namespace = {"window": core.window, "logger": logging.getLogger("solsol")}
        exec(script_text, namespace)

    def check_online_status(self, *args, **kwargs):
        if not check_internet.connected():
            return

        request_time = datetime.now(timezone.utc)
        payload = {}
        response = self.api_requester.binance(
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

    def display_system_status(self, *args, **kwargs):
        time = datetime.now(timezone.utc).replace(microsecond=0)
        internet_connected = check_internet.connected()
        ping = self.online_status["ping"]

        deque_data = self.online_status["server_time_differences"]
        if len(deque_data) > 0:
            mean_difference = sum(deque_data) / len(deque_data)
        else:
            mean_difference = 0

        text = ""
        text += "Current time " + str(time)
        text += "  ⦁  "
        if internet_connected:
            text += "Connected to the internet"
        else:
            text += "Not connected to the internet"
        text += "  ⦁  "
        text += f"Ping {ping:.3f}s"
        text += "  ⦁  "
        text += f"Time difference with server {mean_difference:+.3f}s"
        core.window.undertake(lambda t=text: core.window.gauge.setText(t), False)

    def open_sample_ask_popup(self, *args, **kwargs):
        question = [
            "Where is the capital of italy?",
            "This is a question solely for testing purposes.",
            ["Rome", "Seoul", "New York"],
            False,
        ]
        answer = core.window.ask(question)

        text = f"You chose answer {answer} from the test popup"
        logger = logging.getLogger("solsol")
        logger.info(text)

    def match_system_time(self, *args, **kwargs):
        server_time_differences = self.online_status["server_time_differences"]
        if len(server_time_differences) < 60:
            return
        mean_difference = sum(server_time_differences) / len(server_time_differences)
        new_time = datetime.now(timezone.utc) - timedelta(seconds=mean_difference)
        timesetter.set(new_time)
        server_time_differences.clear()
        server_time_differences.append(0)

    def check_binance_limits(self, *args, **kwargs):
        if not check_internet.connected():
            return

        payload = {}
        response = self.api_requester.binance(
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

    def reset_datapath(self, *args, **kwargs):
        question = [
            "Are you sure you want to change the data folder?",
            "Solsol will shut down shortly. You will get to choose the new data folder"
            " when you start Solsol again. Previous data folder does not get deleted.",
            ["No", "Yes"],
            False,
        ]
        answer = core.window.ask(question)

        if answer in (0, 1):
            return

        user_settings.apply_app_settings({"datapath": None})

        core.window.should_confirm_closing = False
        core.window.undertake(core.window.close, False)

    def show_version(self, *args, **kwargs):
        version = introduction.CURRENT_VERSION

        question = [
            "Current Solsol version",
            version,
            ["Okay"],
            False,
        ]
        core.window.ask(question)

    def show_license_key(self, *args, **kwargs):
        license_key = user_settings.get_app_settings()["license_key"]

        question = [
            "Solsol license key",
            license_key,
            ["Okay"],
            False,
        ]
        core.window.ask(question)

    def occupy_license_key(self, *args, **kwargs):
        license_key = user_settings.get_app_settings()["license_key"]
        payload = {
            "licenseKey": license_key,
            "macAddress": getmac.get_mac_address(),
        }
        self.api_requester.cunarist("PUT", "/api/solsol/key-mac-pair", payload)

    def check_license_key(self, *args, **kwargs):
        is_occupying_key = True
        is_key_valid = True

        license_key = user_settings.get_app_settings()["license_key"]
        try:
            payload = {
                "licenseKey": license_key,
            }
            response = self.api_requester.cunarist(
                "GET", "/api/solsol/key-mac-pair", payload
            )
            if response["macAddress"] != getmac.get_mac_address():
                is_occupying_key = False
        except ApiRequestError:
            is_key_valid = False

        if is_key_valid and is_occupying_key:
            return

        wait_time = 300
        exit_time = datetime.now(timezone.utc) + timedelta(seconds=wait_time)
        exit_time = exit_time.replace(microsecond=0)

        if not is_key_valid:
            question = [
                "License key not valid",
                f"Solsol will shut down at {exit_time}",
                ["Okay"],
                False,
            ]
        elif not is_occupying_key:
            question = [
                "License key is being used by another computer",
                f"Solsol will shut down at {exit_time}",
                ["Okay"],
                False,
            ]

        user_settings.apply_app_settings({"license_key": None})

        def job():
            time.sleep(wait_time)
            core.window.should_confirm_closing = False
            core.window.undertake(core.window.close, False)

        thread_toss.apply_async(job)
        core.window.ask(question)

    def prepare_update(self, *args, **kwargs):
        find_goodies.prepare()

    def notify_update(self, *args, **kwargs):
        run_duration = datetime.now(timezone.utc) - self.executed_time
        did_run_long = run_duration > timedelta(hours=12)

        is_prepared = find_goodies.get_updater_status()

        if is_prepared and did_run_long:
            question = [
                "Update is ready",
                "Shut down Solsol and wait for a while. Update will be automatically"
                " installed.",
                ["Okay"],
                False,
            ]
            core.window.ask(question)

    def open_documentation(self, *args, **kwargs):
        webbrowser.open("https://cunarist.com/solsol")

    def toggle_board_availability(self, *args, **kwargs):
        is_enabled = core.window.undertake(lambda: core.window.board.isEnabled(), True)
        if is_enabled:
            core.window.undertake(lambda: core.window.board.setEnabled(False), False)
        else:
            question = [
                "Unlock the board?",
                "You will be able to manipulate the board again.",
                ["No", "Yes"],
                False,
            ]
            answer = core.window.ask(question)
            if answer in (0, 1):
                return
            core.window.undertake(lambda: core.window.board.setEnabled(True), False)


me = None


def bring_to_life():
    global me
    me = Manager()
