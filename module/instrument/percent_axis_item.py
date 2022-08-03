import math

from pyqtgraph import AxisItem

from module.recipe import simply_format


class PercentAxisItem(AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tickValues(self, min_value, max_value, size):  # noqa:N802

        min_value = max(0.001 * max_value, min_value)

        min_power = math.ceil(math.log(min_value, 1.01))
        max_power = math.floor(math.log(max_value, 1.01))

        major_ticks = [1.01**i for i in range(min_power, max_power + 1)]

        minor_ticks = []
        factors = [1 + i * 0.001 for i in range(1, 10)]
        for power in range(min_power - 1, max_power + 1):
            for factor in factors:
                new_tick = factor * 1.01**power
                if min_value < new_tick < max_value:
                    minor_ticks.append(new_tick)

        return [
            (max_value - min_value, major_ticks),
            (max_value - min_value, minor_ticks),
        ]

    def tickStrings(self, tick_values, scale, spacing):  # noqa:N802

        optimal_count = max(2, math.ceil(self.size().height() / 20))
        distance = spacing / optimal_count

        strings = []

        if len(tick_values) > 0:
            next_condition = tick_values[0]
            for tick_value in tick_values:
                if tick_value >= next_condition:
                    next_condition = tick_value + distance
                    string = simply_format.fixed_float(tick_value, 6)
                    strings.append(string)
                else:
                    strings.append("")

        return strings
