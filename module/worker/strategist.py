import threading
import os
import json

from module.recipe import check_internet
from module.recipe import standardize


class Strategiest:
    def __init__(self, root):

        # ■■■■■ the basic ■■■■■

        self.root = root

        # ■■■■■ for data management ■■■■■

        self.workerpath = standardize.get_datapath() + "/strategist"
        os.makedirs(self.workerpath, exist_ok=True)
        self.datalocks = [threading.Lock() for _ in range(8)]

        # ■■■■■ remember and display ■■■■■

        # decision script
        filepath = self.workerpath + "/decision_script.txt"
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()
        else:
            script = ""
        self.decision_script = script
        self.root.undertake(
            lambda s=script: self.root.plainTextEdit_2.setPlainText(s), False
        )

        # indicators script
        filepath = self.workerpath + "/indicators_script.txt"
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf8") as file:
                script = file.read()
        else:
            script = ""
        self.indicators_script = script
        self.root.undertake(
            lambda s=script: self.root.plainTextEdit_3.setPlainText(s), False
        )

        # strategy details
        try:
            filepath = self.workerpath + "/details.json"
            with open(filepath, "r", encoding="utf8") as file:
                details = json.load(file)
                self.details = details
        except FileNotFoundError:
            details = [True, True, 30, False]
            self.details = details
        self.root.undertake(
            lambda d=details: self.root.checkBox_6.setChecked(d[0]),
            False,
        )
        self.root.undertake(
            lambda d=details: self.root.checkBox_7.setChecked(d[1]),
            False,
        )
        self.root.undertake(
            lambda d=details: self.root.spinBox_3.setValue(d[2]),
            False,
        )
        if details[3]:
            self.root.undertake(
                lambda: self.root.radioButton_11.setChecked(False), False
            )
            self.root.undertake(
                lambda: self.root.radioButton_12.setChecked(True), False
            )
        else:
            self.root.undertake(
                lambda: self.root.radioButton_11.setChecked(True), False
            )
            self.root.undertake(
                lambda: self.root.radioButton_12.setChecked(False), False
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
        script = self.root.undertake(
            lambda: self.root.plainTextEdit_2.toPlainText(), True
        )
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script)
        self.decision_script = script

        # indicators script
        filepath = self.workerpath + "/indicators_script.txt"
        script = self.root.undertake(
            lambda: self.root.plainTextEdit_3.toPlainText(), True
        )
        with open(filepath, "w", encoding="utf8") as file:
            file.write(script)
        self.indicators_script = script

        # strategy details
        filepath = self.workerpath + "/details.json"

        def job():
            return (
                self.root.checkBox_6.isChecked(),
                self.root.checkBox_7.isChecked(),
                self.root.spinBox_3.value(),
                self.root.radioButton_12.isChecked(),
            )

        retuned = self.root.undertake(job, True)

        details = [retuned[0], retuned[1], retuned[2], retuned[3]]
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(details, file, indent=4)
        self.details = details

        # display to graphs
        if self.root.transactor.automation_settings["strategy"] == 0:
            self.root.transactor.display_lines()
        if self.root.simulator.calculation_settings["strategy"] == 0:
            self.root.simulator.display_lines()

    def revert_scripts(self, *args, **kwargs):

        # decision script
        def job(script=self.decision_script):
            self.root.plainTextEdit_2.setPlainText(script)

        self.root.undertake(job, False)

        # indicators script
        def job(script=self.indicators_script):
            self.root.plainTextEdit_3.setPlainText(script)

        self.root.undertake(job, False)

        # strategy details
        def job(details=self.details):
            self.root.checkBox_6.setChecked(details[0])
            self.root.checkBox_7.setChecked(details[1])
            self.root.spinBox_3.setValue(details[2])
            if details[3]:
                self.root.radioButton_11.setChecked(False)
                self.root.radioButton_12.setChecked(True)
            else:
                self.root.radioButton_11.setChecked(True)
                self.root.radioButton_12.setChecked(False)

        self.root.undertake(job, False)

    def fill_with_sample(self, *args, **kwargs):

        # decision script
        filepath = "./resource/sample_decision_script.txt"
        with open(filepath, "r", encoding="utf8") as file:
            script = file.read()

        def job(script=script):
            self.root.plainTextEdit_2.setPlainText(script)

        self.root.undertake(job, False)

        # indicators script
        filepath = "./resource/sample_indicators_script.txt"
        with open(filepath, "r", encoding="utf8") as file:
            script = file.read()

        def job(script=script):
            self.root.plainTextEdit_3.setPlainText(script)

        self.root.undertake(job, False)

        # strategy details
        def job():
            self.root.checkBox_6.setChecked(True)
            self.root.checkBox_7.setChecked(True)
            self.root.spinBox_3.setValue(30)
            self.root.radioButton_11.setChecked(True)
            self.root.radioButton_12.setChecked(False)

        self.root.undertake(job, False)

        question = [
            "샘플 전략으로 채웠습니다.",
            "아직 저장되지는 않았습니다. 원하실 때 저장하세요.",
            ["확인"],
            False,
        ]
        self.root.ask(question)
