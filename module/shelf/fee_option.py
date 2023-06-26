from datetime import datetime, timezone

from PySide6 import QtWidgets, QtCore, QtGui

from module.instrument.api_requester import ApiRequester
from module.widget.horizontal_divider import HorizontalDivider


class FeeOption(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare things ■■■■■

        fee_settings = payload
        api_requester = ApiRequester()
        discount_code = fee_settings["discount_code"]

        # ■■■■■ full layout ■■■■■

        full_layout = QtWidgets.QHBoxLayout(self)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ spacing ■■■■■

        # spacing
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
        detail_text = QtWidgets.QLabel(
            "Discount code",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # divider
        divider = HorizontalDivider(self)
        card_layout.addWidget(divider)

        # spacing
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # discount code input
        this_layout = QtWidgets.QHBoxLayout()
        card_layout.addLayout(this_layout)
        discount_code_input = QtWidgets.QLineEdit()
        discount_code_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        discount_code_input.setFixedWidth(360)
        discount_code_input.setText(discount_code)
        this_layout.addWidget(discount_code_input)

        # rate text
        rate_label = QtWidgets.QLabel(
            "",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        rate_label.setWordWrap(True)
        card_layout.addWidget(rate_label)

        def job():
            discount_code = discount_code_input.text()
            fee_settings["discount_code"] = discount_code
            payload = {
                "discountCode": discount_code,
            }
            response = api_requester.cunarist(
                http_method="GET",
                path="/api/solie/discount-code",
                payload=payload,
            )
            discount_rate = response["discountRate"]
            expire = response["expire"]
            if expire is None:
                expire_text = "doesn't expire"
            else:
                expire_date = datetime.fromtimestamp(expire / 1000, tz=timezone.utc)
                date_text = expire_date.strftime("%Y-%m-%d %H:%M:%S")
                expire_text = f"expires at UTC {date_text}"
            text = f"Fee discount rate is {discount_rate*100:.0f}% and {expire_text}."
            rate_label.setText(text)

        job()

        # submit button
        this_layout = QtWidgets.QHBoxLayout()
        card_layout.addLayout(this_layout)
        submit_button = QtWidgets.QPushButton("Apply", card)
        submit_button.clicked.connect(job)
        submit_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        this_layout.addWidget(submit_button)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
