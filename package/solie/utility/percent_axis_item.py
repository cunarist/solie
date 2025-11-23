import math
from typing import override

from pyqtgraph import AxisItem


class PercentAxisItem(AxisItem):
    @override
    def tickValues(
        self,
        minVal: float,  # noqa
        maxVal: float,  # noqa
        size: float,
    ) -> list[tuple[float, list[float]]]:
        min_value = minVal
        max_value = maxVal
        min_value = max(0.001 * max_value, min_value)

        min_power = math.ceil(math.log(min_value, 1.01))
        max_power = math.floor(math.log(max_value, 1.01))

        major_ticks = [1.01**i for i in range(min_power, max_power + 1)]

        minor_ticks: list[float] = []
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

    @override
    def tickStrings(
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        optimal_count = max(2, math.ceil(self.size().height() / 20))
        distance = spacing / optimal_count

        strings: list[str] = []

        if len(values) > 0:
            next_condition = values[0]
            for tick_value in values:
                if tick_value >= next_condition:
                    next_condition = tick_value + distance
                    string = self.format_fixed_float(tick_value, 6)
                    strings.append(string)
                else:
                    strings.append("")

        return strings

    def format_fixed_float(self, number: float, width=4, positive_sign=False) -> str:
        width = max(width, 4)

        if number < 0 or (positive_sign and number >= 0):
            # when sign should be included
            absolute_limit = 10 ** (width - 1)
        else:
            absolute_limit = 10**width

        if abs(number) >= absolute_limit:
            number = absolute_limit - 1 if number > 0 else -absolute_limit + 1

        string = f"{number:12.12f}"

        if positive_sign and number >= 0:
            string = "+" + string

        string = string[:width]

        return string
