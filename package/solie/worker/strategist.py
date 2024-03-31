import asyncio
import json

import aiofiles
import aiofiles.os
from PySide6 import QtGui, QtWidgets

import solie
from solie.overlay.strategy_basic_input import StrategyBasicInput
from solie.overlay.strategy_develop_input import StrategyDevelopInput
from solie.utility import outsource, standardize


class Strategiest:
    def __init__(self):
        # ■■■■■ for data management ■■■■■

        self.workerpath = solie.window.datapath / "strategist"

        # ■■■■■ worker secret memory ■■■■■

        self.secret_memory = {}

        # ■■■■■ remember and display ■■■■■

        self.strategies = []
        self.strategy_cards: list[QtWidgets.QGroupBox] = []

        self.before_selections = {}

        iconpath = solie.info.PATH / "static" / "icon"
        self.red_pixmap = QtGui.QPixmap()
        self.red_pixmap.load(str(iconpath / "traffic_light_red.png"))
        self.yellow_pixmap = QtGui.QPixmap()
        self.yellow_pixmap.load(str(iconpath / "traffic_light_yellow.png"))
        self.green_pixmap = QtGui.QPixmap()
        self.green_pixmap.load(str(iconpath / "traffic_light_green.png"))

        # ■■■■■ repetitive schedules ■■■■■

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = {}

        # ■■■■■ invoked by the internet connection status change  ■■■■■

    async def load(self, *args, **kwargs):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        # custom strategies
        try:
            filepath = self.workerpath / "strategies.json"
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
            filepath = solie.info.PATH / "static" / "sample_indicators_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy["indicators_script"] = read_data
            filepath = solie.info.PATH / "static" / "sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy["decision_script"] = read_data
            self.strategies = [first_strategy]

    async def save_strategies(self, *args, **kwargs):
        filepath = self.workerpath / "strategies.json"
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
                await self.remember_strategy_selections()
                await solie.window.overlay(
                    "Develop your strategy",
                    StrategyDevelopInput(strategy),
                )
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("Develop")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_bs)

            async def job_eb(strategy=strategy):
                await self.remember_strategy_selections()
                await solie.window.overlay(
                    "Edit your strategy's basic information",
                    StrategyBasicInput(strategy),
                )
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("Edit basic info")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_eb)

            action_menu = QtWidgets.QMenu(solie.window)
            action_button = QtWidgets.QPushButton()
            action_button.setText("☰")
            action_button.setMenu(action_menu)
            card_layout.addWidget(action_button)

            async def job_rs(strategy=strategy):
                answer = await solie.window.ask(
                    "Remove this strategy?",
                    "Once you remove this, it cannot be recovered.",
                    ["Remove"],
                )
                if answer == 0:
                    return
                await self.remember_strategy_selections()
                self.strategies.remove(strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            new_action = action_menu.addAction("Remove")
            outsource.do(new_action.triggered, job_rs)

            async def job_dp(strategy=strategy):
                await self.remember_strategy_selections()
                duplicated = strategy.copy()
                duplicated["code_name"] = standardize.create_strategy_code_name()
                self.strategies.append(duplicated)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            new_action = action_menu.addAction("Duplicate")
            outsource.do(new_action.triggered, job_dp)

            async def job_ss(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.strategies.index(strategy)
                after_index = original_index + 1
                self.strategies.pop(original_index)
                self.strategies.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("▼")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_ss)

            async def job_us(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.strategies.index(strategy)
                after_index = original_index - 1
                self.strategies.pop(original_index)
                self.strategies.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("▲")
            card_layout.addWidget(edit_button)
            outsource.do(edit_button.clicked, job_us)

    async def add_blank_strategy(self, *args, **kwargs):
        await self.remember_strategy_selections()
        new_strategy = standardize.strategy()
        self.strategies.append(new_strategy)
        await self.display_strategies()
        await self.restore_strategy_selections()

    async def remember_strategy_selections(self, *args, **kwargs):
        before_index = solie.window.comboBox_2.currentIndex()
        self.before_selections["transactor"] = self.strategies[before_index]
        before_index = solie.window.comboBox.currentIndex()
        self.before_selections["simulator"] = self.strategies[before_index]

    async def restore_strategy_selections(self, *args, **kwargs):
        if self.before_selections["transactor"] in self.strategies:
            new_index = self.strategies.index(self.before_selections["transactor"])
            solie.window.comboBox_2.setCurrentIndex(new_index)
        if self.before_selections["simulator"] in self.strategies:
            new_index = self.strategies.index(self.before_selections["simulator"])
            solie.window.comboBox.setCurrentIndex(new_index)
