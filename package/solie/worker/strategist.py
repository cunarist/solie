import asyncio
from dataclasses import replace

import aiofiles
import aiofiles.os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6 import QtGui, QtWidgets

from solie.common import PACKAGE_PATH, outsource
from solie.overlay import StrategyBasicInput, StrategyDevelopInput
from solie.utility import Strategies, Strategy, create_strategy_code_name
from solie.widget import ask, overlay
from solie.window import Window


class Strategiest:
    def __init__(self, window: Window, scheduler: AsyncIOScheduler):
        # ■■■■■ for data management ■■■■■

        self.window = window
        self.scheduler = scheduler
        self.workerpath = window.datapath / "strategist"

        # ■■■■■ internal memory ■■■■■

        # ■■■■■ remember and display ■■■■■

        self.strategies: Strategies
        self.strategy_cards: list[QtWidgets.QGroupBox] = []

        self.before_selections = {}

        iconpath = PACKAGE_PATH / "static" / "icon"
        self.red_pixmap = QtGui.QPixmap()
        self.red_pixmap.load(str(iconpath / "traffic_light_red.png"))
        self.yellow_pixmap = QtGui.QPixmap()
        self.yellow_pixmap.load(str(iconpath / "traffic_light_yellow.png"))
        self.green_pixmap = QtGui.QPixmap()
        self.green_pixmap.load(str(iconpath / "traffic_light_green.png"))

        # ■■■■■ repetitive schedules ■■■■■

        # ■■■■■ websocket streamings ■■■■■

        self.api_streamers = {}

        # ■■■■■ invoked by the internet connection status change ■■■■■

        # ■■■■■ connect UI events ■■■■■

        job = self.add_blank_strategy
        outsource(window.pushButton_5.clicked, job)

    async def load(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        filepath = self.workerpath / "strategies.json"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                self.strategies = Strategies.from_json(await file.read())
        else:
            first_strategy = Strategy(
                code_name="SLIESS",
                readable_name="Sample Strategy",
                description="Not for real investment."
                + " This strategy is only for demonstration purposes.",
            )
            filepath = PACKAGE_PATH / "static" / "sample_indicators_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy.indicators_script = read_data
            filepath = PACKAGE_PATH / "static" / "sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy.decision_script = read_data
            self.strategies = Strategies(all=[first_strategy])

    async def save_strategies(self):
        filepath = self.workerpath / "strategies.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(self.strategies.to_json(indent=2))

    async def display_strategies(self):
        self.window.comboBox_2.clear()
        self.window.comboBox.clear()
        for strategy_card in self.strategy_cards:
            strategy_card.setParent(None)
        self.strategy_cards = []

        for strategy in self.strategies.all:
            if strategy.risk_level == 2:
                icon_pixmap = self.red_pixmap
            elif strategy.risk_level == 1:
                icon_pixmap = self.yellow_pixmap
            elif strategy.risk_level == 0:
                icon_pixmap = self.green_pixmap
            else:
                raise ValueError("Invalid risk level for drawing an icon")
            text = f"{strategy.code_name} {strategy.version} - {strategy.readable_name}"
            traffic_light_icon = QtGui.QIcon()
            traffic_light_icon.addPixmap(icon_pixmap)

            self.window.comboBox_2.addItem(traffic_light_icon, text)
            self.window.comboBox.addItem(traffic_light_icon, text)

            strategy_card = QtWidgets.QGroupBox()
            self.window.verticalLayout_16.addWidget(strategy_card)
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
                await overlay(
                    "Develop your strategy",
                    StrategyDevelopInput(strategy),
                )
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("Develop")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_bs)

            async def job_eb(strategy=strategy):
                await self.remember_strategy_selections()
                await overlay(
                    "Edit your strategy's basic information",
                    StrategyBasicInput(strategy),
                )
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("Edit basic info")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_eb)

            action_menu = QtWidgets.QMenu(self.window)
            action_button = QtWidgets.QPushButton()
            action_button.setText("☰")
            action_button.setMenu(action_menu)
            card_layout.addWidget(action_button)

            async def job_rs(strategy=strategy):
                answer = await ask(
                    "Remove this strategy?",
                    "Once you remove this, it cannot be recovered.",
                    ["Remove"],
                )
                if answer == 0:
                    return
                await self.remember_strategy_selections()
                self.strategies.all.remove(strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            new_action = action_menu.addAction("Remove")
            outsource(new_action.triggered, job_rs)

            async def job_dp(strategy=strategy):
                await self.remember_strategy_selections()
                duplicated = replace(
                    strategy,
                    code_name=create_strategy_code_name(),
                )
                self.strategies.all.append(duplicated)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            new_action = action_menu.addAction("Duplicate")
            outsource(new_action.triggered, job_dp)

            async def job_ss(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.strategies.all.index(strategy)
                after_index = original_index + 1
                self.strategies.all.pop(original_index)
                self.strategies.all.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("▼")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_ss)

            async def job_us(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.strategies.all.index(strategy)
                after_index = original_index - 1
                self.strategies.all.pop(original_index)
                self.strategies.all.insert(after_index, strategy)
                asyncio.create_task(self.display_strategies())
                asyncio.create_task(self.save_strategies())
                asyncio.create_task(self.restore_strategy_selections())

            edit_button = QtWidgets.QPushButton("▲")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_us)

    async def add_blank_strategy(self):
        await self.remember_strategy_selections()
        new_strategy = Strategy(code_name=create_strategy_code_name())
        self.strategies.all.append(new_strategy)
        await self.display_strategies()
        await self.restore_strategy_selections()

    async def remember_strategy_selections(self):
        before_index = self.window.comboBox_2.currentIndex()
        self.before_selections["transactor"] = self.strategies.all[before_index]
        before_index = self.window.comboBox.currentIndex()
        self.before_selections["simulator"] = self.strategies.all[before_index]

    async def restore_strategy_selections(self):
        if self.before_selections["transactor"] in self.strategies.all:
            new_index = self.strategies.all.index(self.before_selections["transactor"])
            self.window.comboBox_2.setCurrentIndex(new_index)
        if self.before_selections["simulator"] in self.strategies.all:
            new_index = self.strategies.all.index(self.before_selections["simulator"])
            self.window.comboBox.setCurrentIndex(new_index)
