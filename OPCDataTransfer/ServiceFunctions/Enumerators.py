# -*- coding: UTF-8 -*-

from enum import Enum


class ControllerParametersEnum(Enum):
    POWER_CONSUMPTION = 1
    TEMPERATURE = 2
    VIBRATION = 3


class StatisticsParametersEnum(Enum):
    TIME_WORKED = 1  # The amount of time (while the equipment is running) that the equipment unit worked after repair
    TOTAL_OVERLOAD_POWER_TIME = 2
    TOTAL_OVERLOAD_TEMPERATURE_TIME = 3
    TOTAL_TEMPERATURE_JUMPS = 4
    TOTAL_VIBRATION_JUMPS = 5
