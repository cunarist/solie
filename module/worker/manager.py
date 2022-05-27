from datetime import datetime, timedelta, timezone
import threading
import os
from collections import deque
import time
import statistics
import multiprocessing
import textwrap
import logging
import webbrowser

import timesetter
import getmac

from module.instrument.api_requester import ApiRequester
from module.instrument.api_request_error import ApiRequestError
from module.recipe import simply_format
from module.recipe import check_internet
from module.recipe import process_toss
from module.recipe import standardize
from module.recipe import thread_toss
from module.recipe import find_goodies
from module.recipe import remember_task_durations


class Manager:
    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        self.root = root

        # ■■■■■ for data management ■■■■■

        self.workerpath = standardize.get_datapath() + "/manager"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

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
        self.root.undertake(
            lambda s=script: self.root.plainTextEdit.setPlainText(s), False
        )

        # ■■■■■ default executions ■■■■■

        self.root.initialize_functions.append(
            lambda: self.check_binance_limits(),
        )
        self.root.initialize_functions.append(
            lambda: self.occupy_license_key(),
        )

        # ■■■■■ repetitive schedules ■■■■■

        self.root.scheduler.add_job(
            self.check_online_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.display_system_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.display_internal_status,
            trigger="cron",
            second="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.match_system_time,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.check_license_key,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.prepare_update,
            trigger="cron",
            minute="*/10",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.check_binance_limits,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.occupy_license_key,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )
        self.root.scheduler.add_job(
            self.notify_update,
            trigger="cron",
            hour="*",
            executor="thread_pool_executor",
        )

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functrions = []
        check_internet.add_connected_functions(connected_functrions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def open_datapath(self, *args, **kwargs):
        os.startfile(standardize.get_datapath())

    def deselect_log_output(self, *args, **kwargs):
        def job():
            self.root.listWidget.clearSelection()

        self.root.undertake(job, False)

    def add_log_output(self, *args, **kwargs):
        # get the data
        log_message = args[0]

        # organize
        message_lines = log_message.split("\n")
        output_lines = []
        for original_line in message_lines:
            # split long lines
            if original_line == "":
                continue
            leading_spaces = len(original_line) - len(original_line.lstrip())
            dedented_line = textwrap.dedent(original_line)
            wrapped_line = textwrap.fill(dedented_line, width=80 - leading_spaces)
            divided_lines = wrapped_line.split("\n")
            for divided_line in divided_lines:
                indented_line = textwrap.indent(divided_line, " " * leading_spaces)
                output_lines.append(indented_line)
        if len(output_lines) > 160:
            # only preserve top and bottom if the text has too many lines
            front_lines = output_lines[:80]
            middle_lines = ["", "...", ""]
            back_lines = output_lines[-80:]
            output_lines = front_lines + middle_lines + back_lines
        log_output = "\n".join(output_lines)

        # add to log list
        self.root.undertake(lambda l=log_output: self.root.listWidget.addItem(l), False)

        # save to file
        task_start_time = datetime.now(timezone.utc)
        filepath = str(self.executed_time)
        filepath = filepath.replace(":", "_")
        filepath = filepath.replace(" ", "_")
        filepath = filepath.replace("-", "_")
        filepath = filepath.replace("+", "_")
        filepath = self.workerpath + "/log_outputs_" + filepath + ".txt"
        with open(filepath, "a", encoding="utf8") as file:
            file.write(f"{log_output}\n\n")
        duration = datetime.now(timezone.utc) - task_start_time
        duration = duration.total_seconds()
        remember_task_durations.add("write_log", duration)

    def display_internal_status(self, *args, **kwargs):
        def job():
            parent_process_id = multiprocessing.current_process().pid
            texts = []
            for process_id, thread_count in process_toss.get_thread_counts().items():
                is_parent_process = process_id == parent_process_id
                process_name = "부모 프로세스" if is_parent_process else "자식 프로세스"
                text = f"{process_name} (PID {process_id}): {thread_count}"
                texts.append(text)
            text = "\n".join(texts)
            self.root.undertake(lambda t=text: self.root.label_12.setText(t), False)

            texts = []
            texts.append("한계치")
            for limit_type, limit_value in self.binance_limits.items():
                text = f"{limit_type}: {limit_value}"
                texts.append(text)

            used_rates = self.api_requester.used_rates["real"]
            if len(used_rates) > 0:
                texts.append("")
                texts.append("정식 서버 사용량")
                for used_type, used_tuple in used_rates.items():
                    time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                    text = f"{used_type}: {used_tuple[0]}({time_string})"
                    texts.append(text)

            used_rates = self.api_requester.used_rates["testnet"]
            if len(used_rates) > 0:
                texts.append("")
                texts.append("테스트넷 서버 사용량")
                for used_type, used_tuple in used_rates.items():
                    time_string = used_tuple[1].strftime("%m-%d %H:%M:%S")
                    text = f"{used_type}: {used_tuple[0]}({time_string})"
                    texts.append(text)

            text = "\n".join(texts)
            self.root.undertake(lambda t=text: self.root.label_32.setText(t), False)

            texts = []

            task_durations = remember_task_durations.get()
            for data_name, deque_data in task_durations.items():
                if len(deque_data) > 0:
                    text = data_name
                    text += "\n"
                    data_value = sum(deque_data) / len(deque_data)
                    text += f"평균 {simply_format.fixed_float(data_value,6)}초 "
                    data_value = statistics.median(deque_data)
                    text += f"중앙 {simply_format.fixed_float(data_value,6)}초 "
                    data_value = max(deque_data)
                    text += f"최대 {simply_format.fixed_float(data_value,6)}초 "
                    data_value = min(deque_data)
                    text += f"최소 {simply_format.fixed_float(data_value,6)}초 "
                    texts.append(text)

            text = "\n\n".join(texts)
            self.root.undertake(lambda t=text: self.root.label_33.setText(t), False)

            block_sizes = self.root.collector.aggtrade_candle_sizes
            lines = (f"{symbol} {count}" for (symbol, count) in block_sizes.items())
            text = "\n".join(lines)
            self.root.undertake(lambda t=text: self.root.label_36.setText(t), False)

            thread_names = [thread.name for thread in threading.enumerate()]
            row_size = 2
            chunked = [
                thread_names[i : i + row_size]
                for i in range(0, len(thread_names), row_size)
            ]
            lines = [" ".join(chunk) for chunk in chunked]
            text = "\n".join(lines)
            self.root.undertake(lambda t=text: self.root.label_35.setText(t), False)

        for _ in range(10):
            job()
            time.sleep(0.1)

    def make_small_exception(self, *args, **kwargs):
        variable_1 = "text"
        variable_2 = 5
        variable_3 = variable_1 + variable_2
        return variable_3

    def run_script(self, *args, **kwargs):
        widget = self.root.plainTextEdit
        script_text = self.root.undertake(lambda w=widget: w.toPlainText(), True)
        filepath = self.workerpath + "/python_script.txt"
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script_text)
        namespace = {"root": self.root, "logger": logging.getLogger("solsol")}
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
        difference_string = simply_format.fixed_float(
            mean_difference, 6, positive_sign=True
        )

        text = ""
        text += "현재 시각 " + str(time)
        text += "  ⦁  "
        text += "인터넷에 연결됨" if internet_connected else "인터넷에 연결되어 있지 않음"
        text += "  ⦁  "
        text += "핑 " + simply_format.fixed_float(ping, 5) + "초"
        text += "  ⦁  "
        text += "서버와의 시차 " + difference_string + "초"
        self.root.undertake(lambda t=text: self.root.gauge.setText(t), False)

    def open_sample_ask_popup(self, *args, **kwargs):
        question = [
            "이탈리아의 수도는 어디일까요?",
            "아무 기능이 없는 코드 시험용 질문입니다.",
            ["로마", "서울", "뉴욕"],
        ]
        answer = self.root.ask(question)

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
            "정말 데이터 저장 폴더를 바꾸시겠어요?",
            "데이터 저장 폴더를 바꾸기 위해서 쏠쏠이 꺼집니다. 다음에 쏠쏠을 켤 때에 데이터 저장 폴더를 다시 고르게 됩니다. 기존 데이터"
            " 저장 폴더는 사라지지 않고 그대로 남습니다.",
            ["아니오", "예"],
        ]
        answer = self.root.ask(question)

        if answer in (0, 1):
            return

        os.remove("./note/datapath.txt")

        self.root.should_confirm_closing = False
        self.root.undertake(self.root.close, False)

    def show_version(self, *args, **kwargs):

        with open("./resource/version.txt", mode="r", encoding="utf8") as file:
            version = file.read()

        question = [
            "현재 버전입니다.",
            version,
            ["확인"],
        ]
        self.root.ask(question)

    def show_license_key(self, *args, **kwargs):

        with open("./note/license_key.txt", mode="r", encoding="utf8") as file:
            license_key = file.read()

        question = [
            "현재 라이센스 키입니다.",
            license_key,
            ["확인"],
        ]
        self.root.ask(question)

    def occupy_license_key(self, *args, **kwargs):

        license_key = standardize.get_license_key()
        payload = {
            "licenseKey": license_key,
            "macAddress": getmac.get_mac_address(),
        }
        self.api_requester.cunarist("PUT", "/api/solsol/key-mac-pair", payload)

    def check_license_key(self, *args, **kwargs):

        is_occupying_key = True
        is_key_valid = True

        license_key = standardize.get_license_key()
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
                "라이센스 키가 유효하지 않습니다.",
                f"쏠쏠이 {exit_time}에 종료됩니다.",
                ["확인"],
            ]
        elif not is_occupying_key:
            question = [
                "라이센스 키가 다른 컴퓨터에서 사용되고 있습니다.",
                f"쏠쏠이 {exit_time}에 종료됩니다.",
                ["확인"],
            ]

        os.remove("./note/license_key.txt")

        def job():
            time.sleep(wait_time)
            self.root.should_confirm_closing = False
            self.root.undertake(self.root.close, False)

        thread_toss.apply_async(job)
        self.root.ask(question)

    def prepare_update(self, *args, **kwargs):

        find_goodies.prepare()

    def notify_update(self, *args, **kwargs):

        run_duration = datetime.now(timezone.utc) - self.executed_time
        did_run_long = run_duration > timedelta(hours=12)

        is_prepared = find_goodies.get_status()

        if is_prepared and did_run_long:
            question = [
                "업데이트가 준비되었습니다.",
                "쏠쏠을 종료하고 잠시 기다렸다 다시 켜세요. 그 사이에 업데이트가 자동으로 적용됩니다.",
                ["확인"],
            ]
            self.root.ask(question)

    def open_documentation(self, *args, **kwargs):
        webbrowser.open("https://cunarist-documentation.azurewebsites.net")

    def toggle_board_availability(self, *args, **kwargs):
        is_enabled = self.root.undertake(lambda: self.root.board.isEnabled(), True)
        if is_enabled:
            self.root.undertake(lambda: self.root.board.setEnabled(False), False)
        else:
            question = [
                "보드 잠금을 해제하시겠어요?",
                "잠금을 해제하면 보드를 다시 조작할 수 있게 됩니다.",
                ["아니오", "예"],
            ]
            answer = self.root.ask(question)
            if answer in (0, 1):
                return
            self.root.undertake(lambda: self.root.board.setEnabled(True), False)
