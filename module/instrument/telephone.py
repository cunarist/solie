from PyQt6 import QtCore


class Telephone(QtCore.QObject):
    # pqtSignal 인스턴스는 QObject의 클래스 속성이어야 한다는
    # PyQt의 이상한 규칙 때문에 필요함
    signal = QtCore.pyqtSignal(object, object, object, object)
