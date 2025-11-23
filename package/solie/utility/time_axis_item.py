import math
from datetime import datetime, timedelta, timezone
from typing import override

from pyqtgraph import AxisItem

from .constants import (
    MAX_TICK_LABELS,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    SECONDS_PER_MONTH,
    SECONDS_PER_YEAR,
    TWENTY_MINUTES,
    TWENTY_SECONDS,
    TWO_MINUTES,
    TWO_SECONDS,
)

# We're not using pyqtgraph's default DateAxisItem
# because it doesn't show values in UTC time.


class TimeAxisItem(AxisItem):
    @override
    def tickValues(
        self,
        minVal: float,  # noqa
        maxVal: float,  # noqa
        size: float,
    ) -> list[tuple[float, list[float]]]:
        """Calculate tick values based on time range."""
        min_value = minVal
        max_value = maxVal

        if min_value <= 0:  # use standard implementation from parent
            return AxisItem.tickValues(self, min_value, max_value, size)

        dt1 = datetime.fromtimestamp(min_value, tz=timezone.utc)
        dt2 = datetime.fromtimestamp(max_value, tz=timezone.utc)
        box_seconds = (max_value - min_value) / size * 1000

        majticks = self._calculate_major_ticks(dt1, dt2, box_seconds)

        if not majticks:  # use standard implementation from parent
            return AxisItem.tickValues(self, min_value, max_value, size)

        return [(1, majticks)]

    def _calculate_major_ticks(
        self, dt1: datetime, dt2: datetime, box_seconds: float
    ) -> list[float]:
        """Calculate major tick positions based on time scale."""
        # Define time ranges and their corresponding tick generators
        time_ranges = [
            (3600 * 24 * (365 + 366), self._yearly_ticks),  # 2 years
            (3600 * 24 * 61, self._monthly_ticks),  # 61 days
            (3600 * 24 * 2, self._daily_ticks),  # 2 days
            (3600 * 2, self._hourly_ticks),  # 2 hours
            (TWENTY_MINUTES, self._ten_minute_ticks),  # 20 minutes
            (TWO_MINUTES, self._minute_ticks),  # 2 minutes
            (TWENTY_SECONDS, self._ten_second_ticks),  # 20 seconds
            (TWO_SECONDS, self._second_ticks),  # 2 seconds
        ]

        for threshold, tick_generator in time_ranges:
            if box_seconds > threshold:
                return tick_generator(dt1, dt2)

        return []

    def _yearly_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for yearly intervals."""
        majticks = []
        for year in range(dt1.year + 1, dt2.year + 1):
            dt = datetime(year=year, month=1, day=1, tzinfo=timezone.utc)
            majticks.append(dt.timestamp())
        return majticks

    def _monthly_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for monthly intervals."""
        majticks = []
        distance = timedelta(days=31)
        dt = dt1.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + distance
        while dt < dt2:
            dt = dt.replace(day=1)
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _daily_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for daily intervals."""
        majticks = []
        distance = timedelta(days=1)
        dt = dt1.replace(hour=0, minute=0, second=0, microsecond=0) + distance
        while dt < dt2:
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _hourly_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for hourly intervals."""
        majticks = []
        distance = timedelta(hours=1)
        dt = dt1.replace(minute=0, second=0, microsecond=0) + distance
        while dt < dt2:
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _ten_minute_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for 10-minute intervals."""
        majticks = []
        distance = timedelta(minutes=10)
        dt = (
            dt1.replace(minute=(dt1.minute // 10) * 10, second=0, microsecond=0)
            + distance
        )
        while dt < dt2:
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _minute_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for minute intervals."""
        majticks = []
        distance = timedelta(minutes=1)
        dt = dt1.replace(second=0, microsecond=0) + distance
        while dt < dt2:
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _ten_second_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for 10-second intervals."""
        majticks = []
        distance = timedelta(seconds=10)
        dt = dt1.replace(second=(dt1.second // 10) * 10, microsecond=0) + distance
        while dt < dt2:
            majticks.append(dt.timestamp())
            dt += distance
        return majticks

    def _second_ticks(self, dt1: datetime, dt2: datetime) -> list[float]:
        """Generate ticks for second intervals."""
        min_value = dt1.timestamp()
        max_value = dt2.timestamp()
        return list(range(int(min_value), int(max_value)))

    @override
    def tickStrings(
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        """Reimplemented from PlotItem to adjust to the range"""
        if not values:
            return []

        # Calculate sampling if too many ticks
        count = len(values)
        sample, offset = self._calculate_sampling(count)

        # Determine format based on spacing
        fmt = self._determine_time_format(spacing)

        # Generate tick strings
        return self._generate_tick_strings(values, fmt, sample, offset)

    def _calculate_sampling(self, count: int) -> tuple[int, int]:
        """Calculate sampling rate and offset for tick labels."""
        sample = 1
        if count > MAX_TICK_LABELS:
            sample = math.ceil(count / MAX_TICK_LABELS)
        offset = math.floor((count % sample) / 2)
        return sample, offset

    def _determine_time_format(self, spacing: float) -> str:
        """Determine time format string based on spacing."""
        # Define spacing ranges and their corresponding formats
        format_ranges = [
            (SECONDS_PER_YEAR, "%Y"),  # 366 days
            (SECONDS_PER_MONTH, "%Y-%m"),  # 31 days
            (SECONDS_PER_DAY, "%m-%d"),  # 1 day
            (SECONDS_PER_HOUR, "%m-%d %H:00"),  # 1 hour
            (SECONDS_PER_MINUTE, "%m-%d %H:%M"),  # 1 minute
            (1, "%m-%d %H:%M:%S"),  # 1 second
        ]

        for threshold, fmt in format_ranges:
            if spacing >= threshold:
                return fmt

        return "[+%fms]"  # explicitly relative to last second

    def _generate_tick_strings(
        self, values: list[float], fmt: str, sample: int, offset: int
    ) -> list[str]:
        """Generate formatted tick strings from values."""
        return_data: list[str] = []

        for turn, tick_value in enumerate(values):
            if (turn - offset) % sample == 0:
                try:
                    tick_time = datetime.fromtimestamp(tick_value, tz=timezone.utc)
                    return_data.append(tick_time.strftime(fmt))
                except (ValueError, OSError):
                    # Windows can't handle dates before 1970
                    return_data.append("")
            else:
                return_data.append("")

        return return_data
