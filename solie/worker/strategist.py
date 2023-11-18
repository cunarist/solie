import asyncio
import json
import os

import aiofiles
from PySide6 import QtGui, QtWidgets

import solie
from solie.recipe import check_internet, outsource, standardize, user_settings
from solie.shelf.strategy_basic_input import StrategyBasicInput
from solie.shelf.strategy_develop_input import StrategyDevelopInput


class Strategiest:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = user_settings.get_app_settings()["datapath"] + "/strategist"
        os.makedirs(self.workerpath, exist_ok=True)

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        self.strategies = []
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

    async def load(self, *args, **kwargs):
        # custom strategies
        try:
            filepath = self.workerpath + "/strategies.json"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                content = await file.read()
                self.strategies = json.loads(content)
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
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy["indicators_script"] = read_data
            filepath = "./static/sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy["decision_script"] = read_data
            self.strategies = [first_strategy]

    async def save_strategies(self, *args, **kwargs):
        filepath = self.workerpath + "/strategies.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            content = json.dumps(self.strategies, indent=4)
            await file.write(content)

    async def display_strategies(self, *args, **kwargs):
        solie.window.comboBox_2.clear()
        solie.window.comboBox.clear()
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
            else:
                raise ValueError("Invalid risk level for drawing an icon")
            text = f"{strategy['code_name']} {strategy['version']}"
            text += f" - {strategy['readable_name']}"
            traffic_light_icon = QtGui.QIcon()
            traffic_light_icon.addPixmap(icon_pixmap)

            solie.window.comboBox_2.addItem(traffic_light_icon, text)
            solie.window.comboBox.addItem(traffic_light_icon, text)

            strategy_card = QtWidgets.QGroupBox()
            solie.window.verticalLayout_16.addWidget(strategy_card)
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

            async def job_bs(strategy=strategy):
                before_selections = await self.remember_strategy_selections()
                formation = [
                    "Develop your strategy",
                    StrategyDevelopInput,
                    True,
                    strategy,
                ]
                await solie.window.overlap(formation)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections(before_selections))

            edit_button = QtWidgets.QPushButton("Develop")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_bs)

            async def job_eb(strategy=strategy):
                before_selections = await self.remember_strategy_selections()
                formation = [
                    "Edit your strategy's basic information",
                    StrategyBasicInput,
                    True,
                    strategy,
                ]
                await solie.window.overlap(formation)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections(before_selections))

            edit_button = QtWidgets.QPushButton("Edit basic info")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_eb)

            async def job_rs(strategy=strategy):
                question = [
                    "Remove this strategy?",
                    "Once you remove this, it cannot be recovered.",
                    ["Remove"],
                ]
                answer = await solie.window.ask(question)
                if answer == 0:
                    return
                before_selections = await self.remember_strategy_selections()
                self.strategies.remove(strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections(before_selections))

            edit_button = QtWidgets.QPushButton("Remove")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_rs)

            async def job_ss(strategy=strategy):
                before_selections = await self.remember_strategy_selections()
                original_index = self.strategies.index(strategy)
                after_index = original_index + 1
                self.strategies.pop(original_index)
                self.strategies.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections(before_selections))

            edit_button = QtWidgets.QPushButton("▼")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_ss)

            async def job_us(strategy=strategy):
                before_selections = await self.remember_strategy_selections()
                original_index = self.strategies.index(strategy)
                after_index = original_index - 1
                self.strategies.pop(original_index)
                self.strategies.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections(before_selections))

            edit_button = QtWidgets.QPushButton("▲")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_us)

    async def add_blank_strategy(self, *args, **kwargs):
        new_strategy = standardize.strategy()
        self.strategies.append(new_strategy)
        await self.display_strategies()

    async def remember_strategy_selections(self, *args, **kwargs):
        before_selections = {}
        before_index = solie.window.comboBox_2.currentIndex()
        before_selections["transactor"] = self.strategies[before_index]
        before_index = solie.window.comboBox.currentIndex()
        before_selections["simulator"] = self.strategies[before_index]
        return before_selections

    async def restore_strategy_selections(self, *args, **kwargs):
        before_selections = args[0]
        if before_selections["transactor"] in self.strategies:
            new_index = self.strategies.index(before_selections["transactor"])
            solie.window.comboBox_2.setCurrentIndex(new_index)
        if before_selections["simulator"] in self.strategies:
            new_index = self.strategies.index(before_selections["simulator"])
            solie.window.comboBox.setCurrentIndex(new_index)
