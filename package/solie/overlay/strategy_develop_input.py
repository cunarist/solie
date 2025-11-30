"""Strategy development overlay."""

import webbrowser
from asyncio import Event

import aiofiles
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from solie.common import PACKAGE_PATH, outsource, spawn_blocking
from solie.utility import EXIT_DIALOG_ANSWER, Implements, SavedStrategy
from solie.widget import OverlayContent, ScriptEditor, VerticalDivider, ask

lambda: Implements[OverlayContent](StrategyDevelopInput)


class StrategyDevelopInput:
    """Overlay for developing trading strategies."""

    title = "Develop your strategy"
    close_button = True
    done_event = Event()

    def __init__(self, strategy: SavedStrategy) -> None:
        """Initialize strategy development input overlay."""
        super().__init__()
        self.widget = QWidget()
        self.strategy = strategy
        self.result = None

        # Create main layout
        full_layout = QVBoxLayout(self.widget)

        # Create script editors
        this_layout = QHBoxLayout()
        full_layout.addLayout(this_layout)

        self.indicator_script_input = self._create_script_editor(
            this_layout,
            "Indicator script",
            strategy.indicator_script,
        )
        self.decision_script_input = self._create_script_editor(
            this_layout,
            "Decision script",
            strategy.decision_script,
        )

        # Create button card
        self._create_button_card(full_layout)

    def _create_script_editor(
        self,
        parent_layout: QHBoxLayout,
        title: str,
        content: str,
    ) -> ScriptEditor:
        """Create a script editor column."""
        column_layout = QVBoxLayout()
        parent_layout.addLayout(column_layout)

        detail_text = QLabel()
        detail_text.setText(title)
        detail_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column_layout.addWidget(detail_text)

        script_input = ScriptEditor(self.widget)
        script_input.setPlainText(content)
        column_layout.addWidget(script_input)

        return script_input

    def _create_button_card(self, parent_layout: QVBoxLayout) -> None:
        """Create button card with save and action buttons."""
        card = QGroupBox()
        card_layout = QHBoxLayout(card)
        parent_layout.addWidget(card)

        # Left spacer
        self._add_horizontal_spacer(card_layout)

        # Save button
        self._add_save_button(card, card_layout)

        # Divider
        divider = VerticalDivider(self.widget)
        card_layout.addWidget(divider)

        # Action menu
        self._add_action_menu(card_layout)

        # Right spacer
        self._add_horizontal_spacer(card_layout)

    def _add_horizontal_spacer(self, layout: QHBoxLayout) -> None:
        """Add horizontal expanding spacer."""
        spacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        layout.addItem(spacer)

    def _add_save_button(self, card: QGroupBox, layout: QHBoxLayout) -> None:
        """Add save and close button."""

        async def job_ss() -> None:
            self.strategy.indicator_script = self.indicator_script_input.toPlainText()
            self.strategy.decision_script = self.decision_script_input.toPlainText()
            self.done_event.set()

        button = QPushButton("Save and close", card)
        outsource(button.clicked, job_ss)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(button)

    def _add_action_menu(self, layout: QHBoxLayout) -> None:
        """Add action menu with documentation links and sample scripts."""
        action_menu = QMenu(self.widget)
        action_button = QPushButton()
        action_button.setText("☰")
        action_button.setMenu(action_menu)
        layout.addWidget(action_button)

        # Apply sample scripts action
        async def job_as() -> None:
            await self._apply_sample_scripts()

        new_action = action_menu.addAction("Apply sample scripts")
        outsource(new_action.triggered, job_as)

        # Documentation links
        self._add_doc_links(action_menu)

    async def _apply_sample_scripts(self) -> None:
        """Load and apply sample scripts."""
        filepath = PACKAGE_PATH / "static" / "sample_indicator_script.txt"
        async with aiofiles.open(filepath, encoding="utf8") as file:
            script = await file.read()
        self.indicator_script_input.setPlainText(script)

        filepath = PACKAGE_PATH / "static" / "sample_decision_script.txt"
        async with aiofiles.open(filepath, encoding="utf8") as file:
            script = await file.read()
        self.decision_script_input.setPlainText(script)

        await ask(
            "Sample scripts applied",
            "It hasn't been saved yet, feel free to customize the code to your liking.",
            ["Okay"],
        )

    def _add_doc_links(self, menu: QMenu) -> None:
        """Add documentation link actions to menu."""
        docs = [
            ("Show Solie API docs", "https://solie-docs.cunarist.com/making-strategy/"),
            (
                "Show Pandas API docs",
                "https://pandas.pydata.org/docs/reference/index.html",
            ),
            (
                "Show TA API docs",
                "https://github.com/twopirllc/pandas-ta#indicators-by-category",
            ),
        ]

        for title, url in docs:

            async def job_open(url: str = url) -> None:
                await spawn_blocking(webbrowser.open, url)

            new_action = menu.addAction(title)
            outsource(new_action.triggered, job_open)

    async def confirm_closing(self) -> bool:
        """Confirm if strategy can be closed, saving if modified."""
        strategy = self.strategy

        written_decision = self.decision_script_input.toPlainText()
        is_decision_script_saved = written_decision == strategy.decision_script
        written_indicators = self.indicator_script_input.toPlainText()
        is_indicator_script_saved = written_indicators == strategy.indicator_script
        if is_decision_script_saved and is_indicator_script_saved:
            return True

        should_close = False
        answer = await ask(
            "Scripts are not saved yet",
            "Are you sure you want to exit the editor without saving?",
            ["Cancel", "Exit"],
        )
        if answer == EXIT_DIALOG_ANSWER:
            should_close = True

        return should_close
