import aiofiles
import aiofiles.os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
)

from solie.common import PACKAGE_PATH, outsource, spawn
from solie.overlay import StrategyBasicInput, StrategyDevelopInput
from solie.utility import (
    RiskLevel,
    SavedStrategies,
    SavedStrategy,
    Strategy,
    create_strategy_code_name,
)
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

        self.saved_strategies: SavedStrategies
        self.strategies: list[Strategy] = []
        self.strategy_cards: list[QGroupBox] = []

        self.before_selections: dict[str, Strategy] = {}

        iconpath = PACKAGE_PATH / "static" / "icon"
        self.red_pixmap = QPixmap()
        self.red_pixmap.load(str(iconpath / "traffic_light_red.png"))
        self.yellow_pixmap = QPixmap()
        self.yellow_pixmap.load(str(iconpath / "traffic_light_yellow.png"))
        self.green_pixmap = QPixmap()
        self.green_pixmap.load(str(iconpath / "traffic_light_green.png"))

        # ■■■■■ repetitive schedules ■■■■■

        # ■■■■■ websocket streamings ■■■■■

        # ■■■■■ invoked by the internet connection status change ■■■■■

        # ■■■■■ connect UI events ■■■■■

        job = self.add_blank_strategy
        outsource(window.pushButton_5.clicked, job)

    async def load(self):
        await aiofiles.os.makedirs(self.workerpath, exist_ok=True)

        filepath = self.workerpath / "soft_strategies.json"
        if await aiofiles.os.path.isfile(filepath):
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                self.saved_strategies = SavedStrategies.model_validate_json(
                    await file.read()
                )
        else:
            first_strategy = SavedStrategy(
                code_name="SLIESS",
                readable_name="Sample Strategy",
                description="Not for real investment."
                + " This strategy is only for demonstration purposes.",
            )
            filepath = PACKAGE_PATH / "static" / "sample_indicator_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy.indicator_script = read_data
            filepath = PACKAGE_PATH / "static" / "sample_decision_script.txt"
            async with aiofiles.open(filepath, "r", encoding="utf8") as file:
                read_data = await file.read()
                first_strategy.decision_script = read_data
            self.saved_strategies = SavedStrategies(all=[first_strategy])

        self._combine_strategies()

    def _combine_strategies(self):
        soft_strategies = list[Strategy](self.saved_strategies.all)
        fixed_strategies = self.window.config.get_strategies()
        self.strategies = fixed_strategies + soft_strategies

    async def save_strategies(self):
        filepath = self.workerpath / "soft_strategies.json"
        async with aiofiles.open(filepath, "w", encoding="utf8") as file:
            await file.write(self.saved_strategies.model_dump_json(indent=2))

    async def display_strategies(self):
        self.window.comboBox_2.clear()
        self.window.comboBox.clear()
        for strategy_card in self.strategy_cards:
            strategy_card.setParent(None)
        self.strategy_cards = []

        # Update strategy list view.
        for strategy in self.strategies:
            if strategy.risk_level == RiskLevel.HIGH:
                icon_pixmap = self.red_pixmap
            elif strategy.risk_level == RiskLevel.MIDDLE:
                icon_pixmap = self.yellow_pixmap
            elif strategy.risk_level == RiskLevel.LOW:
                icon_pixmap = self.green_pixmap
            else:
                raise ValueError("Invalid risk level for drawing an icon")
            traffic_light_icon = QIcon()
            traffic_light_icon.addPixmap(icon_pixmap)

            text = f"{strategy.code_name} {strategy.version} - {strategy.readable_name}"

            self.window.comboBox_2.addItem(traffic_light_icon, text)
            self.window.comboBox.addItem(traffic_light_icon, text)

            strategy_card = QGroupBox()
            self.window.verticalLayout_16.addWidget(strategy_card)
            self.strategy_cards.append(strategy_card)
            card_layout = QHBoxLayout(strategy_card)

            icon_label = QLabel("")
            card_layout.addWidget(icon_label)
            icon_label.setPixmap(icon_pixmap)
            icon_label.setScaledContents(True)
            icon_label.setFixedSize(16, 16)

            text_label = QLabel(text)
            card_layout.addWidget(text_label)

            spacer = QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
            card_layout.addItem(spacer)

            # Allow editing only when this is not a fixed strategy.
            if not isinstance(strategy, SavedStrategy):
                fixed_button = QPushButton("Fixed")
                fixed_button.setEnabled(False)
                card_layout.addWidget(fixed_button)
                continue

            async def job_bs(strategy=strategy):
                await self.remember_strategy_selections()
                await overlay(
                    "Develop your strategy",
                    StrategyDevelopInput(strategy),
                )
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            edit_button = QPushButton("Develop")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_bs)

            async def job_eb(strategy=strategy):
                await self.remember_strategy_selections()
                await overlay(
                    "Edit your strategy's basic information",
                    StrategyBasicInput(strategy),
                )
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            edit_button = QPushButton("Edit basic info")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_eb)

            action_menu = QMenu(self.window)
            action_button = QPushButton()
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
                self.saved_strategies.all.remove(strategy)
                self._combine_strategies()
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            new_action = action_menu.addAction("Remove")
            outsource(new_action.triggered, job_rs)

            async def job_dp(strategy=strategy):
                await self.remember_strategy_selections()
                duplicated = strategy.model_copy(deep=True)
                duplicated.code_name = create_strategy_code_name()
                self.saved_strategies.all.append(duplicated)
                self._combine_strategies()
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            new_action = action_menu.addAction("Duplicate")
            outsource(new_action.triggered, job_dp)

            async def job_ss(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.saved_strategies.all.index(strategy)
                after_index = original_index + 1
                self.saved_strategies.all.pop(original_index)
                self.saved_strategies.all.insert(after_index, strategy)
                self._combine_strategies()
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            edit_button = QPushButton("▼")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_ss)

            async def job_us(strategy=strategy):
                await self.remember_strategy_selections()
                original_index = self.saved_strategies.all.index(strategy)
                after_index = original_index - 1
                self.saved_strategies.all.pop(original_index)
                self.saved_strategies.all.insert(after_index, strategy)
                self._combine_strategies()
                spawn(self.display_strategies())
                spawn(self.save_strategies())
                spawn(self.restore_strategy_selections())

            edit_button = QPushButton("▲")
            card_layout.addWidget(edit_button)
            outsource(edit_button.clicked, job_us)

    async def add_blank_strategy(self):
        await self.remember_strategy_selections()
        new_strategy = SavedStrategy(code_name=create_strategy_code_name())
        self.saved_strategies.all.append(new_strategy)
        self._combine_strategies()
        await self.display_strategies()
        await self.restore_strategy_selections()

    async def remember_strategy_selections(self):
        before_index = self.window.comboBox_2.currentIndex()
        self.before_selections["transactor"] = self.strategies[before_index]
        before_index = self.window.comboBox.currentIndex()
        self.before_selections["simulator"] = self.strategies[before_index]

    async def restore_strategy_selections(self):
        if self.before_selections["transactor"] in self.strategies:
            new_index = self.strategies.index(self.before_selections["transactor"])
            self.window.comboBox_2.setCurrentIndex(new_index)
        if self.before_selections["simulator"] in self.strategies:
            new_index = self.strategies.index(self.before_selections["simulator"])
            self.window.comboBox.setCurrentIndex(new_index)
