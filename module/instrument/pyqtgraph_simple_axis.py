from pyqtgraph import AxisItem


class SimpleAxisItem(AxisItem):
    def attach_to_plot_item(self, plot_item):
        self.setParentItem(plot_item)
        viewbox = plot_item.getViewBox()
        self.linkToView(viewbox)
        self._oldAxis = plot_item.axes[self.orientation]["item"]
        self._oldAxis.hide()
        plot_item.axes[self.orientation]["item"] = self
        pos = plot_item.axes[self.orientation]["pos"]
        plot_item.layout.addItem(self, *pos)
        self.setZValue(-1000)
