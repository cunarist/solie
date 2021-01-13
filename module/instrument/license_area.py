import threading
import getmac

from PyQt6 import QtWidgets, QtCore, QtGui

from instrument.api_requester import ApiRequester
from instrument.api_request_error import ApiRequestError
from recipe import standardize
from recipe import outsource


class LicenseArea(QtWidgets.QScrollArea):

    done_event = threading.Event()

    def __init__(self, root):

        # ■■■■■ 기본 ■■■■■

        super().__init__()

        # ■■■■■ 데이터 요청 준비 ■■■■■

        api_requester = ApiRequester()

        # ■■■■■ 전체 형태 ■■■■■

        self.setWidgetResizable(True)
        self.setStyleSheet(
            """
            #card {
                width: 36em;
                max-width: 36em;
                padding: 2em;
            }
            """
        )

        # ■■■■■ 큰 틀 ■■■■■

        full_widget = QtWidgets.QWidget()
        self.setWidget(full_widget)
        full_layout = QtWidgets.QHBoxLayout(full_widget)
        cards_layout = QtWidgets.QVBoxLayout()
        full_layout.addLayout(cards_layout)

        # ■■■■■ 상단 여백 ■■■■■

        # 확장기
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)

        # ■■■■■ 카드 ■■■■■

        # 카드 구조
        card = QtWidgets.QGroupBox(objectName="card")
        card.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout = QtWidgets.QVBoxLayout(card)
        cards_layout.addWidget(card)

        # 확장기
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        card_layout.addItem(spacer)

        # 제목
        main_text = QtWidgets.QLabel(
            "쏠쏠 라이센스 키를 입력하세요.",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        main_text_font = QtGui.QFont()
        main_text_font.setPointSize(12)
        main_text.setFont(main_text_font)
        main_text.setWordWrap(True)
        card_layout.addWidget(main_text)

        # 여백
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # 설명
        detail_text = QtWidgets.QLabel(
            "정확히 입력해야 합니다.",
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        detail_text.setWordWrap(True)
        card_layout.addWidget(detail_text)

        # 여백
        spacing_text = QtWidgets.QLabel("")
        spacing_text_font = QtGui.QFont()
        spacing_text_font.setPointSize(3)
        spacing_text.setFont(spacing_text_font)
        card_layout.addWidget(spacing_text)

        # 입력
        this_layout = QtWidgets.QHBoxLayout()
        card_layout.addLayout(this_layout)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(spacer)
        key_input = QtWidgets.QLineEdit()
        key_input.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        key_input.setStyleSheet("width: 18em;")
        key_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        this_layout.addWidget(key_input)
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Minimum,
        )
        this_layout.addItem(spacer)

        # 확장기
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        card_layout.addItem(spacer)

        # ■■■■■ 카드 ■■■■■

        # 라이센스 키 확인 함수
        def job(*args):
            widget = key_input
            license_key = root.undertake(lambda w=widget: w.text(), True)
            try:
                payload = {
                    "licenseKey": license_key,
                    "macAddress": getmac.get_mac_address(),
                }
                api_requester.cunarist("PUT", "/solsol/key-mac-pair", payload)
                standardize.set_license_key(license_key)
                self.done_event.set()
            except ApiRequestError:
                question = [
                    "유효한 라이센스 키가 아닙니다.",
                    "정확한 라이센스 키를 입력해야 합니다.",
                    ["확인"],
                ]
                root.ask(question)

        # 카드 구조
        card = QtWidgets.QGroupBox(objectName="card")
        card.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout = QtWidgets.QHBoxLayout(card)
        cards_layout.addWidget(card)

        # 확인 버튼
        confirm_button = QtWidgets.QPushButton("확인", card)
        outsource.do(confirm_button.clicked, job)
        confirm_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(confirm_button)

        # ■■■■■ 하단 여백 ■■■■■

        # 확장기
        spacer = QtWidgets.QSpacerItem(
            0,
            0,
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        cards_layout.addItem(spacer)
