# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'user_interface.ui'
##
## Created by: Qt User Interface Compiler version 6.3.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    QTime,
    QUrl,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from module.widget.gauge import Gauge
from module.widget.log_list import LogList
from module.widget.script_editor import ScriptEditor


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1280, 720)
        MainWindow.setMinimumSize(QSize(1280, 720))
        font = QFont()
        MainWindow.setFont(font)
        icon = QIcon()
        icon.addFile(
            "resource/product_icon_solsol.png", QSize(), QIcon.Normal, QIcon.Off
        )
        MainWindow.setWindowIcon(icon)
        MainWindow.setStyleSheet(
            "QPushButton, QComboBox, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox {\n"
            "	height: 1.8em;\n"
            "}\n"
            "\n"
            "QPushButton, QComboBox, QLineEdit {\n"
            "	padding-right: 0.8em;\n"
            "	padding-left: 0.8em;\n"
            "}\n"
            "\n"
            "QTabWidget::tab-bar {\n"
            "	alignment: center;\n"
            "}\n"
            "\n"
            "QProgressBar {\n"
            "	height: 0.4em;\n"
            "}\n"
            "\n"
            "QMenu {\n"
            "	padding-top: 0.6em;\n"
            "	padding-bottom: 0.6em;\n"
            "}\n"
            "\n"
            "QMenu::separator {\n"
            "   	height: 1em;\n"
            "}\n"
            "\n"
            "QSplitter::handle {\n"
            "    background-color: #FCFCFC;\n"
            "}\n"
            "\n"
            "ScriptEditor, LogList {\n"
            "    background-color: #F5F2F0;\n"
            "	border-radius: 0.2em;\n"
            "	border: 1px solid rgba(0,0,0,0.1);\n"
            "}\n"
            "\n"
            "SymbolBox {\n"
            "    min-width: 10em;\n"
            "    max-width: 10em;\n"
            "    min-height: 10em;\n"
            "    max-height: 10em;\n"
            "    background-color: #F7F7F7;\n"
            "	border: 1px solid rgba(0,0,0,0.1);\n"
            "    border-radius: 5em;\n"
            "}\n"
            "\n"
            "AskPopup {\n"
            "    background: rgba(0, 0, 0, 127);\n"
            "}\n"
            "\n"
            "AskPopupContent {\n"
            "    border: 1px solid rgba(0,0,0,0.1);\n"
            ""
            "    border-radius: 0.4em;\n"
            "    background: #F9F9F9;\n"
            "    min-width: 24em;\n"
            "    max-width: 24em;\n"
            "    min-height: 24em;\n"
            "    max-height: 24em;\n"
            "    margin: 0em;\n"
            "    padding: 2em;\n"
            "}"
        )
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayout_3 = QGridLayout(self.centralwidget)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.gauge = Gauge(self.centralwidget)
        self.gauge.setObjectName("gauge")
        self.gauge.setMinimumSize(QSize(0, 22))
        self.gauge.setMaximumSize(QSize(16777215, 22))
        self.gauge.setFlat(True)

        self.gridLayout_3.addWidget(self.gauge, 5, 0, 1, 1)

        self.board = QTabWidget(self.centralwidget)
        self.board.setObjectName("board")
        self.board.setTabPosition(QTabWidget.North)
        self.tab_5 = QWidget()
        self.tab_5.setObjectName("tab_5")
        self.verticalLayout_4 = QVBoxLayout(self.tab_5)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.verticalSpacer_3 = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.verticalLayout_4.addItem(self.verticalSpacer_3)

        self.verticalLayout_14 = QVBoxLayout()
        self.verticalLayout_14.setObjectName("verticalLayout_14")

        self.verticalLayout_4.addLayout(self.verticalLayout_14)

        self.horizontalLayout_20 = QHBoxLayout()
        self.horizontalLayout_20.setObjectName("horizontalLayout_20")

        self.verticalLayout_4.addLayout(self.horizontalLayout_20)

        self.horizontalLayout_17 = QHBoxLayout()
        self.horizontalLayout_17.setObjectName("horizontalLayout_17")

        self.verticalLayout_4.addLayout(self.horizontalLayout_17)

        self.verticalSpacer_4 = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.verticalLayout_4.addItem(self.verticalSpacer_4)

        self.groupBox_10 = QGroupBox(self.tab_5)
        self.groupBox_10.setObjectName("groupBox_10")
        self.verticalLayout_12 = QVBoxLayout(self.groupBox_10)
        self.verticalLayout_12.setObjectName("verticalLayout_12")
        self.label_6 = QLabel(self.groupBox_10)
        self.label_6.setObjectName("label_6")
        self.label_6.setAlignment(Qt.AlignCenter)

        self.verticalLayout_12.addWidget(self.label_6)

        self.verticalLayout_4.addWidget(self.groupBox_10)

        self.groupBox_6 = QGroupBox(self.tab_5)
        self.groupBox_6.setObjectName("groupBox_6")
        self.verticalLayout_17 = QVBoxLayout(self.groupBox_6)
        self.verticalLayout_17.setObjectName("verticalLayout_17")
        self.horizontalLayout_24 = QHBoxLayout()
        self.horizontalLayout_24.setObjectName("horizontalLayout_24")
        self.horizontalSpacer_8 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_24.addItem(self.horizontalSpacer_8)

        self.pushButton_2 = QPushButton(self.groupBox_6)
        self.pushButton_2.setObjectName("pushButton_2")

        self.horizontalLayout_24.addWidget(self.pushButton_2)

        self.line_6 = QFrame(self.groupBox_6)
        self.line_6.setObjectName("line_6")
        self.line_6.setFrameShape(QFrame.VLine)
        self.line_6.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_24.addWidget(self.line_6)

        self.pushButton_13 = QPushButton(self.groupBox_6)
        self.pushButton_13.setObjectName("pushButton_13")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_13.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_13.setSizePolicy(sizePolicy)

        self.horizontalLayout_24.addWidget(self.pushButton_13)

        self.horizontalSpacer_9 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_24.addItem(self.horizontalSpacer_9)

        self.verticalLayout_17.addLayout(self.horizontalLayout_24)

        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName("horizontalLayout_12")
        self.progressBar_3 = QProgressBar(self.groupBox_6)
        self.progressBar_3.setObjectName("progressBar_3")
        font1 = QFont()
        font1.setPointSize(1)
        self.progressBar_3.setFont(font1)
        self.progressBar_3.setMaximum(1000)
        self.progressBar_3.setTextVisible(False)

        self.horizontalLayout_12.addWidget(self.progressBar_3)

        self.verticalLayout_17.addLayout(self.horizontalLayout_12)

        self.verticalLayout_4.addWidget(self.groupBox_6)

        self.board.addTab(self.tab_5, "")
        self.tab = QWidget()
        self.tab.setObjectName("tab")
        self.verticalLayout_3 = QVBoxLayout(self.tab)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.groupBox_2 = QGroupBox(self.tab)
        self.groupBox_2.setObjectName("groupBox_2")
        self.horizontalLayout_4 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName("label_8")
        self.label_8.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_4.addWidget(self.label_8)

        self.verticalLayout_3.addWidget(self.groupBox_2)

        self.splitter = QSplitter(self.tab)
        self.splitter.setObjectName("splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.horizontalLayoutWidget_1 = QWidget(self.splitter)
        self.horizontalLayoutWidget_1.setObjectName("horizontalLayoutWidget_1")
        self.horizontalLayout_7 = QHBoxLayout(self.horizontalLayoutWidget_1)
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_1)
        self.horizontalLayoutWidget = QWidget(self.splitter)
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout_16 = QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout_16.setObjectName("horizontalLayout_16")
        self.horizontalLayout_16.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget)
        self.horizontalLayoutWidget_5 = QWidget(self.splitter)
        self.horizontalLayoutWidget_5.setObjectName("horizontalLayoutWidget_5")
        self.horizontalLayout_28 = QHBoxLayout(self.horizontalLayoutWidget_5)
        self.horizontalLayout_28.setObjectName("horizontalLayout_28")
        self.horizontalLayout_28.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_5)
        self.horizontalLayoutWidget_3 = QWidget(self.splitter)
        self.horizontalLayoutWidget_3.setObjectName("horizontalLayoutWidget_3")
        self.horizontalLayout_29 = QHBoxLayout(self.horizontalLayoutWidget_3)
        self.horizontalLayout_29.setObjectName("horizontalLayout_29")
        self.horizontalLayout_29.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_3)

        self.verticalLayout_3.addWidget(self.splitter)

        self.groupBox = QGroupBox(self.tab)
        self.groupBox.setObjectName("groupBox")
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.label_16 = QLabel(self.groupBox)
        self.label_16.setObjectName("label_16")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_16.sizePolicy().hasHeightForWidth())
        self.label_16.setSizePolicy(sizePolicy1)
        self.label_16.setFont(font)
        self.label_16.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_3.addWidget(self.label_16)

        self.verticalLayout_3.addWidget(self.groupBox)

        self.groupBox_9 = QGroupBox(self.tab)
        self.groupBox_9.setObjectName("groupBox_9")
        self.verticalLayout_5 = QVBoxLayout(self.groupBox_9)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.horizontalLayout_15 = QHBoxLayout()
        self.horizontalLayout_15.setObjectName("horizontalLayout_15")
        self.horizontalSpacer = QSpacerItem(
            0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_15.addItem(self.horizontalSpacer)

        self.checkBox_2 = QCheckBox(self.groupBox_9)
        self.checkBox_2.setObjectName("checkBox_2")
        self.checkBox_2.setChecked(True)

        self.horizontalLayout_15.addWidget(self.checkBox_2)

        self.pushButton_14 = QPushButton(self.groupBox_9)
        self.pushButton_14.setObjectName("pushButton_14")

        self.horizontalLayout_15.addWidget(self.pushButton_14)

        self.label_2 = QLabel(self.groupBox_9)
        self.label_2.setObjectName("label_2")

        self.horizontalLayout_15.addWidget(self.label_2)

        self.comboBox_4 = QComboBox(self.groupBox_9)
        self.comboBox_4.setObjectName("comboBox_4")
        self.comboBox_4.setMinimumSize(QSize(150, 0))
        self.comboBox_4.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_15.addWidget(self.comboBox_4)

        self.line_8 = QFrame(self.groupBox_9)
        self.line_8.setObjectName("line_8")
        self.line_8.setFrameShape(QFrame.VLine)
        self.line_8.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_15.addWidget(self.line_8)

        self.label_21 = QLabel(self.groupBox_9)
        self.label_21.setObjectName("label_21")

        self.horizontalLayout_15.addWidget(self.label_21)

        self.comboBox_2 = QComboBox(self.groupBox_9)
        self.comboBox_2.setObjectName("comboBox_2")
        self.comboBox_2.setMinimumSize(QSize(380, 0))
        self.comboBox_2.setMaximumSize(QSize(380, 16777215))

        self.horizontalLayout_15.addWidget(self.comboBox_2)

        self.checkBox = QCheckBox(self.groupBox_9)
        self.checkBox.setObjectName("checkBox")
        self.checkBox.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_15.addWidget(self.checkBox)

        self.horizontalSpacer_3 = QSpacerItem(
            0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_15.addItem(self.horizontalSpacer_3)

        self.verticalLayout_5.addLayout(self.horizontalLayout_15)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.horizontalSpacer_2 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)

        self.label_31 = QLabel(self.groupBox_9)
        self.label_31.setObjectName("label_31")

        self.horizontalLayout_5.addWidget(self.label_31)

        self.comboBox_3 = QComboBox(self.groupBox_9)
        self.comboBox_3.addItem("")
        self.comboBox_3.addItem("")
        self.comboBox_3.setObjectName("comboBox_3")
        self.comboBox_3.setMinimumSize(QSize(100, 0))
        self.comboBox_3.setMaximumSize(QSize(100, 16777215))

        self.horizontalLayout_5.addWidget(self.comboBox_3)

        self.label = QLabel(self.groupBox_9)
        self.label.setObjectName("label")

        self.horizontalLayout_5.addWidget(self.label)

        self.lineEdit_4 = QLineEdit(self.groupBox_9)
        self.lineEdit_4.setObjectName("lineEdit_4")
        self.lineEdit_4.setMinimumSize(QSize(320, 0))
        self.lineEdit_4.setMaximumSize(QSize(320, 16777215))
        font2 = QFont()
        font2.setPointSize(5)
        self.lineEdit_4.setFont(font2)
        self.lineEdit_4.setMaxLength(64)
        self.lineEdit_4.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.lineEdit_4)

        self.label_18 = QLabel(self.groupBox_9)
        self.label_18.setObjectName("label_18")

        self.horizontalLayout_5.addWidget(self.label_18)

        self.lineEdit_6 = QLineEdit(self.groupBox_9)
        self.lineEdit_6.setObjectName("lineEdit_6")
        self.lineEdit_6.setMinimumSize(QSize(320, 0))
        self.lineEdit_6.setMaximumSize(QSize(320, 16777215))
        self.lineEdit_6.setFont(font2)
        self.lineEdit_6.setMaxLength(64)
        self.lineEdit_6.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.lineEdit_6)

        self.line = QFrame(self.groupBox_9)
        self.line.setObjectName("line")
        self.line.setFrameShape(QFrame.VLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_5.addWidget(self.line)

        self.label_7 = QLabel(self.groupBox_9)
        self.label_7.setObjectName("label_7")

        self.horizontalLayout_5.addWidget(self.label_7)

        self.spinBox = QSpinBox(self.groupBox_9)
        self.spinBox.setObjectName("spinBox")
        self.spinBox.setMinimumSize(QSize(80, 0))
        self.spinBox.setMaximumSize(QSize(80, 16777215))
        self.spinBox.setAlignment(Qt.AlignCenter)
        self.spinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.spinBox.setMinimum(1)
        self.spinBox.setMaximum(100)

        self.horizontalLayout_5.addWidget(self.spinBox)

        self.line_3 = QFrame(self.groupBox_9)
        self.line_3.setObjectName("line_3")
        self.line_3.setFrameShape(QFrame.VLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_5.addWidget(self.line_3)

        self.pushButton_12 = QPushButton(self.groupBox_9)
        self.pushButton_12.setObjectName("pushButton_12")
        sizePolicy.setHeightForWidth(
            self.pushButton_12.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_12.setSizePolicy(sizePolicy)

        self.horizontalLayout_5.addWidget(self.pushButton_12)

        self.horizontalSpacer_4 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_5.addItem(self.horizontalSpacer_4)

        self.verticalLayout_5.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_27 = QHBoxLayout()
        self.horizontalLayout_27.setObjectName("horizontalLayout_27")
        self.progressBar_2 = QProgressBar(self.groupBox_9)
        self.progressBar_2.setObjectName("progressBar_2")
        self.progressBar_2.setFont(font1)
        self.progressBar_2.setMaximum(1000)
        self.progressBar_2.setTextVisible(False)

        self.horizontalLayout_27.addWidget(self.progressBar_2)

        self.verticalLayout_5.addLayout(self.horizontalLayout_27)

        self.verticalLayout_3.addWidget(self.groupBox_9)

        self.board.addTab(self.tab, "")
        self.tab_13 = QWidget()
        self.tab_13.setObjectName("tab_13")
        self.verticalLayout_10 = QVBoxLayout(self.tab_13)
        self.verticalLayout_10.setObjectName("verticalLayout_10")
        self.groupBox_4 = QGroupBox(self.tab_13)
        self.groupBox_4.setObjectName("groupBox_4")
        self.horizontalLayout_10 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.label_13 = QLabel(self.groupBox_4)
        self.label_13.setObjectName("label_13")
        self.label_13.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_10.addWidget(self.label_13)

        self.verticalLayout_10.addWidget(self.groupBox_4)

        self.splitter_2 = QSplitter(self.tab_13)
        self.splitter_2.setObjectName("splitter_2")
        self.splitter_2.setOrientation(Qt.Vertical)
        self.horizontalLayoutWidget_7 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_7.setObjectName("horizontalLayoutWidget_7")
        self.horizontalLayout = QHBoxLayout(self.horizontalLayoutWidget_7)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_7)
        self.horizontalLayoutWidget_2 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayout_19 = QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_19.setObjectName("horizontalLayout_19")
        self.horizontalLayout_19.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_2)
        self.horizontalLayoutWidget_6 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_6.setObjectName("horizontalLayoutWidget_6")
        self.horizontalLayout_31 = QHBoxLayout(self.horizontalLayoutWidget_6)
        self.horizontalLayout_31.setObjectName("horizontalLayout_31")
        self.horizontalLayout_31.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_6)
        self.horizontalLayoutWidget_4 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_4.setObjectName("horizontalLayoutWidget_4")
        self.horizontalLayout_30 = QHBoxLayout(self.horizontalLayoutWidget_4)
        self.horizontalLayout_30.setObjectName("horizontalLayout_30")
        self.horizontalLayout_30.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_4)

        self.verticalLayout_10.addWidget(self.splitter_2)

        self.groupBox_5 = QGroupBox(self.tab_13)
        self.groupBox_5.setObjectName("groupBox_5")
        self.horizontalLayout_11 = QHBoxLayout(self.groupBox_5)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")
        self.label_19 = QLabel(self.groupBox_5)
        self.label_19.setObjectName("label_19")
        self.label_19.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_11.addWidget(self.label_19)

        self.verticalLayout_10.addWidget(self.groupBox_5)

        self.groupBox_3 = QGroupBox(self.tab_13)
        self.groupBox_3.setObjectName("groupBox_3")
        self.groupBox_3.setEnabled(True)
        self.verticalLayout_6 = QVBoxLayout(self.groupBox_3)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.horizontalLayout_23 = QHBoxLayout()
        self.horizontalLayout_23.setObjectName("horizontalLayout_23")
        self.horizontalSpacer_21 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_23.addItem(self.horizontalSpacer_21)

        self.checkBox_3 = QCheckBox(self.groupBox_3)
        self.checkBox_3.setObjectName("checkBox_3")

        self.horizontalLayout_23.addWidget(self.checkBox_3)

        self.pushButton_15 = QPushButton(self.groupBox_3)
        self.pushButton_15.setObjectName("pushButton_15")

        self.horizontalLayout_23.addWidget(self.pushButton_15)

        self.label_10 = QLabel(self.groupBox_3)
        self.label_10.setObjectName("label_10")

        self.horizontalLayout_23.addWidget(self.label_10)

        self.comboBox_6 = QComboBox(self.groupBox_3)
        self.comboBox_6.setObjectName("comboBox_6")
        self.comboBox_6.setMinimumSize(QSize(150, 0))
        self.comboBox_6.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_23.addWidget(self.comboBox_6)

        self.line_2 = QFrame(self.groupBox_3)
        self.line_2.setObjectName("line_2")
        self.line_2.setFrameShape(QFrame.VLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_23.addWidget(self.line_2)

        self.label_20 = QLabel(self.groupBox_3)
        self.label_20.setObjectName("label_20")

        self.horizontalLayout_23.addWidget(self.label_20)

        self.doubleSpinBox_2 = QDoubleSpinBox(self.groupBox_3)
        self.doubleSpinBox_2.setObjectName("doubleSpinBox_2")
        self.doubleSpinBox_2.setMinimumSize(QSize(80, 0))
        self.doubleSpinBox_2.setMaximumSize(QSize(80, 16777215))
        self.doubleSpinBox_2.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_2.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.doubleSpinBox_2.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.doubleSpinBox_2.setDecimals(3)
        self.doubleSpinBox_2.setMaximum(1.000000000000000)
        self.doubleSpinBox_2.setSingleStep(0.001000000000000)
        self.doubleSpinBox_2.setValue(0.020000000000000)

        self.horizontalLayout_23.addWidget(self.doubleSpinBox_2)

        self.label_4 = QLabel(self.groupBox_3)
        self.label_4.setObjectName("label_4")

        self.horizontalLayout_23.addWidget(self.label_4)

        self.doubleSpinBox = QDoubleSpinBox(self.groupBox_3)
        self.doubleSpinBox.setObjectName("doubleSpinBox")
        self.doubleSpinBox.setMinimumSize(QSize(80, 0))
        self.doubleSpinBox.setMaximumSize(QSize(80, 16777215))
        self.doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.doubleSpinBox.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.doubleSpinBox.setDecimals(3)
        self.doubleSpinBox.setMaximum(1.000000000000000)
        self.doubleSpinBox.setSingleStep(0.001000000000000)
        self.doubleSpinBox.setValue(0.040000000000000)

        self.horizontalLayout_23.addWidget(self.doubleSpinBox)

        self.label_17 = QLabel(self.groupBox_3)
        self.label_17.setObjectName("label_17")

        self.horizontalLayout_23.addWidget(self.label_17)

        self.spinBox_2 = QSpinBox(self.groupBox_3)
        self.spinBox_2.setObjectName("spinBox_2")
        self.spinBox_2.setMinimumSize(QSize(80, 0))
        self.spinBox_2.setMaximumSize(QSize(80, 16777215))
        self.spinBox_2.setAlignment(Qt.AlignCenter)
        self.spinBox_2.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox_2.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.spinBox_2.setMinimum(1)
        self.spinBox_2.setMaximum(100)

        self.horizontalLayout_23.addWidget(self.spinBox_2)

        self.horizontalSpacer_22 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_23.addItem(self.horizontalSpacer_22)

        self.verticalLayout_6.addLayout(self.horizontalLayout_23)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.horizontalSpacer_13 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_9.addItem(self.horizontalSpacer_13)

        self.label_23 = QLabel(self.groupBox_3)
        self.label_23.setObjectName("label_23")

        self.horizontalLayout_9.addWidget(self.label_23)

        self.comboBox_5 = QComboBox(self.groupBox_3)
        self.comboBox_5.setObjectName("comboBox_5")
        self.comboBox_5.setMinimumSize(QSize(100, 0))
        self.comboBox_5.setMaximumSize(QSize(100, 16777215))

        self.horizontalLayout_9.addWidget(self.comboBox_5)

        self.label_22 = QLabel(self.groupBox_3)
        self.label_22.setObjectName("label_22")

        self.horizontalLayout_9.addWidget(self.label_22)

        self.comboBox = QComboBox(self.groupBox_3)
        self.comboBox.setObjectName("comboBox")
        self.comboBox.setMinimumSize(QSize(380, 0))
        self.comboBox.setMaximumSize(QSize(380, 16777215))

        self.horizontalLayout_9.addWidget(self.comboBox)

        self.pushButton_3 = QPushButton(self.groupBox_3)
        self.pushButton_3.setObjectName("pushButton_3")
        sizePolicy.setHeightForWidth(self.pushButton_3.sizePolicy().hasHeightForWidth())
        self.pushButton_3.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_3)

        self.pushButton_17 = QPushButton(self.groupBox_3)
        self.pushButton_17.setObjectName("pushButton_17")

        self.horizontalLayout_9.addWidget(self.pushButton_17)

        self.pushButton_4 = QPushButton(self.groupBox_3)
        self.pushButton_4.setObjectName("pushButton_4")
        sizePolicy.setHeightForWidth(self.pushButton_4.sizePolicy().hasHeightForWidth())
        self.pushButton_4.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_4)

        self.pushButton_16 = QPushButton(self.groupBox_3)
        self.pushButton_16.setObjectName("pushButton_16")

        self.horizontalLayout_9.addWidget(self.pushButton_16)

        self.line_4 = QFrame(self.groupBox_3)
        self.line_4.setObjectName("line_4")
        self.line_4.setFrameShape(QFrame.VLine)
        self.line_4.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_9.addWidget(self.line_4)

        self.pushButton_11 = QPushButton(self.groupBox_3)
        self.pushButton_11.setObjectName("pushButton_11")
        sizePolicy.setHeightForWidth(
            self.pushButton_11.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_11.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_11)

        self.horizontalSpacer_14 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_9.addItem(self.horizontalSpacer_14)

        self.verticalLayout_6.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.progressBar_4 = QProgressBar(self.groupBox_3)
        self.progressBar_4.setObjectName("progressBar_4")
        self.progressBar_4.setMinimumSize(QSize(160, 0))
        self.progressBar_4.setMaximumSize(QSize(160, 16777215))
        self.progressBar_4.setFont(font1)
        self.progressBar_4.setMaximum(1000)
        self.progressBar_4.setTextVisible(False)

        self.horizontalLayout_8.addWidget(self.progressBar_4)

        self.progressBar = QProgressBar(self.groupBox_3)
        self.progressBar.setObjectName("progressBar")
        self.progressBar.setFont(font1)
        self.progressBar.setMaximum(1000)
        self.progressBar.setTextVisible(False)

        self.horizontalLayout_8.addWidget(self.progressBar)

        self.verticalLayout_6.addLayout(self.horizontalLayout_8)

        self.verticalLayout_10.addWidget(self.groupBox_3)

        self.board.addTab(self.tab_13, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName("tab_3")
        self.verticalLayout_21 = QVBoxLayout(self.tab_3)
        self.verticalLayout_21.setObjectName("verticalLayout_21")
        self.horizontalLayout_25 = QHBoxLayout()
        self.horizontalLayout_25.setObjectName("horizontalLayout_25")
        self.verticalLayout_20 = QVBoxLayout()
        self.verticalLayout_20.setObjectName("verticalLayout_20")
        self.label_30 = QLabel(self.tab_3)
        self.label_30.setObjectName("label_30")
        self.label_30.setAlignment(Qt.AlignCenter)

        self.verticalLayout_20.addWidget(self.label_30)

        self.plainTextEdit_3 = ScriptEditor(self.tab_3)
        self.plainTextEdit_3.setObjectName("plainTextEdit_3")
        self.plainTextEdit_3.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.verticalLayout_20.addWidget(self.plainTextEdit_3)

        self.horizontalLayout_25.addLayout(self.verticalLayout_20)

        self.verticalLayout_19 = QVBoxLayout()
        self.verticalLayout_19.setObjectName("verticalLayout_19")
        self.label_11 = QLabel(self.tab_3)
        self.label_11.setObjectName("label_11")
        self.label_11.setAlignment(Qt.AlignCenter)

        self.verticalLayout_19.addWidget(self.label_11)

        self.plainTextEdit_2 = ScriptEditor(self.tab_3)
        self.plainTextEdit_2.setObjectName("plainTextEdit_2")
        self.plainTextEdit_2.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.verticalLayout_19.addWidget(self.plainTextEdit_2)

        self.horizontalLayout_25.addLayout(self.verticalLayout_19)

        self.verticalLayout_21.addLayout(self.horizontalLayout_25)

        self.groupBox_17 = QGroupBox(self.tab_3)
        self.groupBox_17.setObjectName("groupBox_17")
        self.verticalLayout_23 = QVBoxLayout(self.groupBox_17)
        self.verticalLayout_23.setObjectName("verticalLayout_23")
        self.horizontalLayout_26 = QHBoxLayout()
        self.horizontalLayout_26.setObjectName("horizontalLayout_26")
        self.horizontalSpacer_23 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_26.addItem(self.horizontalSpacer_23)

        self.checkBox_6 = QCheckBox(self.groupBox_17)
        self.checkBox_6.setObjectName("checkBox_6")
        self.checkBox_6.setChecked(True)

        self.horizontalLayout_26.addWidget(self.checkBox_6)

        self.line_10 = QFrame(self.groupBox_17)
        self.line_10.setObjectName("line_10")
        self.line_10.setFrameShape(QFrame.VLine)
        self.line_10.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_26.addWidget(self.line_10)

        self.label_43 = QLabel(self.groupBox_17)
        self.label_43.setObjectName("label_43")

        self.horizontalLayout_26.addWidget(self.label_43)

        self.spinBox_3 = QSpinBox(self.groupBox_17)
        self.spinBox_3.setObjectName("spinBox_3")
        self.spinBox_3.setMinimumSize(QSize(80, 0))
        self.spinBox_3.setMaximumSize(QSize(80, 16777215))
        self.spinBox_3.setAlignment(Qt.AlignCenter)
        self.spinBox_3.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox_3.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.spinBox_3.setMinimum(7)
        self.spinBox_3.setMaximum(90)
        self.spinBox_3.setValue(30)

        self.horizontalLayout_26.addWidget(self.spinBox_3)

        self.checkBox_7 = QCheckBox(self.groupBox_17)
        self.checkBox_7.setObjectName("checkBox_7")
        self.checkBox_7.setChecked(True)

        self.horizontalLayout_26.addWidget(self.checkBox_7)

        self.line_7 = QFrame(self.groupBox_17)
        self.line_7.setObjectName("line_7")
        self.line_7.setFrameShape(QFrame.VLine)
        self.line_7.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_26.addWidget(self.line_7)

        self.pushButton_19 = QPushButton(self.groupBox_17)
        self.pushButton_19.setObjectName("pushButton_19")

        self.horizontalLayout_26.addWidget(self.pushButton_19)

        self.pushButton_20 = QPushButton(self.groupBox_17)
        self.pushButton_20.setObjectName("pushButton_20")

        self.horizontalLayout_26.addWidget(self.pushButton_20)

        self.line_11 = QFrame(self.groupBox_17)
        self.line_11.setObjectName("line_11")
        self.line_11.setFrameShape(QFrame.VLine)
        self.line_11.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_26.addWidget(self.line_11)

        self.pushButton_9 = QPushButton(self.groupBox_17)
        self.pushButton_9.setObjectName("pushButton_9")

        self.horizontalLayout_26.addWidget(self.pushButton_9)

        self.horizontalSpacer_24 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_26.addItem(self.horizontalSpacer_24)

        self.verticalLayout_23.addLayout(self.horizontalLayout_26)

        self.verticalLayout_21.addWidget(self.groupBox_17)

        self.board.addTab(self.tab_3, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName("tab_2")
        self.verticalLayout = QVBoxLayout(self.tab_2)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QTabWidget(self.tab_2)
        self.tabWidget.setObjectName("tabWidget")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName("tab_4")
        self.verticalLayout_9 = QVBoxLayout(self.tab_4)
        self.verticalLayout_9.setObjectName("verticalLayout_9")
        self.horizontalLayout_22 = QHBoxLayout()
        self.horizontalLayout_22.setObjectName("horizontalLayout_22")
        self.horizontalSpacer_11 = QSpacerItem(
            323, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_22.addItem(self.horizontalSpacer_11)

        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName("verticalLayout_13")
        self.verticalSpacer_2 = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.verticalLayout_13.addItem(self.verticalSpacer_2)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName("horizontalLayout_13")
        self.label_5 = QLabel(self.tab_4)
        self.label_5.setObjectName("label_5")
        self.label_5.setMinimumSize(QSize(80, 80))
        self.label_5.setMaximumSize(QSize(80, 80))
        self.label_5.setPixmap(QPixmap("resource/product_icon_solsol.png"))
        self.label_5.setScaledContents(True)

        self.horizontalLayout_13.addWidget(self.label_5)

        self.label_9 = QLabel(self.tab_4)
        self.label_9.setObjectName("label_9")
        self.label_9.setMinimumSize(QSize(320, 80))
        self.label_9.setMaximumSize(QSize(320, 80))
        self.label_9.setPixmap(QPixmap("resource/product_text_solsol.png"))
        self.label_9.setScaledContents(True)

        self.horizontalLayout_13.addWidget(self.label_9)

        self.verticalLayout_13.addLayout(self.horizontalLayout_13)

        self.label_15 = QLabel(self.tab_4)
        self.label_15.setObjectName("label_15")
        font3 = QFont()
        font3.setPointSize(3)
        self.label_15.setFont(font3)

        self.verticalLayout_13.addWidget(self.label_15)

        self.line_12 = QFrame(self.tab_4)
        self.line_12.setObjectName("line_12")
        self.line_12.setFrameShape(QFrame.HLine)
        self.line_12.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_13.addWidget(self.line_12)

        self.label_14 = QLabel(self.tab_4)
        self.label_14.setObjectName("label_14")
        self.label_14.setFont(font3)

        self.verticalLayout_13.addWidget(self.label_14)

        self.horizontalLayout_18 = QHBoxLayout()
        self.horizontalLayout_18.setObjectName("horizontalLayout_18")
        self.pushButton_7 = QPushButton(self.tab_4)
        self.pushButton_7.setObjectName("pushButton_7")
        sizePolicy.setHeightForWidth(self.pushButton_7.sizePolicy().hasHeightForWidth())
        self.pushButton_7.setSizePolicy(sizePolicy)

        self.horizontalLayout_18.addWidget(self.pushButton_7)

        self.verticalLayout_13.addLayout(self.horizontalLayout_18)

        self.verticalSpacer = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.verticalLayout_13.addItem(self.verticalSpacer)

        self.horizontalLayout_22.addLayout(self.verticalLayout_13)

        self.horizontalSpacer_10 = QSpacerItem(
            324, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_22.addItem(self.horizontalSpacer_10)

        self.verticalLayout_9.addLayout(self.horizontalLayout_22)

        self.groupBox_7 = QGroupBox(self.tab_4)
        self.groupBox_7.setObjectName("groupBox_7")
        self.horizontalLayout_6 = QHBoxLayout(self.groupBox_7)
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.horizontalLayout_21 = QHBoxLayout()
        self.horizontalLayout_21.setObjectName("horizontalLayout_21")
        self.horizontalSpacer_12 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_21.addItem(self.horizontalSpacer_12)

        self.label_3 = QLabel(self.groupBox_7)
        self.label_3.setObjectName("label_3")

        self.horizontalLayout_21.addWidget(self.label_3)

        self.lineEdit = QLineEdit(self.groupBox_7)
        self.lineEdit.setObjectName("lineEdit")
        sizePolicy.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy)
        self.lineEdit.setMinimumSize(QSize(620, 0))
        self.lineEdit.setMaximumSize(QSize(620, 16777215))
        self.lineEdit.setAlignment(Qt.AlignCenter)
        self.lineEdit.setReadOnly(True)

        self.horizontalLayout_21.addWidget(self.lineEdit)

        self.pushButton_8 = QPushButton(self.groupBox_7)
        self.pushButton_8.setObjectName("pushButton_8")

        self.horizontalLayout_21.addWidget(self.pushButton_8)

        self.pushButton_22 = QPushButton(self.groupBox_7)
        self.pushButton_22.setObjectName("pushButton_22")

        self.horizontalLayout_21.addWidget(self.pushButton_22)

        self.line_5 = QFrame(self.groupBox_7)
        self.line_5.setObjectName("line_5")
        self.line_5.setFrameShape(QFrame.VLine)
        self.line_5.setFrameShadow(QFrame.Sunken)

        self.horizontalLayout_21.addWidget(self.line_5)

        self.pushButton_10 = QPushButton(self.groupBox_7)
        self.pushButton_10.setObjectName("pushButton_10")
        sizePolicy.setHeightForWidth(
            self.pushButton_10.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_10.setSizePolicy(sizePolicy)

        self.horizontalLayout_21.addWidget(self.pushButton_10)

        self.horizontalSpacer_5 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_21.addItem(self.horizontalSpacer_5)

        self.horizontalLayout_6.addLayout(self.horizontalLayout_21)

        self.verticalLayout_9.addWidget(self.groupBox_7)

        self.tabWidget.addTab(self.tab_4, "")
        self.tab_6 = QWidget()
        self.tab_6.setObjectName("tab_6")
        self.verticalLayout_8 = QVBoxLayout(self.tab_6)
        self.verticalLayout_8.setObjectName("verticalLayout_8")
        self.horizontalLayout_14 = QHBoxLayout()
        self.horizontalLayout_14.setObjectName("horizontalLayout_14")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_24 = QLabel(self.tab_6)
        self.label_24.setObjectName("label_24")
        self.label_24.setAlignment(Qt.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_24)

        self.plainTextEdit = ScriptEditor(self.tab_6)
        self.plainTextEdit.setObjectName("plainTextEdit")
        self.plainTextEdit.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.verticalLayout_2.addWidget(self.plainTextEdit)

        self.horizontalLayout_14.addLayout(self.verticalLayout_2)

        self.verticalLayout_11 = QVBoxLayout()
        self.verticalLayout_11.setObjectName("verticalLayout_11")
        self.label_25 = QLabel(self.tab_6)
        self.label_25.setObjectName("label_25")
        self.label_25.setAlignment(Qt.AlignCenter)

        self.verticalLayout_11.addWidget(self.label_25)

        self.listWidget = LogList(self.tab_6)
        self.listWidget.setObjectName("listWidget")
        self.listWidget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.listWidget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.verticalLayout_11.addWidget(self.listWidget)

        self.horizontalLayout_14.addLayout(self.verticalLayout_11)

        self.verticalLayout_8.addLayout(self.horizontalLayout_14)

        self.groupBox_18 = QGroupBox(self.tab_6)
        self.groupBox_18.setObjectName("groupBox_18")
        self.verticalLayout_24 = QVBoxLayout(self.groupBox_18)
        self.verticalLayout_24.setObjectName("verticalLayout_24")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalSpacer_6 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_6)

        self.pushButton = QPushButton(self.groupBox_18)
        self.pushButton.setObjectName("pushButton")

        self.horizontalLayout_2.addWidget(self.pushButton)

        self.pushButton_6 = QPushButton(self.groupBox_18)
        self.pushButton_6.setObjectName("pushButton_6")

        self.horizontalLayout_2.addWidget(self.pushButton_6)

        self.horizontalSpacer_7 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_7)

        self.verticalLayout_24.addLayout(self.horizontalLayout_2)

        self.verticalLayout_8.addWidget(self.groupBox_18)

        self.tabWidget.addTab(self.tab_6, "")
        self.tab_7 = QWidget()
        self.tab_7.setObjectName("tab_7")
        self.verticalLayout_7 = QVBoxLayout(self.tab_7)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.scrollArea_6 = QScrollArea(self.tab_7)
        self.scrollArea_6.setObjectName("scrollArea_6")
        self.scrollArea_6.setWidgetResizable(True)
        self.scrollAreaWidgetContents_6 = QWidget()
        self.scrollAreaWidgetContents_6.setObjectName("scrollAreaWidgetContents_6")
        self.scrollAreaWidgetContents_6.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_6 = QGridLayout(self.scrollAreaWidgetContents_6)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.label_33 = QLabel(self.scrollAreaWidgetContents_6)
        self.label_33.setObjectName("label_33")
        self.label_33.setAlignment(Qt.AlignCenter)

        self.gridLayout_6.addWidget(self.label_33, 0, 0, 1, 1)

        self.scrollArea_6.setWidget(self.scrollAreaWidgetContents_6)

        self.gridLayout.addWidget(self.scrollArea_6, 1, 2, 1, 1)

        self.scrollArea_4 = QScrollArea(self.tab_7)
        self.scrollArea_4.setObjectName("scrollArea_4")
        self.scrollArea_4.setWidgetResizable(True)
        self.scrollAreaWidgetContents_4 = QWidget()
        self.scrollAreaWidgetContents_4.setObjectName("scrollAreaWidgetContents_4")
        self.scrollAreaWidgetContents_4.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_7 = QGridLayout(self.scrollAreaWidgetContents_4)
        self.gridLayout_7.setObjectName("gridLayout_7")
        self.label_35 = QLabel(self.scrollAreaWidgetContents_4)
        self.label_35.setObjectName("label_35")
        self.label_35.setAlignment(Qt.AlignCenter)

        self.gridLayout_7.addWidget(self.label_35, 0, 0, 1, 1)

        self.scrollArea_4.setWidget(self.scrollAreaWidgetContents_4)

        self.gridLayout.addWidget(self.scrollArea_4, 3, 1, 1, 1)

        self.scrollArea = QScrollArea(self.tab_7)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_4 = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.label_12 = QLabel(self.scrollAreaWidgetContents)
        self.label_12.setObjectName("label_12")
        self.label_12.setAlignment(Qt.AlignCenter)

        self.gridLayout_4.addWidget(self.label_12, 0, 0, 1, 1)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout.addWidget(self.scrollArea, 1, 0, 1, 1)

        self.scrollArea_5 = QScrollArea(self.tab_7)
        self.scrollArea_5.setObjectName("scrollArea_5")
        self.scrollArea_5.setWidgetResizable(True)
        self.scrollAreaWidgetContents_5 = QWidget()
        self.scrollAreaWidgetContents_5.setObjectName("scrollAreaWidgetContents_5")
        self.scrollAreaWidgetContents_5.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_8 = QGridLayout(self.scrollAreaWidgetContents_5)
        self.gridLayout_8.setObjectName("gridLayout_8")
        self.label_36 = QLabel(self.scrollAreaWidgetContents_5)
        self.label_36.setObjectName("label_36")
        self.label_36.setAlignment(Qt.AlignCenter)

        self.gridLayout_8.addWidget(self.label_36, 0, 0, 1, 1)

        self.scrollArea_5.setWidget(self.scrollAreaWidgetContents_5)

        self.gridLayout.addWidget(self.scrollArea_5, 3, 0, 1, 1)

        self.scrollArea_3 = QScrollArea(self.tab_7)
        self.scrollArea_3.setObjectName("scrollArea_3")
        self.scrollArea_3.setWidgetResizable(True)
        self.scrollAreaWidgetContents_3 = QWidget()
        self.scrollAreaWidgetContents_3.setObjectName("scrollAreaWidgetContents_3")
        self.scrollAreaWidgetContents_3.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_5 = QGridLayout(self.scrollAreaWidgetContents_3)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.label_32 = QLabel(self.scrollAreaWidgetContents_3)
        self.label_32.setObjectName("label_32")
        self.label_32.setAlignment(Qt.AlignCenter)

        self.gridLayout_5.addWidget(self.label_32, 0, 0, 1, 1)

        self.scrollArea_3.setWidget(self.scrollAreaWidgetContents_3)

        self.gridLayout.addWidget(self.scrollArea_3, 1, 1, 1, 1)

        self.scrollArea_7 = QScrollArea(self.tab_7)
        self.scrollArea_7.setObjectName("scrollArea_7")
        self.scrollArea_7.setWidgetResizable(True)
        self.scrollAreaWidgetContents_7 = QWidget()
        self.scrollAreaWidgetContents_7.setObjectName("scrollAreaWidgetContents_7")
        self.scrollAreaWidgetContents_7.setGeometry(QRect(0, 0, 81, 34))
        self.gridLayout_9 = QGridLayout(self.scrollAreaWidgetContents_7)
        self.gridLayout_9.setObjectName("gridLayout_9")
        self.label_34 = QLabel(self.scrollAreaWidgetContents_7)
        self.label_34.setObjectName("label_34")
        self.label_34.setAlignment(Qt.AlignCenter)

        self.gridLayout_9.addWidget(self.label_34, 0, 0, 1, 1)

        self.scrollArea_7.setWidget(self.scrollAreaWidgetContents_7)

        self.gridLayout.addWidget(self.scrollArea_7, 3, 2, 1, 1)

        self.label_37 = QLabel(self.tab_7)
        self.label_37.setObjectName("label_37")
        self.label_37.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_37, 0, 0, 1, 1)

        self.label_38 = QLabel(self.tab_7)
        self.label_38.setObjectName("label_38")
        self.label_38.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_38, 2, 0, 1, 1)

        self.label_39 = QLabel(self.tab_7)
        self.label_39.setObjectName("label_39")
        self.label_39.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_39, 2, 1, 1, 1)

        self.label_40 = QLabel(self.tab_7)
        self.label_40.setObjectName("label_40")
        self.label_40.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_40, 2, 2, 1, 1)

        self.label_41 = QLabel(self.tab_7)
        self.label_41.setObjectName("label_41")
        self.label_41.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_41, 0, 2, 1, 1)

        self.label_42 = QLabel(self.tab_7)
        self.label_42.setObjectName("label_42")
        self.label_42.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_42, 0, 1, 1, 1)

        self.gridLayout.setRowStretch(1, 1)
        self.gridLayout.setRowStretch(3, 1)
        self.gridLayout.setColumnStretch(0, 1)
        self.gridLayout.setColumnStretch(1, 1)
        self.gridLayout.setColumnStretch(2, 1)

        self.verticalLayout_7.addLayout(self.gridLayout)

        self.tabWidget.addTab(self.tab_7, "")
        self.tab_8 = QWidget()
        self.tab_8.setObjectName("tab_8")
        self.horizontalLayout_32 = QHBoxLayout(self.tab_8)
        self.horizontalLayout_32.setObjectName("horizontalLayout_32")
        self.scrollArea_2 = QScrollArea(self.tab_8)
        self.scrollArea_2.setObjectName("scrollArea_2")
        self.scrollArea_2.setWidgetResizable(True)
        self.scrollAreaWidgetContents_2 = QWidget()
        self.scrollAreaWidgetContents_2.setObjectName("scrollAreaWidgetContents_2")
        self.scrollAreaWidgetContents_2.setGeometry(QRect(0, 0, 80, 20))
        self.horizontalLayout_33 = QHBoxLayout(self.scrollAreaWidgetContents_2)
        self.horizontalLayout_33.setObjectName("horizontalLayout_33")
        self.verticalLayout_15 = QVBoxLayout()
        self.verticalLayout_15.setObjectName("verticalLayout_15")

        self.horizontalLayout_33.addLayout(self.verticalLayout_15)

        self.scrollArea_2.setWidget(self.scrollAreaWidgetContents_2)

        self.horizontalLayout_32.addWidget(self.scrollArea_2)

        self.tabWidget.addTab(self.tab_8, "")

        self.verticalLayout.addWidget(self.tabWidget)

        self.board.addTab(self.tab_2, "")

        self.gridLayout_3.addWidget(self.board, 0, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.board.setCurrentIndex(0)
        self.comboBox.setCurrentIndex(-1)
        self.tabWidget.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "Solsol", None)
        )
        self.gauge.setText("")
        self.pushButton_2.setText(
            QCoreApplication.translate("MainWindow", "Fill candle data", None)
        )
        self.pushButton_13.setText(
            QCoreApplication.translate("MainWindow", "\u2630", None)
        )
        self.board.setTabText(
            self.board.indexOf(self.tab_5),
            QCoreApplication.translate("MainWindow", "Collect", None),
        )
        self.checkBox_2.setText(
            QCoreApplication.translate("MainWindow", "Draw frequently", None)
        )
        self.pushButton_14.setText(
            QCoreApplication.translate("MainWindow", "Display last 24 hours", None)
        )
        self.label_2.setText(
            QCoreApplication.translate("MainWindow", "Graph crypto", None)
        )
        self.label_21.setText(
            QCoreApplication.translate("MainWindow", "Strategy", None)
        )
        self.checkBox.setText(
            QCoreApplication.translate("MainWindow", "Auto-transact", None)
        )
        self.label_31.setText(QCoreApplication.translate("MainWindow", "Server", None))
        self.comboBox_3.setItemText(
            0, QCoreApplication.translate("MainWindow", "Real", None)
        )
        self.comboBox_3.setItemText(
            1, QCoreApplication.translate("MainWindow", "Testnet", None)
        )

        self.label.setText(QCoreApplication.translate("MainWindow", "API key", None))
        self.label_18.setText(
            QCoreApplication.translate("MainWindow", "Secret key", None)
        )
        self.label_7.setText(QCoreApplication.translate("MainWindow", "Leverage", None))
        self.spinBox.setPrefix(QCoreApplication.translate("MainWindow", "\u00d7", None))
        self.pushButton_12.setText(
            QCoreApplication.translate("MainWindow", "\u2630", None)
        )
        self.board.setTabText(
            self.board.indexOf(self.tab),
            QCoreApplication.translate("MainWindow", "Transact", None),
        )
        self.checkBox_3.setText(
            QCoreApplication.translate("MainWindow", "Draw all years", None)
        )
        self.pushButton_15.setText(
            QCoreApplication.translate("MainWindow", "Display selected year", None)
        )
        self.label_10.setText(
            QCoreApplication.translate("MainWindow", "Graph crypto", None)
        )
        self.label_20.setText(
            QCoreApplication.translate("MainWindow", "Maker fee", None)
        )
        self.doubleSpinBox_2.setSuffix(
            QCoreApplication.translate("MainWindow", "%", None)
        )
        self.label_4.setText(
            QCoreApplication.translate("MainWindow", "Taker fee", None)
        )
        self.doubleSpinBox.setSuffix(
            QCoreApplication.translate("MainWindow", "%", None)
        )
        self.label_17.setText(
            QCoreApplication.translate("MainWindow", "Leverage", None)
        )
        self.spinBox_2.setPrefix(
            QCoreApplication.translate("MainWindow", "\u00d7", None)
        )
        self.label_23.setText(QCoreApplication.translate("MainWindow", "Year", None))
        self.label_22.setText(
            QCoreApplication.translate("MainWindow", "Strategy", None)
        )
        self.pushButton_3.setText(
            QCoreApplication.translate("MainWindow", "Calculate", None)
        )
        self.pushButton_17.setText(
            QCoreApplication.translate("MainWindow", "Draw", None)
        )
        self.pushButton_4.setText(
            QCoreApplication.translate("MainWindow", "Erase", None)
        )
        self.pushButton_16.setText(
            QCoreApplication.translate("MainWindow", "Forget", None)
        )
        self.pushButton_11.setText(
            QCoreApplication.translate("MainWindow", "\u2630", None)
        )
        self.board.setTabText(
            self.board.indexOf(self.tab_13),
            QCoreApplication.translate("MainWindow", "Simulate", None),
        )
        self.label_30.setText(
            QCoreApplication.translate("MainWindow", "Indicators script", None)
        )
        self.label_11.setText(
            QCoreApplication.translate("MainWindow", "Decision script", None)
        )
        self.checkBox_6.setText(
            QCoreApplication.translate("MainWindow", "Available", None)
        )
        self.label_43.setText(
            QCoreApplication.translate("MainWindow", "Chunk division", None)
        )
        self.spinBox_3.setSuffix(QCoreApplication.translate("MainWindow", "d", None))
        self.checkBox_7.setText(
            QCoreApplication.translate("MainWindow", "Parallelized simulation", None)
        )
        self.pushButton_19.setText(
            QCoreApplication.translate("MainWindow", "Revert", None)
        )
        self.pushButton_20.setText(
            QCoreApplication.translate("MainWindow", "Save", None)
        )
        self.pushButton_9.setText(
            QCoreApplication.translate("MainWindow", "\u2630", None)
        )
        self.board.setTabText(
            self.board.indexOf(self.tab_3),
            QCoreApplication.translate("MainWindow", "Strategize", None),
        )
        self.pushButton_7.setText(
            QCoreApplication.translate("MainWindow", "Open documentation", None)
        )
        self.label_3.setText(
            QCoreApplication.translate("MainWindow", "Data folder", None)
        )
        self.pushButton_8.setText(
            QCoreApplication.translate("MainWindow", "Open with file manager", None)
        )
        self.pushButton_22.setText(
            QCoreApplication.translate("MainWindow", "Change", None)
        )
        self.pushButton_10.setText(
            QCoreApplication.translate("MainWindow", "\u2630", None)
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_4),
            QCoreApplication.translate("MainWindow", "Settings", None),
        )
        self.label_24.setText(
            QCoreApplication.translate("MainWindow", "Python script", None)
        )
        self.label_25.setText(
            QCoreApplication.translate("MainWindow", "Log output", None)
        )
        self.pushButton.setText(
            QCoreApplication.translate("MainWindow", "Run script", None)
        )
        self.pushButton_6.setText(
            QCoreApplication.translate("MainWindow", "Deselect log", None)
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_6),
            QCoreApplication.translate("MainWindow", "Logs", None),
        )
        self.label_33.setText("")
        self.label_35.setText("")
        self.label_12.setText("")
        self.label_36.setText("")
        self.label_32.setText("")
        self.label_34.setText("")
        self.label_37.setText(
            QCoreApplication.translate("MainWindow", "Process pool", None)
        )
        self.label_38.setText(
            QCoreApplication.translate(
                "MainWindow", "Number of transactions inside latest candle", None
            )
        )
        self.label_39.setText(
            QCoreApplication.translate(
                "MainWindow", "Threads in the main process", None
            )
        )
        self.label_40.setText(QCoreApplication.translate("MainWindow", "(None)", None))
        self.label_41.setText(
            QCoreApplication.translate("MainWindow", "Task durations", None)
        )
        self.label_42.setText(
            QCoreApplication.translate(
                "MainWindow", "Binance API usage and limits", None
            )
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_7),
            QCoreApplication.translate("MainWindow", "Status", None),
        )
        self.tabWidget.setTabText(
            self.tabWidget.indexOf(self.tab_8),
            QCoreApplication.translate("MainWindow", "License", None),
        )
        self.board.setTabText(
            self.board.indexOf(self.tab_2),
            QCoreApplication.translate("MainWindow", "Manage", None),
        )

    # retranslateUi
