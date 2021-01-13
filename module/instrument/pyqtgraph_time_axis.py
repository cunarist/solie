#!/usr/bin/env python

#############################################################################
#
# This file was adapted from Taurus TEP17, but all taurus dependencies were
# removed so that it works with just pyqtgraph
#
# Just run it and play with the zoom to see how the labels and tick positions
# automatically adapt to the shown range
#
#############################################################################
# http://taurus-scada.org
#
# Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
#
# Taurus is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Taurus is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

"""
This module provides date-time aware axis
"""

import math
from datetime import datetime, timedelta, timezone

from pyqtgraph import AxisItem


class DateAxisItem(AxisItem):
    """
    A tool that provides a date-time aware axis. It is implemented as an
    AxisItem that interpretes positions as unix timestamps (i.e. seconds
    since 1970).
    The labels and the tick positions are dynamically adjusted depending
    on the range.
    It provides a  :meth:`attach_to_plot_item` method to add it to a given
    PlotItem
    """

    def __init__(self, *args, **kwargs):
        AxisItem.__init__(self, *args, **kwargs)
        self._oldAxis = None

    def tickValues(self, min_value, max_value, size):  # noqa:N802
        """
        Reimplemented from PlotItem to adjust to the range and to force
        the ticks at "round" positions in the context of time units instead of
        rounding in a decimal base
        """

        if min_value <= 0:  # use standard implementation from parent
            return AxisItem.tickValues(self, min_value, max_value, size)

        dt1 = datetime.fromtimestamp(min_value, tz=timezone.utc)
        dt2 = datetime.fromtimestamp(max_value, tz=timezone.utc)

        dx = max_value - min_value
        majticks = []

        if dx > 3600 * 24 * (365 + 366):  # 2 years (count leap year)
            distance = timedelta(days=366)
            for year in range(dt1.year + 1, dt2.year + 1):
                dt = datetime(year=year, month=1, day=1, tzinfo=timezone.utc)
                majticks.append(dt.timestamp())

        elif dx > 3600 * 24 * 61:  # 61 days
            distance = timedelta(days=31)
            dt = (
                dt1.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + distance
            )
            while dt < dt2:
                # make sure that we are on day 1 (even if always sum 31 days)
                dt = dt.replace(day=1)
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 3600 * 24 * 2:  # 2 days
            distance = timedelta(days=1)
            dt = dt1.replace(hour=0, minute=0, second=0, microsecond=0) + distance
            while dt < dt2:
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 3600 * 2:  # 2hours
            distance = timedelta(hours=1)
            dt = dt1.replace(minute=0, second=0, microsecond=0) + distance
            while dt < dt2:
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 1200:  # 20 minutes
            distance = timedelta(minutes=10)
            dt = (
                dt1.replace(minute=(dt1.minute // 10) * 10, second=0, microsecond=0)
                + distance
            )
            while dt < dt2:
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 120:  # 2 minutes
            distance = timedelta(minutes=1)
            dt = dt1.replace(second=0, microsecond=0) + distance
            while dt < dt2:
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 20:  # 20s
            distance = timedelta(seconds=10)
            dt = dt1.replace(second=(dt1.second // 10) * 10, microsecond=0) + distance
            while dt < dt2:
                majticks.append(dt.timestamp())
                dt += distance

        elif dx > 2:  # 2s
            distance = timedelta(seconds=1)
            majticks = range(int(min_value), int(max_value))

        else:  # <2s , use standard implementation from parent
            return AxisItem.tickValues(self, min_value, max_value, size)

        return [(distance.total_seconds(), majticks)]

    def tickStrings(self, tick_values, scale, spacing):  # noqa:N802
        """Reimplemented from PlotItem to adjust to the range"""

        count = len(tick_values)
        sample = 1
        if count > 12:
            sample = math.ceil((count / 12))
        offset = math.floor((count % sample) / 2)
        return_data = []

        if not tick_values:
            return []

        if spacing >= 31622400:  # 366 days
            fmt = "%Y"

        elif spacing >= 2678400:  # 31 days
            fmt = "%Y-%m"

        elif spacing >= 86400:  # = 1 day
            fmt = "%m-%d"

        elif spacing >= 3600:  # 1 h
            fmt = "%m-%d %H:00"

        elif spacing >= 60:  # 1 m
            fmt = "%m-%d %H:%M"

        elif spacing >= 1:  # 1s
            fmt = "%m-%d %H:%M:%S"

        else:
            # less than 2s (show microseconds)
            # fmt = '%S.%f"'
            fmt = "[+%fms]"  # explicitly relative to last second

        for turn, tick_value in enumerate(tick_values):
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

    def attach_to_plot_item(self, plot_item):
        """Add this axis to the given PlotItem
        :param plot_item: (PlotItem)
        """
        self.setParentItem(plot_item)
        viewbox = plot_item.getViewBox()
        self.linkToView(viewbox)
        self._oldAxis = plot_item.axes[self.orientation]["item"]
        self._oldAxis.hide()
        plot_item.axes[self.orientation]["item"] = self
        pos = plot_item.axes[self.orientation]["pos"]
        plot_item.layout.addItem(self, *pos)
        self.setZValue(-1000)
