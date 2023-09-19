from PySide6 import QtWidgets

from module.recipe import outsource


class DownloadFillOption(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare variables ■■■■■

        answer_container = payload[0]
        fill_options = (
            "From 2020 to last year",
            "From 2020 to last year (With small daily files)",
            "From first month of this year to last month",
            "From first month of this year to last month (With small daily files)",
            "This month",
            "Yesterday and the day before yesterday",
        )

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        explain_label = QtWidgets.QLabel(
            "Solie will fill the candle data with historical data provided by"
            " Binance. The more you fill, the longer it takes. Amount of a few days"
            " only takes few minutes while amount of a few years can take hours."
        )
        explain_label.setWordWrap(True)
        card_layout.addWidget(explain_label)

        # ■■■■■ a card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # option buttons
        for turn, text in enumerate(fill_options):

            def job(turn=turn, *args, **kwargs):
                answer_container["filling_type"] = turn
                done_event.set()

            option_button = QtWidgets.QPushButton(text, card)
            outsource.do(option_button.clicked, job)
            card_layout.addWidget(option_button)

        # ■■■■■ spacing ■■■■■

        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
