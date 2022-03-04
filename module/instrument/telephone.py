from PyQt6 import QtCore


class Telephone(QtCore.QObject):
    # pqtSignal instance needs to be a class attribute of QObject
    signal = QtCore.pyqtSignal(object, object, object, object)
