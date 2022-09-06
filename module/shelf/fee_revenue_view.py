from datetime import datetime, timezone, timedelta

from PySide6 import QtWidgets, QtCore, QtGui

from module.instrument.api_requester import ApiRequester
from module.widget.horizontal_divider import HorizontalDivider


class FeeRevenueView(QtWidgets.QWidget):
    def __init__(self, done_event, payload):
        # ■■■■■ the basic ■■■■■

        super().__init__()

        # ■■■■■ prepare things ■■■■■

        device_identifier = payload
        api_requester = ApiRequester()
        payload = {
            "solsolPasscode": "SBJyXScaIEIteBPcqpMTMAG3T6B75rb4",
            "deviceIdentifier": device_identifier,
        }
        response = api_requester.cunarist(
            http_method="GET",
            path="/api/solsol/automated-revenue",
            payload=payload,
        )
        doc_items = response
        doc_items = sorted(doc_items, key=lambda d: d["weekNumber"], reverse=True)

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

        # ■■■■■ card ■■■■■

        # card structure
        card = QtWidgets.QGroupBox()
        card.setFixedWidth(720)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(80, 40, 80, 40)
        cards_layout.addWidget(card)

        # explanation
        text = "Guide to fees"
        detail_text = QtWidgets.QLabel(
            text,
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

        # explanation
        text = (
            "In short, 20% of the total automated revenue gets paid as fees every"
            " week. 10% of the automated revenue goes to the strategy creator and"
            " another 10% goes to Cunarist each week. If the automated revenue is below"
            " zero or is too little, the amount of fee for that week is $0. Effect of"
            " discount code is not shown in these values, though it still works as it"
            " should when fees actually get paid."
        )
        detail_text = QtWidgets.QLabel(
            text,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # ■■■■■ cards ■■■■■

        for doc_item in doc_items:
            # card structure
            card = QtWidgets.QGroupBox()
            card.setFixedWidth(720)
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(80, 40, 80, 40)
            cards_layout.addWidget(card)

            # explanation
            week_number = doc_item["weekNumber"]
            timestamp = (week_number * 7 + 4) * 24 * 60 * 60
            week_start = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            week_end = week_start + timedelta(days=7)
            week_start_text = week_start.strftime("%Y-%m-%d %H:%M:%S")
            week_end_text = week_end.strftime("%Y-%m-%d %H:%M:%S")
            text = f"UTC±0 {week_start_text} ~ {week_end_text} (Week {week_number})"
            detail_text = QtWidgets.QLabel(
                text,
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

            # explanation
            text = ""
            text += "Fee paid" if doc_item["isFeePaid"] else "Fee not paid"
            text += "\n"
            text += f"Sum of automated revenue: ${doc_item['sumRevenue']:.4f}"
            text += "\n"
            app_fee = doc_item["appFee"]
            app_fee = 0 if app_fee < 10 else app_fee
            text += f"App fee: ${app_fee:.4f}"
            for address, fee in doc_item["strategyFee"].items():
                fee = 0 if fee < 10 else fee
                text += "\n"
                text += f"Fee for BUSD(BSC) wallet {address}: ${fee:.4f}"
            detail_text = QtWidgets.QLabel(text)
            detail_text.setWordWrap(True)
            card_layout.addWidget(detail_text)

        # ■■■■■ spacing ■■■■■

        # spacing
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
