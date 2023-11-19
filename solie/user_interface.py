# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'user_interface.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox,
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidgetItem, QMainWindow, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QSpinBox, QSplitter, QTabWidget,
    QVBoxLayout, QWidget)

from solie.widget.horizontal_divider import HorizontalDivider
from solie.widget.log_list import LogList
from solie.widget.script_editor import ScriptEditor
from solie.widget.vertical_divider import VerticalDivider

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 720)
        MainWindow.setMinimumSize(QSize(1280, 720))
        icon = QIcon()
        icon.addFile(u"solie/static/product_icon.png", QSize(), QIcon.Normal, QIcon.Off)
        MainWindow.setWindowIcon(icon)
        MainWindow.setStyleSheet(u"QPushButton, QComboBox, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox {\n"
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
"    background: rgba(0,0,0,0);\n"
"}\n"
"\n"
"QGroupBox {\n"
"	background: 1px solid rgba(255,255,255,0.02);\n"
"	border-radius: 0.2em;\n"
"	border: 1px solid rgba(255,255,255,0.1);\n"
"}\n"
"\n"
"ScriptEditor, LogList {\n"
"    background: #4C3f33;\n"
"	border-radius: 0.2em;\n"
"	border: 1px solid rgba(255,255,255,0.1);\n"
"}\n"
"\n"
"SymbolBox {\n"
"    min-width: 10em;\n"
"    max-width: 10em;\n"
"    min-height: 10em;\n"
"    max-height: 10em;\n"
"    background: rgba(255,255,255,0.05);\n"
"	border: 1px solid rgba(255,255,255,0.1);\n"
" "
                        "   border-radius: 5em;\n"
"}\n"
"\n"
"AskPopup, OverlayPanel {\n"
"    background: rgba(0, 0, 0, 191);\n"
"}\n"
"\n"
"PopupBox {\n"
"    border: 1px solid rgba(255,255,255,0.1);\n"
"    border-radius: 0.4em;\n"
"    background: #2B2B2B;\n"
"    margin: 1.2em;\n"
"    padding: 1.2em;\n"
"}\n"
"\n"
"BrandLabel {\n"
"	color: #888888;\n"
"}\n"
"\n"
"HorizontalDivider, VerticalDivider {\n"
"    border: 8px solid #464646;\n"
"}\n"
"\n"
"TransparentScrollArea, TransparentScrollArea > QWidget > QWidget {\n"
"    background: transparent;\n"
"}")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_3 = QGridLayout(self.centralwidget)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.board = QTabWidget(self.centralwidget)
        self.board.setObjectName(u"board")
        self.board.setTabPosition(QTabWidget.North)
        self.tab_5 = QWidget()
        self.tab_5.setObjectName(u"tab_5")
        self.verticalLayout_4 = QVBoxLayout(self.tab_5)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_3)

        self.verticalLayout_14 = QVBoxLayout()
        self.verticalLayout_14.setObjectName(u"verticalLayout_14")

        self.verticalLayout_4.addLayout(self.verticalLayout_14)

        self.horizontalLayout_20 = QHBoxLayout()
        self.horizontalLayout_20.setObjectName(u"horizontalLayout_20")

        self.verticalLayout_4.addLayout(self.horizontalLayout_20)

        self.horizontalLayout_17 = QHBoxLayout()
        self.horizontalLayout_17.setObjectName(u"horizontalLayout_17")

        self.verticalLayout_4.addLayout(self.horizontalLayout_17)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_4)

        self.horizontalLayout_21 = QHBoxLayout()
        self.horizontalLayout_21.setObjectName(u"horizontalLayout_21")
        self.horizontalSpacer_17 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_21.addItem(self.horizontalSpacer_17)

        self.pushButton_9 = QPushButton(self.tab_5)
        self.pushButton_9.setObjectName(u"pushButton_9")
        self.pushButton_9.setStyleSheet(u"color:rgba(255,255,255,0.5)")
        self.pushButton_9.setFlat(True)

        self.horizontalLayout_21.addWidget(self.pushButton_9)

        self.horizontalSpacer_18 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_21.addItem(self.horizontalSpacer_18)


        self.verticalLayout_4.addLayout(self.horizontalLayout_21)

        self.groupBox_10 = QGroupBox(self.tab_5)
        self.groupBox_10.setObjectName(u"groupBox_10")
        self.verticalLayout_12 = QVBoxLayout(self.groupBox_10)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.label_6 = QLabel(self.groupBox_10)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setAlignment(Qt.AlignCenter)

        self.verticalLayout_12.addWidget(self.label_6)


        self.verticalLayout_4.addWidget(self.groupBox_10)

        self.groupBox_6 = QGroupBox(self.tab_5)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.verticalLayout_17 = QVBoxLayout(self.groupBox_6)
        self.verticalLayout_17.setObjectName(u"verticalLayout_17")
        self.horizontalLayout_24 = QHBoxLayout()
        self.horizontalLayout_24.setObjectName(u"horizontalLayout_24")
        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_24.addItem(self.horizontalSpacer_8)

        self.pushButton_2 = QPushButton(self.groupBox_6)
        self.pushButton_2.setObjectName(u"pushButton_2")

        self.horizontalLayout_24.addWidget(self.pushButton_2)

        self.frame = VerticalDivider(self.groupBox_6)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.VLine)

        self.horizontalLayout_24.addWidget(self.frame)

        self.pushButton_13 = QPushButton(self.groupBox_6)
        self.pushButton_13.setObjectName(u"pushButton_13")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_13.sizePolicy().hasHeightForWidth())
        self.pushButton_13.setSizePolicy(sizePolicy)

        self.horizontalLayout_24.addWidget(self.pushButton_13)

        self.horizontalSpacer_9 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_24.addItem(self.horizontalSpacer_9)


        self.verticalLayout_17.addLayout(self.horizontalLayout_24)

        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.progressBar_3 = QProgressBar(self.groupBox_6)
        self.progressBar_3.setObjectName(u"progressBar_3")
        font = QFont()
        font.setPointSize(1)
        self.progressBar_3.setFont(font)
        self.progressBar_3.setMaximum(1000)
        self.progressBar_3.setTextVisible(False)

        self.horizontalLayout_12.addWidget(self.progressBar_3)


        self.verticalLayout_17.addLayout(self.horizontalLayout_12)


        self.verticalLayout_4.addWidget(self.groupBox_6)

        self.board.addTab(self.tab_5, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_3 = QVBoxLayout(self.tab)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.groupBox_2 = QGroupBox(self.tab)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.horizontalLayout_4 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_4.addWidget(self.label_8)


        self.verticalLayout_3.addWidget(self.groupBox_2)

        self.splitter = QSplitter(self.tab)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.horizontalLayoutWidget_1 = QWidget(self.splitter)
        self.horizontalLayoutWidget_1.setObjectName(u"horizontalLayoutWidget_1")
        self.horizontalLayout_7 = QHBoxLayout(self.horizontalLayoutWidget_1)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_1)
        self.horizontalLayoutWidget = QWidget(self.splitter)
        self.horizontalLayoutWidget.setObjectName(u"horizontalLayoutWidget")
        self.horizontalLayout_16 = QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.horizontalLayout_16.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget)
        self.horizontalLayoutWidget_5 = QWidget(self.splitter)
        self.horizontalLayoutWidget_5.setObjectName(u"horizontalLayoutWidget_5")
        self.horizontalLayout_28 = QHBoxLayout(self.horizontalLayoutWidget_5)
        self.horizontalLayout_28.setObjectName(u"horizontalLayout_28")
        self.horizontalLayout_28.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_5)
        self.horizontalLayoutWidget_3 = QWidget(self.splitter)
        self.horizontalLayoutWidget_3.setObjectName(u"horizontalLayoutWidget_3")
        self.horizontalLayout_29 = QHBoxLayout(self.horizontalLayoutWidget_3)
        self.horizontalLayout_29.setObjectName(u"horizontalLayout_29")
        self.horizontalLayout_29.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.horizontalLayoutWidget_3)

        self.verticalLayout_3.addWidget(self.splitter)

        self.groupBox = QGroupBox(self.tab)
        self.groupBox.setObjectName(u"groupBox")
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_16 = QLabel(self.groupBox)
        self.label_16.setObjectName(u"label_16")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_16.sizePolicy().hasHeightForWidth())
        self.label_16.setSizePolicy(sizePolicy1)
        font1 = QFont()
        self.label_16.setFont(font1)
        self.label_16.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_3.addWidget(self.label_16)


        self.verticalLayout_3.addWidget(self.groupBox)

        self.groupBox_9 = QGroupBox(self.tab)
        self.groupBox_9.setObjectName(u"groupBox_9")
        self.verticalLayout_5 = QVBoxLayout(self.groupBox_9)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.horizontalLayout_15 = QHBoxLayout()
        self.horizontalLayout_15.setObjectName(u"horizontalLayout_15")
        self.horizontalSpacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_15.addItem(self.horizontalSpacer)

        self.checkBox_2 = QCheckBox(self.groupBox_9)
        self.checkBox_2.setObjectName(u"checkBox_2")
        self.checkBox_2.setChecked(True)

        self.horizontalLayout_15.addWidget(self.checkBox_2)

        self.pushButton_14 = QPushButton(self.groupBox_9)
        self.pushButton_14.setObjectName(u"pushButton_14")

        self.horizontalLayout_15.addWidget(self.pushButton_14)

        self.label_2 = QLabel(self.groupBox_9)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_15.addWidget(self.label_2)

        self.comboBox_4 = QComboBox(self.groupBox_9)
        self.comboBox_4.setObjectName(u"comboBox_4")
        self.comboBox_4.setMinimumSize(QSize(150, 0))
        self.comboBox_4.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_15.addWidget(self.comboBox_4)

        self.frame_7 = VerticalDivider(self.groupBox_9)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.VLine)

        self.horizontalLayout_15.addWidget(self.frame_7)

        self.label_21 = QLabel(self.groupBox_9)
        self.label_21.setObjectName(u"label_21")

        self.horizontalLayout_15.addWidget(self.label_21)

        self.comboBox_2 = QComboBox(self.groupBox_9)
        self.comboBox_2.setObjectName(u"comboBox_2")
        self.comboBox_2.setMinimumSize(QSize(380, 0))
        self.comboBox_2.setMaximumSize(QSize(380, 16777215))

        self.horizontalLayout_15.addWidget(self.comboBox_2)

        self.checkBox = QCheckBox(self.groupBox_9)
        self.checkBox.setObjectName(u"checkBox")
        self.checkBox.setMaximumSize(QSize(16777215, 16777215))

        self.horizontalLayout_15.addWidget(self.checkBox)

        self.horizontalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_15.addItem(self.horizontalSpacer_3)


        self.verticalLayout_5.addLayout(self.horizontalLayout_15)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_2)

        self.label = QLabel(self.groupBox_9)
        self.label.setObjectName(u"label")

        self.horizontalLayout_5.addWidget(self.label)

        self.lineEdit_4 = QLineEdit(self.groupBox_9)
        self.lineEdit_4.setObjectName(u"lineEdit_4")
        self.lineEdit_4.setMinimumSize(QSize(320, 0))
        self.lineEdit_4.setMaximumSize(QSize(320, 16777215))
        font2 = QFont()
        font2.setPointSize(5)
        self.lineEdit_4.setFont(font2)
        self.lineEdit_4.setMaxLength(64)
        self.lineEdit_4.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.lineEdit_4)

        self.label_18 = QLabel(self.groupBox_9)
        self.label_18.setObjectName(u"label_18")

        self.horizontalLayout_5.addWidget(self.label_18)

        self.lineEdit_6 = QLineEdit(self.groupBox_9)
        self.lineEdit_6.setObjectName(u"lineEdit_6")
        self.lineEdit_6.setMinimumSize(QSize(320, 0))
        self.lineEdit_6.setMaximumSize(QSize(320, 16777215))
        self.lineEdit_6.setFont(font2)
        self.lineEdit_6.setMaxLength(64)
        self.lineEdit_6.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.lineEdit_6)

        self.frame_4 = VerticalDivider(self.groupBox_9)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.VLine)

        self.horizontalLayout_5.addWidget(self.frame_4)

        self.label_7 = QLabel(self.groupBox_9)
        self.label_7.setObjectName(u"label_7")

        self.horizontalLayout_5.addWidget(self.label_7)

        self.spinBox = QSpinBox(self.groupBox_9)
        self.spinBox.setObjectName(u"spinBox")
        self.spinBox.setMinimumSize(QSize(80, 0))
        self.spinBox.setMaximumSize(QSize(80, 16777215))
        self.spinBox.setAlignment(Qt.AlignCenter)
        self.spinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.spinBox.setMinimum(1)
        self.spinBox.setMaximum(125)

        self.horizontalLayout_5.addWidget(self.spinBox)

        self.frame_8 = VerticalDivider(self.groupBox_9)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.VLine)

        self.horizontalLayout_5.addWidget(self.frame_8)

        self.pushButton_12 = QPushButton(self.groupBox_9)
        self.pushButton_12.setObjectName(u"pushButton_12")
        sizePolicy.setHeightForWidth(self.pushButton_12.sizePolicy().hasHeightForWidth())
        self.pushButton_12.setSizePolicy(sizePolicy)

        self.horizontalLayout_5.addWidget(self.pushButton_12)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_4)


        self.verticalLayout_5.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_27 = QHBoxLayout()
        self.horizontalLayout_27.setObjectName(u"horizontalLayout_27")
        self.progressBar_2 = QProgressBar(self.groupBox_9)
        self.progressBar_2.setObjectName(u"progressBar_2")
        self.progressBar_2.setFont(font)
        self.progressBar_2.setMaximum(1000)
        self.progressBar_2.setTextVisible(False)

        self.horizontalLayout_27.addWidget(self.progressBar_2)


        self.verticalLayout_5.addLayout(self.horizontalLayout_27)


        self.verticalLayout_3.addWidget(self.groupBox_9)

        self.board.addTab(self.tab, "")
        self.tab_13 = QWidget()
        self.tab_13.setObjectName(u"tab_13")
        self.verticalLayout_10 = QVBoxLayout(self.tab_13)
        self.verticalLayout_10.setObjectName(u"verticalLayout_10")
        self.groupBox_4 = QGroupBox(self.tab_13)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.horizontalLayout_10 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.label_13 = QLabel(self.groupBox_4)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_10.addWidget(self.label_13)


        self.verticalLayout_10.addWidget(self.groupBox_4)

        self.splitter_2 = QSplitter(self.tab_13)
        self.splitter_2.setObjectName(u"splitter_2")
        self.splitter_2.setOrientation(Qt.Vertical)
        self.horizontalLayoutWidget_7 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_7.setObjectName(u"horizontalLayoutWidget_7")
        self.horizontalLayout = QHBoxLayout(self.horizontalLayoutWidget_7)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_7)
        self.horizontalLayoutWidget_2 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_2.setObjectName(u"horizontalLayoutWidget_2")
        self.horizontalLayout_19 = QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_19.setObjectName(u"horizontalLayout_19")
        self.horizontalLayout_19.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_2)
        self.horizontalLayoutWidget_6 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_6.setObjectName(u"horizontalLayoutWidget_6")
        self.horizontalLayout_31 = QHBoxLayout(self.horizontalLayoutWidget_6)
        self.horizontalLayout_31.setObjectName(u"horizontalLayout_31")
        self.horizontalLayout_31.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_6)
        self.horizontalLayoutWidget_4 = QWidget(self.splitter_2)
        self.horizontalLayoutWidget_4.setObjectName(u"horizontalLayoutWidget_4")
        self.horizontalLayout_30 = QHBoxLayout(self.horizontalLayoutWidget_4)
        self.horizontalLayout_30.setObjectName(u"horizontalLayout_30")
        self.horizontalLayout_30.setContentsMargins(0, 0, 0, 0)
        self.splitter_2.addWidget(self.horizontalLayoutWidget_4)

        self.verticalLayout_10.addWidget(self.splitter_2)

        self.groupBox_5 = QGroupBox(self.tab_13)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.horizontalLayout_11 = QHBoxLayout(self.groupBox_5)
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.label_19 = QLabel(self.groupBox_5)
        self.label_19.setObjectName(u"label_19")
        self.label_19.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_11.addWidget(self.label_19)


        self.verticalLayout_10.addWidget(self.groupBox_5)

        self.groupBox_3 = QGroupBox(self.tab_13)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setEnabled(True)
        self.verticalLayout_6 = QVBoxLayout(self.groupBox_3)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.horizontalLayout_23 = QHBoxLayout()
        self.horizontalLayout_23.setObjectName(u"horizontalLayout_23")
        self.horizontalSpacer_21 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_23.addItem(self.horizontalSpacer_21)

        self.checkBox_3 = QCheckBox(self.groupBox_3)
        self.checkBox_3.setObjectName(u"checkBox_3")

        self.horizontalLayout_23.addWidget(self.checkBox_3)

        self.pushButton_15 = QPushButton(self.groupBox_3)
        self.pushButton_15.setObjectName(u"pushButton_15")

        self.horizontalLayout_23.addWidget(self.pushButton_15)

        self.label_10 = QLabel(self.groupBox_3)
        self.label_10.setObjectName(u"label_10")

        self.horizontalLayout_23.addWidget(self.label_10)

        self.comboBox_6 = QComboBox(self.groupBox_3)
        self.comboBox_6.setObjectName(u"comboBox_6")
        self.comboBox_6.setMinimumSize(QSize(150, 0))
        self.comboBox_6.setMaximumSize(QSize(150, 16777215))

        self.horizontalLayout_23.addWidget(self.comboBox_6)

        self.frame_2 = VerticalDivider(self.groupBox_3)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.VLine)

        self.horizontalLayout_23.addWidget(self.frame_2)

        self.label_20 = QLabel(self.groupBox_3)
        self.label_20.setObjectName(u"label_20")

        self.horizontalLayout_23.addWidget(self.label_20)

        self.doubleSpinBox_2 = QDoubleSpinBox(self.groupBox_3)
        self.doubleSpinBox_2.setObjectName(u"doubleSpinBox_2")
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
        self.label_4.setObjectName(u"label_4")

        self.horizontalLayout_23.addWidget(self.label_4)

        self.doubleSpinBox = QDoubleSpinBox(self.groupBox_3)
        self.doubleSpinBox.setObjectName(u"doubleSpinBox")
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
        self.label_17.setObjectName(u"label_17")

        self.horizontalLayout_23.addWidget(self.label_17)

        self.spinBox_2 = QSpinBox(self.groupBox_3)
        self.spinBox_2.setObjectName(u"spinBox_2")
        self.spinBox_2.setMinimumSize(QSize(80, 0))
        self.spinBox_2.setMaximumSize(QSize(80, 16777215))
        self.spinBox_2.setAlignment(Qt.AlignCenter)
        self.spinBox_2.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox_2.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        self.spinBox_2.setMinimum(1)
        self.spinBox_2.setMaximum(100)

        self.horizontalLayout_23.addWidget(self.spinBox_2)

        self.horizontalSpacer_22 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_23.addItem(self.horizontalSpacer_22)


        self.verticalLayout_6.addLayout(self.horizontalLayout_23)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalSpacer_13 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_13)

        self.label_23 = QLabel(self.groupBox_3)
        self.label_23.setObjectName(u"label_23")

        self.horizontalLayout_9.addWidget(self.label_23)

        self.comboBox_5 = QComboBox(self.groupBox_3)
        self.comboBox_5.setObjectName(u"comboBox_5")
        self.comboBox_5.setMinimumSize(QSize(100, 0))
        self.comboBox_5.setMaximumSize(QSize(100, 16777215))

        self.horizontalLayout_9.addWidget(self.comboBox_5)

        self.label_22 = QLabel(self.groupBox_3)
        self.label_22.setObjectName(u"label_22")

        self.horizontalLayout_9.addWidget(self.label_22)

        self.comboBox = QComboBox(self.groupBox_3)
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setMinimumSize(QSize(380, 0))
        self.comboBox.setMaximumSize(QSize(380, 16777215))

        self.horizontalLayout_9.addWidget(self.comboBox)

        self.pushButton_3 = QPushButton(self.groupBox_3)
        self.pushButton_3.setObjectName(u"pushButton_3")
        sizePolicy.setHeightForWidth(self.pushButton_3.sizePolicy().hasHeightForWidth())
        self.pushButton_3.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_3)

        self.pushButton_17 = QPushButton(self.groupBox_3)
        self.pushButton_17.setObjectName(u"pushButton_17")

        self.horizontalLayout_9.addWidget(self.pushButton_17)

        self.pushButton_4 = QPushButton(self.groupBox_3)
        self.pushButton_4.setObjectName(u"pushButton_4")
        sizePolicy.setHeightForWidth(self.pushButton_4.sizePolicy().hasHeightForWidth())
        self.pushButton_4.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_4)

        self.pushButton_16 = QPushButton(self.groupBox_3)
        self.pushButton_16.setObjectName(u"pushButton_16")

        self.horizontalLayout_9.addWidget(self.pushButton_16)

        self.frame_5 = VerticalDivider(self.groupBox_3)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.VLine)

        self.horizontalLayout_9.addWidget(self.frame_5)

        self.pushButton_11 = QPushButton(self.groupBox_3)
        self.pushButton_11.setObjectName(u"pushButton_11")
        sizePolicy.setHeightForWidth(self.pushButton_11.sizePolicy().hasHeightForWidth())
        self.pushButton_11.setSizePolicy(sizePolicy)

        self.horizontalLayout_9.addWidget(self.pushButton_11)

        self.horizontalSpacer_14 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_9.addItem(self.horizontalSpacer_14)


        self.verticalLayout_6.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.progressBar_4 = QProgressBar(self.groupBox_3)
        self.progressBar_4.setObjectName(u"progressBar_4")
        self.progressBar_4.setMinimumSize(QSize(160, 0))
        self.progressBar_4.setMaximumSize(QSize(160, 16777215))
        self.progressBar_4.setFont(font)
        self.progressBar_4.setMaximum(1000)
        self.progressBar_4.setTextVisible(False)

        self.horizontalLayout_8.addWidget(self.progressBar_4)

        self.progressBar = QProgressBar(self.groupBox_3)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setFont(font)
        self.progressBar.setMaximum(1000)
        self.progressBar.setTextVisible(False)

        self.horizontalLayout_8.addWidget(self.progressBar)


        self.verticalLayout_6.addLayout(self.horizontalLayout_8)


        self.verticalLayout_10.addWidget(self.groupBox_3)

        self.board.addTab(self.tab_13, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.verticalLayout_21 = QVBoxLayout(self.tab_3)
        self.verticalLayout_21.setObjectName(u"verticalLayout_21")
        self.groupBox_17 = QGroupBox(self.tab_3)
        self.groupBox_17.setObjectName(u"groupBox_17")
        self.horizontalLayout_25 = QHBoxLayout(self.groupBox_17)
        self.horizontalLayout_25.setObjectName(u"horizontalLayout_25")
        self.scrollArea_8 = QScrollArea(self.groupBox_17)
        self.scrollArea_8.setObjectName(u"scrollArea_8")
        self.scrollArea_8.setWidgetResizable(True)
        self.scrollAreaWidgetContents_8 = QWidget()
        self.scrollAreaWidgetContents_8.setObjectName(u"scrollAreaWidgetContents_8")
        self.scrollAreaWidgetContents_8.setGeometry(QRect(0, 0, 1216, 611))
        self.verticalLayout_19 = QVBoxLayout(self.scrollAreaWidgetContents_8)
        self.verticalLayout_19.setObjectName(u"verticalLayout_19")
        self.verticalLayout_16 = QVBoxLayout()
        self.verticalLayout_16.setObjectName(u"verticalLayout_16")

        self.verticalLayout_19.addLayout(self.verticalLayout_16)

        self.horizontalLayout_26 = QHBoxLayout()
        self.horizontalLayout_26.setObjectName(u"horizontalLayout_26")
        self.pushButton_5 = QPushButton(self.scrollAreaWidgetContents_8)
        self.pushButton_5.setObjectName(u"pushButton_5")
        self.pushButton_5.setMinimumSize(QSize(260, 0))
        self.pushButton_5.setMaximumSize(QSize(260, 16777215))

        self.horizontalLayout_26.addWidget(self.pushButton_5)


        self.verticalLayout_19.addLayout(self.horizontalLayout_26)

        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_19.addItem(self.verticalSpacer_5)

        self.scrollArea_8.setWidget(self.scrollAreaWidgetContents_8)

        self.horizontalLayout_25.addWidget(self.scrollArea_8)


        self.verticalLayout_21.addWidget(self.groupBox_17)

        self.board.addTab(self.tab_3, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout = QVBoxLayout(self.tab_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.tabWidget = QTabWidget(self.tab_2)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab_9 = QWidget()
        self.tab_9.setObjectName(u"tab_9")
        self.verticalLayout_20 = QVBoxLayout(self.tab_9)
        self.verticalLayout_20.setObjectName(u"verticalLayout_20")
        self.horizontalLayout_34 = QHBoxLayout()
        self.horizontalLayout_34.setObjectName(u"horizontalLayout_34")
        self.horizontalSpacer_15 = QSpacerItem(323, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_34.addItem(self.horizontalSpacer_15)

        self.verticalLayout_18 = QVBoxLayout()
        self.verticalLayout_18.setObjectName(u"verticalLayout_18")
        self.verticalSpacer_6 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_18.addItem(self.verticalSpacer_6)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")

        self.verticalLayout_18.addLayout(self.horizontalLayout_13)

        self.label_26 = QLabel(self.tab_9)
        self.label_26.setObjectName(u"label_26")
        font3 = QFont()
        font3.setPointSize(3)
        self.label_26.setFont(font3)

        self.verticalLayout_18.addWidget(self.label_26)

        self.frame_9 = HorizontalDivider(self.tab_9)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setFrameShape(QFrame.HLine)

        self.verticalLayout_18.addWidget(self.frame_9)

        self.label_27 = QLabel(self.tab_9)
        self.label_27.setObjectName(u"label_27")
        self.label_27.setFont(font3)

        self.verticalLayout_18.addWidget(self.label_27)

        self.horizontalLayout_36 = QHBoxLayout()
        self.horizontalLayout_36.setObjectName(u"horizontalLayout_36")
        self.pushButton_7 = QPushButton(self.tab_9)
        self.pushButton_7.setObjectName(u"pushButton_7")
        sizePolicy.setHeightForWidth(self.pushButton_7.sizePolicy().hasHeightForWidth())
        self.pushButton_7.setSizePolicy(sizePolicy)

        self.horizontalLayout_36.addWidget(self.pushButton_7)


        self.verticalLayout_18.addLayout(self.horizontalLayout_36)

        self.verticalSpacer_7 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_18.addItem(self.verticalSpacer_7)


        self.horizontalLayout_34.addLayout(self.verticalLayout_18)

        self.horizontalSpacer_16 = QSpacerItem(324, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_34.addItem(self.horizontalSpacer_16)


        self.verticalLayout_20.addLayout(self.horizontalLayout_34)

        self.tabWidget.addTab(self.tab_9, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.verticalLayout_9 = QVBoxLayout(self.tab_4)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.scrollArea_9 = QScrollArea(self.tab_4)
        self.scrollArea_9.setObjectName(u"scrollArea_9")
        self.scrollArea_9.setWidgetResizable(True)
        self.scrollAreaWidgetContents_9 = QWidget()
        self.scrollAreaWidgetContents_9.setObjectName(u"scrollAreaWidgetContents_9")
        self.scrollAreaWidgetContents_9.setGeometry(QRect(0, 0, 752, 690))
        self.horizontalLayout_6 = QHBoxLayout(self.scrollAreaWidgetContents_9)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalSpacer_10 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_10)

        self.verticalLayout_13 = QVBoxLayout()
        self.verticalLayout_13.setObjectName(u"verticalLayout_13")
        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_13.addItem(self.verticalSpacer_2)

        self.groupBox_7 = QGroupBox(self.scrollAreaWidgetContents_9)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.groupBox_7.setMinimumSize(QSize(720, 0))
        self.groupBox_7.setMaximumSize(QSize(720, 16777215))
        self.verticalLayout_22 = QVBoxLayout(self.groupBox_7)
        self.verticalLayout_22.setObjectName(u"verticalLayout_22")
        self.verticalLayout_22.setContentsMargins(80, 40, 80, 40)
        self.label_3 = QLabel(self.groupBox_7)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setAlignment(Qt.AlignCenter)

        self.verticalLayout_22.addWidget(self.label_3)

        self.label_14 = QLabel(self.groupBox_7)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setFont(font3)

        self.verticalLayout_22.addWidget(self.label_14)

        self.frame_10 = HorizontalDivider(self.groupBox_7)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setFrameShape(QFrame.HLine)

        self.verticalLayout_22.addWidget(self.frame_10)

        self.label_43 = QLabel(self.groupBox_7)
        self.label_43.setObjectName(u"label_43")
        self.label_43.setFont(font3)

        self.verticalLayout_22.addWidget(self.label_43)

        self.horizontalLayout_18 = QHBoxLayout()
        self.horizontalLayout_18.setObjectName(u"horizontalLayout_18")
        self.horizontalSpacer_11 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_18.addItem(self.horizontalSpacer_11)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.label_5 = QLabel(self.groupBox_7)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setMinimumSize(QSize(120, 0))
        self.label_5.setMaximumSize(QSize(120, 16777215))
        self.label_5.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label_5)

        self.lineEdit = QLineEdit(self.groupBox_7)
        self.lineEdit.setObjectName(u"lineEdit")
        sizePolicy.setHeightForWidth(self.lineEdit.sizePolicy().hasHeightForWidth())
        self.lineEdit.setSizePolicy(sizePolicy)
        self.lineEdit.setMinimumSize(QSize(360, 0))
        self.lineEdit.setMaximumSize(QSize(360, 16777215))
        self.lineEdit.setAlignment(Qt.AlignCenter)
        self.lineEdit.setReadOnly(True)

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.lineEdit)

        self.pushButton_8 = QPushButton(self.groupBox_7)
        self.pushButton_8.setObjectName(u"pushButton_8")
        self.pushButton_8.setMinimumSize(QSize(360, 0))
        self.pushButton_8.setMaximumSize(QSize(360, 16777215))

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.pushButton_8)

        self.pushButton_22 = QPushButton(self.groupBox_7)
        self.pushButton_22.setObjectName(u"pushButton_22")
        self.pushButton_22.setMinimumSize(QSize(360, 0))
        self.pushButton_22.setMaximumSize(QSize(360, 16777215))

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.pushButton_22)


        self.horizontalLayout_18.addLayout(self.formLayout)

        self.horizontalSpacer_12 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_18.addItem(self.horizontalSpacer_12)


        self.verticalLayout_22.addLayout(self.horizontalLayout_18)


        self.verticalLayout_13.addWidget(self.groupBox_7)

        self.groupBox_8 = QGroupBox(self.scrollAreaWidgetContents_9)
        self.groupBox_8.setObjectName(u"groupBox_8")
        self.groupBox_8.setMinimumSize(QSize(720, 0))
        self.groupBox_8.setMaximumSize(QSize(720, 16777215))
        self.verticalLayout_29 = QVBoxLayout(self.groupBox_8)
        self.verticalLayout_29.setObjectName(u"verticalLayout_29")
        self.verticalLayout_29.setContentsMargins(80, 40, 80, 40)
        self.label_44 = QLabel(self.groupBox_8)
        self.label_44.setObjectName(u"label_44")
        self.label_44.setAlignment(Qt.AlignCenter)

        self.verticalLayout_29.addWidget(self.label_44)

        self.label_45 = QLabel(self.groupBox_8)
        self.label_45.setObjectName(u"label_45")
        self.label_45.setFont(font3)

        self.verticalLayout_29.addWidget(self.label_45)

        self.frame_12 = HorizontalDivider(self.groupBox_8)
        self.frame_12.setObjectName(u"frame_12")
        self.frame_12.setFrameShape(QFrame.HLine)

        self.verticalLayout_29.addWidget(self.frame_12)

        self.label_46 = QLabel(self.groupBox_8)
        self.label_46.setObjectName(u"label_46")
        self.label_46.setFont(font3)

        self.verticalLayout_29.addWidget(self.label_46)

        self.horizontalLayout_22 = QHBoxLayout()
        self.horizontalLayout_22.setObjectName(u"horizontalLayout_22")
        self.horizontalSpacer_19 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_22.addItem(self.horizontalSpacer_19)

        self.formLayout_3 = QFormLayout()
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.label_9 = QLabel(self.groupBox_8)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setMinimumSize(QSize(120, 0))
        self.label_9.setMaximumSize(QSize(120, 16777215))
        self.label_9.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_3.setWidget(0, QFormLayout.LabelRole, self.label_9)

        self.checkBox_12 = QCheckBox(self.groupBox_8)
        self.checkBox_12.setObjectName(u"checkBox_12")
        self.checkBox_12.setMinimumSize(QSize(360, 0))
        self.checkBox_12.setMaximumSize(QSize(360, 16777215))

        self.formLayout_3.setWidget(0, QFormLayout.FieldRole, self.checkBox_12)

        self.checkBox_13 = QCheckBox(self.groupBox_8)
        self.checkBox_13.setObjectName(u"checkBox_13")
        self.checkBox_13.setMinimumSize(QSize(360, 0))
        self.checkBox_13.setMaximumSize(QSize(360, 16777215))

        self.formLayout_3.setWidget(1, QFormLayout.FieldRole, self.checkBox_13)


        self.horizontalLayout_22.addLayout(self.formLayout_3)

        self.horizontalSpacer_20 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_22.addItem(self.horizontalSpacer_20)


        self.verticalLayout_29.addLayout(self.horizontalLayout_22)


        self.verticalLayout_13.addWidget(self.groupBox_8)

        self.groupBox_11 = QGroupBox(self.scrollAreaWidgetContents_9)
        self.groupBox_11.setObjectName(u"groupBox_11")
        self.groupBox_11.setMinimumSize(QSize(720, 0))
        self.groupBox_11.setMaximumSize(QSize(720, 16777215))
        self.verticalLayout_30 = QVBoxLayout(self.groupBox_11)
        self.verticalLayout_30.setObjectName(u"verticalLayout_30")
        self.verticalLayout_30.setContentsMargins(80, 40, 80, 40)
        self.label_47 = QLabel(self.groupBox_11)
        self.label_47.setObjectName(u"label_47")
        self.label_47.setAlignment(Qt.AlignCenter)

        self.verticalLayout_30.addWidget(self.label_47)

        self.label_48 = QLabel(self.groupBox_11)
        self.label_48.setObjectName(u"label_48")
        self.label_48.setFont(font3)

        self.verticalLayout_30.addWidget(self.label_48)

        self.frame_13 = HorizontalDivider(self.groupBox_11)
        self.frame_13.setObjectName(u"frame_13")
        self.frame_13.setFrameShape(QFrame.HLine)

        self.verticalLayout_30.addWidget(self.frame_13)

        self.label_49 = QLabel(self.groupBox_11)
        self.label_49.setObjectName(u"label_49")
        self.label_49.setFont(font3)

        self.verticalLayout_30.addWidget(self.label_49)

        self.horizontalLayout_37 = QHBoxLayout()
        self.horizontalLayout_37.setObjectName(u"horizontalLayout_37")
        self.horizontalSpacer_25 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_37.addItem(self.horizontalSpacer_25)

        self.formLayout_5 = QFormLayout()
        self.formLayout_5.setObjectName(u"formLayout_5")
        self.label_51 = QLabel(self.groupBox_11)
        self.label_51.setObjectName(u"label_51")
        self.label_51.setMinimumSize(QSize(120, 0))
        self.label_51.setMaximumSize(QSize(120, 16777215))
        self.label_51.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.formLayout_5.setWidget(0, QFormLayout.LabelRole, self.label_51)

        self.comboBox_3 = QComboBox(self.groupBox_11)
        self.comboBox_3.addItem("")
        self.comboBox_3.addItem("")
        self.comboBox_3.addItem("")
        self.comboBox_3.addItem("")
        self.comboBox_3.addItem("")
        self.comboBox_3.setObjectName(u"comboBox_3")
        self.comboBox_3.setMinimumSize(QSize(360, 0))
        self.comboBox_3.setMaximumSize(QSize(360, 16777215))

        self.formLayout_5.setWidget(0, QFormLayout.FieldRole, self.comboBox_3)


        self.horizontalLayout_37.addLayout(self.formLayout_5)

        self.horizontalSpacer_26 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_37.addItem(self.horizontalSpacer_26)


        self.verticalLayout_30.addLayout(self.horizontalLayout_37)


        self.verticalLayout_13.addWidget(self.groupBox_11)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_13.addItem(self.verticalSpacer)


        self.horizontalLayout_6.addLayout(self.verticalLayout_13)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_5)

        self.scrollArea_9.setWidget(self.scrollAreaWidgetContents_9)

        self.verticalLayout_9.addWidget(self.scrollArea_9)

        self.tabWidget.addTab(self.tab_4, "")
        self.tab_6 = QWidget()
        self.tab_6.setObjectName(u"tab_6")
        self.verticalLayout_8 = QVBoxLayout(self.tab_6)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.horizontalLayout_14 = QHBoxLayout()
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_24 = QLabel(self.tab_6)
        self.label_24.setObjectName(u"label_24")
        self.label_24.setAlignment(Qt.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_24)

        self.plainTextEdit = ScriptEditor(self.tab_6)
        self.plainTextEdit.setObjectName(u"plainTextEdit")
        self.plainTextEdit.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.verticalLayout_2.addWidget(self.plainTextEdit)


        self.horizontalLayout_14.addLayout(self.verticalLayout_2)

        self.verticalLayout_11 = QVBoxLayout()
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.label_25 = QLabel(self.tab_6)
        self.label_25.setObjectName(u"label_25")
        self.label_25.setAlignment(Qt.AlignCenter)

        self.verticalLayout_11.addWidget(self.label_25)

        self.listWidget = LogList(self.tab_6)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.listWidget.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.verticalLayout_11.addWidget(self.listWidget)


        self.horizontalLayout_14.addLayout(self.verticalLayout_11)


        self.verticalLayout_8.addLayout(self.horizontalLayout_14)

        self.groupBox_18 = QGroupBox(self.tab_6)
        self.groupBox_18.setObjectName(u"groupBox_18")
        self.verticalLayout_24 = QVBoxLayout(self.groupBox_18)
        self.verticalLayout_24.setObjectName(u"verticalLayout_24")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_6)

        self.pushButton = QPushButton(self.groupBox_18)
        self.pushButton.setObjectName(u"pushButton")

        self.horizontalLayout_2.addWidget(self.pushButton)

        self.pushButton_6 = QPushButton(self.groupBox_18)
        self.pushButton_6.setObjectName(u"pushButton_6")

        self.horizontalLayout_2.addWidget(self.pushButton_6)

        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_7)


        self.verticalLayout_24.addLayout(self.horizontalLayout_2)


        self.verticalLayout_8.addWidget(self.groupBox_18)

        self.tabWidget.addTab(self.tab_6, "")
        self.tab_7 = QWidget()
        self.tab_7.setObjectName(u"tab_7")
        self.verticalLayout_7 = QVBoxLayout(self.tab_7)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.scrollArea_6 = QScrollArea(self.tab_7)
        self.scrollArea_6.setObjectName(u"scrollArea_6")
        self.scrollArea_6.setWidgetResizable(True)
        self.scrollAreaWidgetContents_6 = QWidget()
        self.scrollAreaWidgetContents_6.setObjectName(u"scrollAreaWidgetContents_6")
        self.scrollAreaWidgetContents_6.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_6 = QGridLayout(self.scrollAreaWidgetContents_6)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.label_33 = QLabel(self.scrollAreaWidgetContents_6)
        self.label_33.setObjectName(u"label_33")
        self.label_33.setAlignment(Qt.AlignCenter)

        self.gridLayout_6.addWidget(self.label_33, 0, 0, 1, 1)

        self.scrollArea_6.setWidget(self.scrollAreaWidgetContents_6)

        self.gridLayout.addWidget(self.scrollArea_6, 1, 2, 1, 1)

        self.scrollArea_4 = QScrollArea(self.tab_7)
        self.scrollArea_4.setObjectName(u"scrollArea_4")
        self.scrollArea_4.setWidgetResizable(True)
        self.scrollAreaWidgetContents_4 = QWidget()
        self.scrollAreaWidgetContents_4.setObjectName(u"scrollAreaWidgetContents_4")
        self.scrollAreaWidgetContents_4.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_7 = QGridLayout(self.scrollAreaWidgetContents_4)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.label_35 = QLabel(self.scrollAreaWidgetContents_4)
        self.label_35.setObjectName(u"label_35")
        self.label_35.setAlignment(Qt.AlignCenter)

        self.gridLayout_7.addWidget(self.label_35, 0, 0, 1, 1)

        self.scrollArea_4.setWidget(self.scrollAreaWidgetContents_4)

        self.gridLayout.addWidget(self.scrollArea_4, 3, 1, 1, 1)

        self.scrollArea = QScrollArea(self.tab_7)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_4 = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.label_12 = QLabel(self.scrollAreaWidgetContents)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setAlignment(Qt.AlignCenter)

        self.gridLayout_4.addWidget(self.label_12, 0, 0, 1, 1)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout.addWidget(self.scrollArea, 1, 0, 1, 1)

        self.scrollArea_5 = QScrollArea(self.tab_7)
        self.scrollArea_5.setObjectName(u"scrollArea_5")
        self.scrollArea_5.setWidgetResizable(True)
        self.scrollAreaWidgetContents_5 = QWidget()
        self.scrollAreaWidgetContents_5.setObjectName(u"scrollAreaWidgetContents_5")
        self.scrollAreaWidgetContents_5.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_8 = QGridLayout(self.scrollAreaWidgetContents_5)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.label_36 = QLabel(self.scrollAreaWidgetContents_5)
        self.label_36.setObjectName(u"label_36")
        self.label_36.setAlignment(Qt.AlignCenter)

        self.gridLayout_8.addWidget(self.label_36, 0, 0, 1, 1)

        self.scrollArea_5.setWidget(self.scrollAreaWidgetContents_5)

        self.gridLayout.addWidget(self.scrollArea_5, 3, 0, 1, 1)

        self.scrollArea_3 = QScrollArea(self.tab_7)
        self.scrollArea_3.setObjectName(u"scrollArea_3")
        self.scrollArea_3.setWidgetResizable(True)
        self.scrollAreaWidgetContents_3 = QWidget()
        self.scrollAreaWidgetContents_3.setObjectName(u"scrollAreaWidgetContents_3")
        self.scrollAreaWidgetContents_3.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_5 = QGridLayout(self.scrollAreaWidgetContents_3)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.label_32 = QLabel(self.scrollAreaWidgetContents_3)
        self.label_32.setObjectName(u"label_32")
        self.label_32.setAlignment(Qt.AlignCenter)

        self.gridLayout_5.addWidget(self.label_32, 0, 0, 1, 1)

        self.scrollArea_3.setWidget(self.scrollAreaWidgetContents_3)

        self.gridLayout.addWidget(self.scrollArea_3, 1, 1, 1, 1)

        self.scrollArea_7 = QScrollArea(self.tab_7)
        self.scrollArea_7.setObjectName(u"scrollArea_7")
        self.scrollArea_7.setWidgetResizable(True)
        self.scrollAreaWidgetContents_7 = QWidget()
        self.scrollAreaWidgetContents_7.setObjectName(u"scrollAreaWidgetContents_7")
        self.scrollAreaWidgetContents_7.setGeometry(QRect(0, 0, 398, 265))
        self.gridLayout_9 = QGridLayout(self.scrollAreaWidgetContents_7)
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.label_34 = QLabel(self.scrollAreaWidgetContents_7)
        self.label_34.setObjectName(u"label_34")
        self.label_34.setAlignment(Qt.AlignCenter)

        self.gridLayout_9.addWidget(self.label_34, 0, 0, 1, 1)

        self.scrollArea_7.setWidget(self.scrollAreaWidgetContents_7)

        self.gridLayout.addWidget(self.scrollArea_7, 3, 2, 1, 1)

        self.label_37 = QLabel(self.tab_7)
        self.label_37.setObjectName(u"label_37")
        self.label_37.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_37, 0, 0, 1, 1)

        self.label_38 = QLabel(self.tab_7)
        self.label_38.setObjectName(u"label_38")
        self.label_38.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_38, 2, 0, 1, 1)

        self.label_39 = QLabel(self.tab_7)
        self.label_39.setObjectName(u"label_39")
        self.label_39.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_39, 2, 1, 1, 1)

        self.label_40 = QLabel(self.tab_7)
        self.label_40.setObjectName(u"label_40")
        self.label_40.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_40, 2, 2, 1, 1)

        self.label_41 = QLabel(self.tab_7)
        self.label_41.setObjectName(u"label_41")
        self.label_41.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_41, 0, 2, 1, 1)

        self.label_42 = QLabel(self.tab_7)
        self.label_42.setObjectName(u"label_42")
        self.label_42.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_42, 0, 1, 1, 1)

        self.gridLayout.setRowStretch(1, 1)
        self.gridLayout.setRowStretch(3, 1)
        self.gridLayout.setColumnStretch(0, 1)
        self.gridLayout.setColumnStretch(1, 1)
        self.gridLayout.setColumnStretch(2, 1)

        self.verticalLayout_7.addLayout(self.gridLayout)

        self.tabWidget.addTab(self.tab_7, "")

        self.verticalLayout.addWidget(self.tabWidget)

        self.board.addTab(self.tab_2, "")

        self.gridLayout_3.addWidget(self.board, 0, 0, 1, 1)

        self.gauge = QLabel(self.centralwidget)
        self.gauge.setObjectName(u"gauge")
        self.gauge.setAlignment(Qt.AlignCenter)

        self.gridLayout_3.addWidget(self.gauge, 5, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.board.setCurrentIndex(0)
        self.comboBox.setCurrentIndex(-1)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Solie", None))
        self.pushButton_9.setText(QCoreApplication.translate("MainWindow", u"Support the Solie project \u2665", None))
        self.pushButton_2.setText(QCoreApplication.translate("MainWindow", u"Fill candle data", None))
        self.pushButton_13.setText(QCoreApplication.translate("MainWindow", u"\u2630", None))
        self.board.setTabText(self.board.indexOf(self.tab_5), QCoreApplication.translate("MainWindow", u"Collect", None))
        self.checkBox_2.setText(QCoreApplication.translate("MainWindow", u"Draw frequently", None))
        self.pushButton_14.setText(QCoreApplication.translate("MainWindow", u"Display last 24 hours", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Graph coin", None))
        self.label_21.setText(QCoreApplication.translate("MainWindow", u"Strategy", None))
        self.checkBox.setText(QCoreApplication.translate("MainWindow", u"Auto-transact", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"API key", None))
        self.label_18.setText(QCoreApplication.translate("MainWindow", u"Secret key", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Leverage", None))
        self.spinBox.setPrefix(QCoreApplication.translate("MainWindow", u"\u00d7", None))
        self.pushButton_12.setText(QCoreApplication.translate("MainWindow", u"\u2630", None))
        self.board.setTabText(self.board.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"Transact", None))
        self.checkBox_3.setText(QCoreApplication.translate("MainWindow", u"Draw all years", None))
        self.pushButton_15.setText(QCoreApplication.translate("MainWindow", u"Display selected year", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"Graph coin", None))
        self.label_20.setText(QCoreApplication.translate("MainWindow", u"Maker fee", None))
        self.doubleSpinBox_2.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Taker fee", None))
        self.doubleSpinBox.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.label_17.setText(QCoreApplication.translate("MainWindow", u"Leverage", None))
        self.spinBox_2.setPrefix(QCoreApplication.translate("MainWindow", u"\u00d7", None))
        self.label_23.setText(QCoreApplication.translate("MainWindow", u"Year", None))
        self.label_22.setText(QCoreApplication.translate("MainWindow", u"Strategy", None))
        self.pushButton_3.setText(QCoreApplication.translate("MainWindow", u"Calculate", None))
        self.pushButton_17.setText(QCoreApplication.translate("MainWindow", u"Draw", None))
        self.pushButton_4.setText(QCoreApplication.translate("MainWindow", u"Erase", None))
        self.pushButton_16.setText(QCoreApplication.translate("MainWindow", u"Forget", None))
        self.pushButton_11.setText(QCoreApplication.translate("MainWindow", u"\u2630", None))
        self.board.setTabText(self.board.indexOf(self.tab_13), QCoreApplication.translate("MainWindow", u"Simulate", None))
        self.pushButton_5.setText(QCoreApplication.translate("MainWindow", u"Add", None))
        self.board.setTabText(self.board.indexOf(self.tab_3), QCoreApplication.translate("MainWindow", u"Strategize", None))
        self.pushButton_7.setText(QCoreApplication.translate("MainWindow", u"Open documentation", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_9), QCoreApplication.translate("MainWindow", u"About", None))
        self.groupBox_7.setTitle("")
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Data folder", None))
        self.label_14.setText("")
        self.label_43.setText("")
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Path", None))
        self.pushButton_8.setText(QCoreApplication.translate("MainWindow", u"Open with file manager", None))
        self.pushButton_22.setText(QCoreApplication.translate("MainWindow", u"Change", None))
        self.groupBox_8.setTitle("")
        self.label_44.setText(QCoreApplication.translate("MainWindow", u"System stability", None))
        self.label_45.setText("")
        self.label_46.setText("")
        self.label_9.setText("")
        self.checkBox_12.setText(QCoreApplication.translate("MainWindow", u"Match system time with Binance server", None))
        self.checkBox_13.setText(QCoreApplication.translate("MainWindow", u"Disable system's auto update", None))
        self.groupBox_11.setTitle("")
        self.label_47.setText(QCoreApplication.translate("MainWindow", u"Convenience", None))
        self.label_48.setText("")
        self.label_49.setText("")
        self.label_51.setText(QCoreApplication.translate("MainWindow", u"Lock the window", None))
        self.comboBox_3.setItemText(0, QCoreApplication.translate("MainWindow", u"Never", None))
        self.comboBox_3.setItemText(1, QCoreApplication.translate("MainWindow", u"After 10 seconds", None))
        self.comboBox_3.setItemText(2, QCoreApplication.translate("MainWindow", u"After 1 minute", None))
        self.comboBox_3.setItemText(3, QCoreApplication.translate("MainWindow", u"After 10 minutes", None))
        self.comboBox_3.setItemText(4, QCoreApplication.translate("MainWindow", u"After 1 hour", None))

        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_4), QCoreApplication.translate("MainWindow", u"Settings", None))
        self.label_24.setText(QCoreApplication.translate("MainWindow", u"Python script", None))
        self.label_25.setText(QCoreApplication.translate("MainWindow", u"Log output", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"Run script", None))
        self.pushButton_6.setText(QCoreApplication.translate("MainWindow", u"Deselect log", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_6), QCoreApplication.translate("MainWindow", u"Logs", None))
        self.label_33.setText("")
        self.label_35.setText("")
        self.label_12.setText("")
        self.label_36.setText("")
        self.label_32.setText("")
        self.label_34.setText("")
        self.label_37.setText(QCoreApplication.translate("MainWindow", u"Async tasks", None))
        self.label_38.setText(QCoreApplication.translate("MainWindow", u"Number of transactions inside latest candle", None))
        self.label_39.setText(QCoreApplication.translate("MainWindow", u"Binance API usage and limits", None))
        self.label_40.setText(QCoreApplication.translate("MainWindow", u"(Preserved)", None))
        self.label_41.setText(QCoreApplication.translate("MainWindow", u"Task durations", None))
        self.label_42.setText(QCoreApplication.translate("MainWindow", u"Process pool", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_7), QCoreApplication.translate("MainWindow", u"Status", None))
        self.board.setTabText(self.board.indexOf(self.tab_2), QCoreApplication.translate("MainWindow", u"Manage", None))
        self.gauge.setText("")
    # retranslateUi

