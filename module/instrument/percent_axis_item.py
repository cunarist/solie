import math

from pyqtgraph import AxisItem

from module.recipe import simply_format


class PercentAxisItem(AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._oldAxis = None
        self.fixedWidth = 15

    def tickValues(self, min_value, max_value, size):  # noqa:N802

        min_value = max(0.001 * max_value, min_value)

        if max_value / min_value < 1.02:
            basepower = math.floor(math.log(min_value, 1.001))
            morepower = math.ceil(math.log(max_value / min_value, 1.001)) + 1
            tick_values = [1.001 ** (i + basepower) for i in range(morepower)]
            tick_values = [i for i in tick_values if min_value < i < max_value]
            return [(max_value - min_value, tick_values)]
        else:
            basepower = math.floor(math.log(min_value, 1.01))
            morepower = math.ceil(math.log(max_value / min_value, 1.01)) + 1
            tick_values = [1.01 ** (i + basepower) for i in range(morepower)]
            tick_values = [i for i in tick_values if min_value < i < max_value]
            return [(max_value - min_value, tick_values)]

    def tickStrings(self, tick_values, scale, spacing):  # noqa:N802

        optimal_count = max(2, math.ceil(self.size().height() / 40))
        tick_count = len(tick_values)

        if tick_count == 0:
            return []

        else:
            distance = spacing / optimal_count
            next_condition = self.range[0]
            next_condition += distance / 2
            strings = []
            for tick_value in tick_values:
                if tick_value > next_condition:
                    next_condition += distance
                    string = simply_format.fixed_float(tick_value, 6)
                    strings.append(string)
                else:
                    strings.append("")
            return strings
