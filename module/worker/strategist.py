import os
import json

from PySide6 import QtGui, QtWidgets

from module import core
from module.recipe import check_internet
from module.recipe import user_settings
from module.recipe import standardize
from module.recipe import outsource
from module.shelf.strategy_basic_input import StrategyBasicInput
from module.shelf.strategy_develop_input import StrategyDevelopInput
from module.shelf.strategy_info_view import StrategyInfoView


class Strategiest:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/strategist"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        # custom strategies
        try:
            filepath = self.workerpath + "/strategies.json"
            with open(filepath, "r", encoding="utf8") as file:
                self.strategies = json.load(file)
        except FileNotFoundError:
            first_strategy = standardize.strategy()
            first_strategy["code_name"] = "SLIESS"
            first_strategy["readable_name"] = "Sample Strategy"
            first_strategy["description"] = (
                "Not for real investment."
                + " This strategy is only for demonstration purposes."
            )
            first_strategy["risk_level"] = 2
            filepath = "./static/sample_indicators_script.txt"
            with open(filepath, "r", encoding="utf8") as file:
                read_data = file.read()
                first_strategy["indicators_script"] = read_data
            filepath = "./static/sample_decision_script.txt"
            with open(filepath, "r", encoding="utf8") as file:
                read_data = file.read()
                first_strategy["decision_script"] = read_data
            self.strategies = [first_strategy]
        self.strategy_cards = []

        self.red_pixmap = QtGui.QPixmap()
        self.red_pixmap.load("./static/icon/traffic_light_red.png")
        self.yellow_pixmap = QtGui.QPixmap()
        self.yellow_pixmap.load("./static/icon/traffic_light_yellow.png")
        self.green_pixmap = QtGui.QPixmap()
        self.green_pixmap.load("./static/icon/traffic_light_green.png")

        # ■■■■■ repetitive schedules ■■■■■

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = []

        # ■■■■■ invoked by the internet connection  ■■■■■

        connected_functions = []
        check_internet.add_connected_functions(connected_functions)

        disconnected_functions = []
        check_internet.add_disconnected_functions(disconnected_functions)

    def save_strategies(self, *args, **kwargs):
        filepath = self.workerpath + "/strategies.json"
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(self.strategies, file, indent=4)

    def display_strategies(self, *args, **kwargs):
        def job():
            core.window.comboBox_2.clear()
            core.window.comboBox.clear()
            for strategy_card in self.strategy_cards:
                strategy_card.setParent(None)
            self.strategy_cards = []

            for strategy in self.strategies:
                if strategy["risk_level"] == 0:
                    icon_pixmap = self.red_pixmap
                elif strategy["risk_level"] == 1:
                    icon_pixmap = self.yellow_pixmap
                elif strategy["risk_level"] == 2:
                    icon_pixmap = self.green_pixmap
                text = f"{strategy['code_name']} {strategy['version']}"
                text += f" - {strategy['readable_name']}"
                traffic_light_icon = QtGui.QIcon()
                traffic_light_icon.addPixmap(icon_pixmap)

                core.window.comboBox_2.addItem(traffic_light_icon, text)
                core.window.comboBox.addItem(traffic_light_icon, text)

                strategy_card = QtWidgets.QGroupBox()
                core.window.verticalLayout_16.addWidget(strategy_card)
                self.strategy_cards.append(strategy_card)
                card_layout = QtWidgets.QHBoxLayout(strategy_card)

                icon_label = QtWidgets.QLabel("")
                card_layout.addWidget(icon_label)
                icon_label.setPixmap(icon_pixmap)
                icon_label.setScaledContents(True)
                icon_label.setFixedSize(16, 16)

                text_label = QtWidgets.QLabel(text)
                card_layout.addWidget(text_label)

                spacer = QtWidgets.QSpacerItem(
                    0,
                    0,
                    QtWidgets.QSizePolicy.Policy.Expanding,
                    QtWidgets.QSizePolicy.Policy.Minimum,
                )
                card_layout.addItem(spacer)

                def job(strategy=strategy):
                    before_selections = self.remember_strategy_selections()
                    formation = [
                        "Develop your strategy",
                        StrategyDevelopInput,
                        True,
                        strategy,
                    ]
                    core.window.overlap(formation)
                    self.display_strategies()
                    self.save_strategies()
                    self.restore_strategy_selections(before_selections)

                edit_button = QtWidgets.QPushButton("Develop")
                card_layout.addWidget(edit_button)
                outsource.do(edit_button.clicked, job)

                def job(strategy=strategy):
                    before_selections = self.remember_strategy_selections()
                    formation = [
                        "Edit your strategy's basic information",
                        StrategyBasicInput,
                        True,
                        strategy,
                    ]
                    core.window.overlap(formation)
                    self.display_strategies()
                    self.save_strategies()
                    self.restore_strategy_selections(before_selections)

                edit_button = QtWidgets.QPushButton("Edit basic info")
                card_layout.addWidget(edit_button)
                outsource.do(edit_button.clicked, job)

                def job(strategy=strategy):
                    question = [
                        "Remove this strategy?",
                        "If you remove this strategy, it cannot be recovered"
                        + " unless a new data folder is made.",
                        ["Remove"],
                    ]
                    answer = core.window.ask(question)
                    if answer == 0:
                        return
                    before_selections = self.remember_strategy_selections()
                    self.strategies.remove(strategy)
                    self.display_strategies()
                    self.save_strategies()
                    self.restore_strategy_selections(before_selections)

                edit_button = QtWidgets.QPushButton("Remove")
                card_layout.addWidget(edit_button)
                outsource.do(edit_button.clicked, job)

                def job(strategy=strategy):
                    before_selections = self.remember_strategy_selections()
                    original_index = self.strategies.index(strategy)
                    after_index = original_index + 1
                    self.strategies.pop(original_index)
                    self.strategies.insert(after_index, strategy)
                    self.display_strategies()
                    self.save_strategies()
                    self.restore_strategy_selections(before_selections)

                edit_button = QtWidgets.QPushButton("▼")
                card_layout.addWidget(edit_button)
                outsource.do(edit_button.clicked, job)

                def job(strategy=strategy):
                    before_selections = self.remember_strategy_selections()
                    original_index = self.strategies.index(strategy)
                    after_index = original_index - 1
                    self.strategies.pop(original_index)
                    self.strategies.insert(after_index, strategy)
                    self.display_strategies()
                    self.save_strategies()
                    self.restore_strategy_selections(before_selections)

                edit_button = QtWidgets.QPushButton("▲")
                card_layout.addWidget(edit_button)
                outsource.do(edit_button.clicked, job)

        core.window.undertake(job, False)

    def add_blank_strategy(self, *args, **kwargs):
        new_strategy = standardize.strategy()
        self.strategies.append(new_strategy)
        self.display_strategies()

    def remember_strategy_selections(self, *args, **kwargs):
        def job():
            before_selections = {}
            before_index = core.window.comboBox_2.currentIndex()
            before_selections["transactor"] = self.strategies[before_index]
            before_index = core.window.comboBox.currentIndex()
            before_selections["simulator"] = self.strategies[before_index]
            return before_selections

        before_selections = core.window.undertake(job, True)
        return before_selections

    def restore_strategy_selections(self, *args, **kwargs):
        before_selections = args[0]

        def job():
            if before_selections["transactor"] in self.strategies:
                new_index = self.strategies.index(before_selections["transactor"])
                core.window.comboBox_2.setCurrentIndex(new_index)
            if before_selections["simulator"] in self.strategies:
                new_index = self.strategies.index(before_selections["simulator"])
                core.window.comboBox.setCurrentIndex(new_index)

        core.window.undertake(job, False)


me = None


def bring_to_life():
    global me
    me = Strategiest()
