from datetime import datetime, timezone

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
            "appPasscode": "SBJyXScaIEIteBPcqpMTMAG3T6B75rb4",
            "deviceIdentifier": device_identifier,
        }
        response = api_requester.cunarist(
            http_method="GET",
            path="/api/solsol/automated-revenue",
            payload=payload,
        )
        about_automated_revenues = response
        about_automated_revenues = sorted(
            about_automated_revenues,
            key=lambda d: d["cycleNumber"],
            reverse=True,
        )

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
            "In short, 20% of the total automated revenue gets paid as fees every first"
            " day of the month. 10% of the automated revenue goes to the strategy"
            " creator and another 10% goes to Cunarist each month. If the automated"
            " revenue is below zero or is too little, the amount of fee for that month"
            " is $0. Effect of your discount code is already applied in these values."
        )
        detail_text = QtWidgets.QLabel(
            text,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # ■■■■■ cards ■■■■■

        for about_automated_revenue in about_automated_revenues:
            # card structure
            card = QtWidgets.QGroupBox()
            card.setFixedWidth(720)
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(80, 40, 80, 40)
            cards_layout.addWidget(card)

            # explanation
            cycle_number = about_automated_revenue["cycleNumber"]
            quotient, remainder = divmod(cycle_number - 1, 12)
            cycle_year = quotient + 1970
            cycle_month = remainder + 1
            cycle_start = datetime(
                year=cycle_year,
                month=cycle_month,
                day=1,
                tzinfo=timezone.utc,
            )
            next_cycle_number = cycle_number + 1
            quotient, remainder = divmod(next_cycle_number - 1, 12)
            next_cycle_year = quotient + 1970
            next_cycle_month = remainder + 1
            cycle_end = datetime(
                year=next_cycle_year,
                month=next_cycle_month,
                day=1,
                tzinfo=timezone.utc,
            )
            cycle_start_text = cycle_start.strftime("%Y-%m-%d %H:%M:%S")
            cycle_end_text = cycle_end.strftime("%Y-%m-%d %H:%M:%S")
            text = (
                f"UTC {cycle_start_text} ~ {cycle_end_text} (Fee cycle {cycle_number})"
            )
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
            is_fee_paid = about_automated_revenue["isFeePaid"]
            text += "Fee paid" if is_fee_paid else "Fee not paid"
            text += "\n"
            sum_revenue = about_automated_revenue["sumRevenue"]
            text += f"Sum of automated revenue: ${sum_revenue:.4f}"
            text += "\n"
            app_fee = about_automated_revenue["appFee"]
            text += f"App fee: ${app_fee:.4f}"
            for address, fee in about_automated_revenue["strategyFee"].items():
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
