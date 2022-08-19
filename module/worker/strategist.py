import os
import json

from module import core
from module.worker import transactor
from module.worker import simulator
from module.recipe import check_internet
from module.recipe import user_settings


class Strategiest:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/strategist"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        # decision script
        filepath = self.workerpath + "/decision_script.txt"
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()
        else:
            script = ""
        self.decision_script = script
        core.window.undertake(
            lambda s=script: core.window.plainTextEdit_2.setPlainText(s), False
        )

        # indicators script
        filepath = self.workerpath + "/indicators_script.txt"
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()
        else:
            script = ""
        self.indicators_script = script
        core.window.undertake(
            lambda s=script: core.window.plainTextEdit_3.setPlainText(s), False
        )

        # strategy details
        try:
            filepath = self.workerpath + "/details.json"
            with open(filepath, "r", encoding="utf8") as file:
                details = json.load(file)
                self.details = details
        except FileNotFoundError:
            details = [True, 30]
            self.details = details
        core.window.undertake(
            lambda d=details: core.window.checkBox_7.setChecked(d[0]),
            False,
        )
        core.window.undertake(
            lambda d=details: core.window.spinBox_3.setValue(d[1]),
            False,
        )

        # ■■■■■ default executions ■■■■■

        # ■■■■■ repetitive schedules ■■■■■

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def save_scripts(self, *args, **kwargs):
        # decision script
        filepath = self.workerpath + "/decision_script.txt"
        script = core.window.undertake(
            lambda: core.window.plainTextEdit_2.toPlainText(), True
        )
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script)
        self.decision_script = script

        # indicators script
        filepath = self.workerpath + "/indicators_script.txt"
        script = core.window.undertake(
            lambda: core.window.plainTextEdit_3.toPlainText(), True
        )
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script)
        self.indicators_script = script

        # strategy details
        filepath = self.workerpath + "/details.json"

        def job():
            return (
                core.window.checkBox_7.isChecked(),
                core.window.spinBox_3.value(),
            )

        retuned = core.window.undertake(job, True)

        details = [retuned[0], retuned[1]]
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(details, file, indent=4)
        self.details = details

        # display to graphs
        if transactor.me.automation_settings["strategy_code"] == 0:
            transactor.me.display_lines()
        if simulator.me.calculation_settings["strategy_code"] == 0:
            simulator.me.display_lines()

    def revert_scripts(self, *args, **kwargs):
        # decision script
        def job(script=self.decision_script):
            core.window.plainTextEdit_2.setPlainText(script)

        core.window.undertake(job, False)

        # indicators script
        def job(script=self.indicators_script):
            core.window.plainTextEdit_3.setPlainText(script)

        core.window.undertake(job, False)

        # strategy details
        def job(details=self.details):
            core.window.checkBox_7.setChecked(details[0])
            core.window.spinBox_3.setValue(details[1])

        core.window.undertake(job, False)

    def fill_with_sample(self, *args, **kwargs):
        # decision script
        filepath = "./static/sample_decision_script.txt"
        with open(filepath, "r", encoding="utf8") as file:
            script = file.read()

        def job(script=script):
            core.window.plainTextEdit_2.setPlainText(script)

        core.window.undertake(job, False)

        # indicators script
        filepath = "./static/sample_indicators_script.txt"
        with open(filepath, "r", encoding="utf8") as file:
            script = file.read()

        def job(script=script):
            core.window.plainTextEdit_3.setPlainText(script)

        core.window.undertake(job, False)

        # strategy details
        def job():
            core.window.checkBox_7.setChecked(True)
            core.window.spinBox_3.setValue(30)

        core.window.undertake(job, False)

        question = [
            "Sample strategy applied",
            "It is not yet saved. Use it as you want.",
            ["Okay"],
        ]
        core.window.ask(question)


me = None


def bring_to_life():
    global me
    me = Strategiest()
