from PySide6 import QtCore


class Telephone(QtCore.QObject):
    # Signal instance needs to be a class attribute of QObject
    signal = QtCore.Signal(object, object, object, object)
