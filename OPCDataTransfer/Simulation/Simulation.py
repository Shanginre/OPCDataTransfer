# -*- coding: UTF-8 -*-

import numpy as np
import time
import copy
from OPCDataTransfer.ServiceFunctions import Parameters
from OPCDataTransfer.ServiceFunctions import StatParams


class SimulationModel:
    def __init__(self, facility_controller_parameter_settings, facility_controller_cumulated_statistics_settings,
                 facility_settings):
        self._time = None
        self._time_previous = None
        self._facility_controller_parameter_settings = dict()
        self._facility_controller_cumulated_statistics_settings = dict()
        self._facility_settings = dict()
        self._current_controller_parameters_values = dict()
        self._last_current_controller_parameters_values = dict()
        self._accumulated_statistics_values = dict()
        self._current_facility_parameters_values = dict()
        self._current_facility_component_state = dict()
        self._current_facility_state = dict()
        self._facility_component_structure = dict()
        self._facility_component_statistics_structure = dict()
        self._data_history_list = list()

        self._facility_settings = facility_settings
        self._facility_controller_parameter_settings = facility_controller_parameter_settings
        self._facility_controller_cumulated_statistics_settings = facility_controller_cumulated_statistics_settings

        for key in facility_controller_parameter_settings:
            # key - ('facility_id, component_id, controller_parameter)
            # structure to store the current values of controllers sensors
            self._current_controller_parameters_values[key] = \
                {'value': None, 'time_last_state_change': None, 'state_fixed_interval': None, 'now_jumping': False}
            # structure to store the past values of controllers sensors (to calculate the gain)
            self._last_current_controller_parameters_values[key] = None

        for key in facility_controller_cumulated_statistics_settings:
            # key - ('facility_id, component_id, cumulated_parameter)
            # structure to store the accumulated statistical data of controllers sensors
            self._accumulated_statistics_values[key] = None

        for key in facility_controller_cumulated_statistics_settings:
            # key - ('facility_id, component_id, cumulated_parameter)
            key_facility_component = (key[0], key[1])
            if key_facility_component not in self._current_facility_component_state:
                # structure to store the current state of a specific node
                self._current_facility_component_state[key_facility_component] = {'breakdown': None, 'have_faulty': None}
                # structure to store the binding of the accumulated data parameter to a facility nodes
                self._facility_component_statistics_structure[key_facility_component] = []
            self._facility_component_statistics_structure.get(key_facility_component).append(key[2])

        for key in facility_settings:
            # structure to store the current state of facilities
            self._current_facility_state[key] = {'running': None,
                                                 'state_fixed_interval': None,
                                                 'time_last_state_change': None,
                                                 'breakdown': None,
                                                 'time_last_breakdown': None}

        for key in self._current_facility_component_state:
            # key - ('facility_id, component_id)
            # structure for storing the binding of nodes to facilities
            key_facility = key[0]
            structure_list = self._facility_component_structure.setdefault(key_facility, [])
            structure_list.append(key[1])

    def _add_simulation_data_to_history_list(self):
        self._data_history_list.extend(self.get_current_controller_parameters_values_list())

    def get_data_history_list(self):
        return self._data_history_list

    def make_model_iteration(self, current_time=None):
        self._set_time(current_time)

        # Let's calculate the accumulated values of the parameters on which the failure in the nodes depends
        for key, value in self._accumulated_statistics_values.items():
            self._compute_new_facility_component_statistics(key, value)

        for key, value in self._current_facility_component_state.items():
            self._compute_new_facility_component_state(key, value)

        for key, value in self._current_facility_state.items():
            self._compute_new_facility_state(key, value)

        # remember the current state so that the _compute_new_current_parameters_values method can access to the current
        # and previous value
        current_controller_parameters_values_deepcopy = copy.deepcopy(self._current_controller_parameters_values)

        # update current values
        for key, value in self._current_controller_parameters_values.items():
            self._compute_new_current_parameters_values(key, value)

        # the current values have been updated. keep the previous values
        for key, value in current_controller_parameters_values_deepcopy.items():
            self._compute_last_current_controller_parameters_values(key, value)

        self._add_simulation_data_to_history_list()

    def get_current_controller_parameters_values_list(self):
        current_values_list = list()
        for key, state_dict in self._current_controller_parameters_values.items():
            # key - ('facility_id, component_id, controller_parameter)
            current_value_dict = {'facility': key[0], 'component': key[1], 'parameter': key[2].value,
                                  'value': state_dict.get('value'), 'time': self._time}
            current_values_list.append(current_value_dict)
        return current_values_list

    def _set_time(self, current_time):
        # set the time. We can generate data as in current time mode (default),
        # and for generating historical data
        if current_time is None:
            self._time_previous = self._time
            self._time = time.time()
        else:
            self._time_previous = self._time
            self._time = current_time

    def _compute_new_facility_component_statistics(self, key, value):
        if value is None:
            # Setting the initial values of statistics parameters for facilities nodes
            self._refresh_component_statistics(key[0], key[1], key[2])
            return

        cumulated_parameter = key[2]
        if cumulated_parameter == StatParams.TIME_WORKED:
            # if the equipment is working, then we write the amount of time that it worked in the statistics data
            if self._current_facility_state.get(key[0]).get('running'):
                period = self._time - self._time_previous
                self._accumulated_statistics_values[key] = value + period
        elif cumulated_parameter == StatParams.TOTAL_OVERLOAD_POWER_TIME:
            self._compute_total_component_statistics_with_type_overload(key, value,
                                                                        Parameters.POWER_CONSUMPTION)
        elif cumulated_parameter == StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME:
            self._compute_total_component_statistics_with_type_overload(key, value,
                                                                        Parameters.TEMPERATURE)
        elif cumulated_parameter == StatParams.TOTAL_TEMPERATURE_JUMPS:
            self._compute_total_component_statistics_with_type_jumps(key, value,
                                                                     Parameters.TEMPERATURE)
        elif cumulated_parameter == StatParams.TOTAL_VIBRATION_JUMPS:
            self._compute_total_component_statistics_with_type_jumps(key, value,
                                                                     Parameters.VIBRATION)

    def _compute_new_facility_component_state(self, key, dict_state):
        # Based on the accumulated statistics of facilities nodes, we compute the presence of damage
        # or total damage of nodes
        parameters_list = self._facility_component_statistics_structure.get(key)
        have_faulty = 0
        have_breakdown = 0
        for parameter in parameters_list:
            value = self._accumulated_statistics_values.get((key[0], key[1], parameter))
            faulty, breakdown = self._compute_new_facility_component_probabilities_failure(
                (key[0], key[1], parameter), value)
            if faulty:
                have_faulty = 1
            if breakdown:
                have_breakdown = 1
        dict_state['have_faulty'] = have_faulty
        dict_state['breakdown'] = have_breakdown

    def _compute_new_facility_state(self, key_facility, dict_state):
        if dict_state.get('running') is None:
            dict_state['running'] = self._make_decision_running_or_stop_facility(key_facility)
            self._set_facility_state_change_values(key_facility, dict_state)
            dict_state['breakdown'] = 0
        else:
            if dict_state.get('breakdown'):
                # the facility is already broken. Let's check if it has already been repaired
                time_last_breakdown = self._current_facility_state.get(key_facility).get('time_last_breakdown')
                time_repair = self._facility_settings.get(key_facility).get('time_repair')
                if (self._time - time_last_breakdown) >= time_repair:
                    # The facility was repaired. We launch the facility and update statistics on it
                    dict_state['running'] = 1
                    self._set_facility_state_change_values(key_facility, dict_state)
                    dict_state['breakdown'] = 0
                    # We will get the facility nodes that were broken
                    component_breakdown_list = self._get_failed_components(key_facility)
                    for component in component_breakdown_list:
                        self._refresh_component_statistics(key_facility, component)
            else:
                if dict_state.get('running'):
                    # if the facility is working, we analyze the state of the facility nodes.
                    # If at least one node is broken, then the entire facility fails.
                    component_breakdown_list = self._get_failed_components(key_facility)
                    if component_breakdown_list:
                        dict_state['running'] = 0
                        dict_state['breakdown'] = 1
                        dict_state['time_last_breakdown'] = self._time

                # change the facility state with a given probability
                if not dict_state.get('breakdown'):
                    time_last_state_change = dict_state.get('time_last_state_change')
                    time_interval_without_change = dict_state.get('state_fixed_interval')
                    if (self._time - time_last_state_change) >= time_interval_without_change:
                        decision_state = self._make_decision_running_or_stop_facility(key_facility)
                        if not decision_state == dict_state.get('running'):
                            dict_state['running'] = decision_state
                            self._set_facility_state_change_values(key_facility, dict_state)

    def _compute_new_current_parameters_values(self, key, dict_state):
        dict_settings = self._facility_controller_parameter_settings.get(key)

        if dict_state.get('value') is None:
            value_distribution = dict_settings.get('value_distribution')
            dict_state['value'] = self._get_random_value_with_distribution(value_distribution)
            self._set_controller_parameter_state_change_values(key, dict_state)
        else:
            # Get the state of the node
            component_state = self._current_facility_component_state.get((key[0], key[1]))
            facility_state = self._current_facility_state.get(key[0])
            if facility_state.get('running'):
                if component_state.get('have_faulty'):
                    # works, but there is a problem.
                    new_value = self._compute_new_value_controller_parameter(
                        key, dict_settings, dict_state, dict_settings.get('probability_jump_faulty'))
                    dict_state['value'] = new_value
                    self._set_controller_parameter_state_change_values(key, dict_state)
                else:
                    # works fine. We change the value in the planned mode
                    time_last_state_change = dict_state.get('time_last_state_change')
                    state_fixed_interval = dict_state.get('state_fixed_interval')
                    if (self._time - time_last_state_change) >= state_fixed_interval:
                        # we can change the parameter value
                        new_value = self._compute_new_value_controller_parameter(
                            key, dict_settings, dict_state, dict_settings.get('probability_jump'))
                        dict_state['value'] = new_value
                        self._set_controller_parameter_state_change_values(key, dict_state)
            else:
                # does not work. Or turned off according to plan, or there is a fault
                # the values of all parameters are rapidly decreasing
                new_value = self._compute_new_value_controller_parameter(
                    key, dict_settings, dict_state, 0, (0, 0))
                dict_state['value'] = new_value

    def _compute_last_current_controller_parameters_values(self, key, value_dict):
        current_value = value_dict.get('value')
        self._last_current_controller_parameters_values[key] = current_value

    def _set_facility_state_change_values(self, key_facility, dict_state):
        time_running_distribution = self._facility_settings.get(key_facility).get('time_running_distribution')
        self._set_state_change_values(time_running_distribution, dict_state)

    def _set_controller_parameter_state_change_values(self, key, dict_state):
        state_fixed_distribution = self._facility_controller_parameter_settings.get(key).get('state_fixed_distribution')
        self._set_state_change_values(state_fixed_distribution, dict_state)

    def _set_state_change_values(self, distribution, dict_state):
        dict_state['time_last_state_change'] = self._time
        dict_state['state_fixed_interval'] = self._get_random_value_with_distribution(distribution)

    def _get_failed_components(self, key_facility):
        component_list = self._facility_component_structure.get(key_facility)
        component_breakdown_list = []
        for component in component_list:
            if self._current_facility_component_state.get((key_facility, component)).get('breakdown'):
                component_breakdown_list.append(component)
        return component_breakdown_list

    def _refresh_component_statistics(self, key_facility, component, parameter_name=None):
        component_state_dict = self._current_facility_component_state.get((key_facility, component))
        if parameter_name == 'breakdown' or parameter_name is None:
            component_state_dict['breakdown'] = 0
        if parameter_name == 'breakdown' or parameter_name is None:
            component_state_dict['have_faulty'] = 0

        if parameter_name == StatParams.TIME_WORKED or parameter_name is None:
            self._accumulated_statistics_values[
                (key_facility, component, StatParams.TIME_WORKED)] = 0

        if parameter_name == StatParams.TOTAL_OVERLOAD_POWER_TIME or parameter_name is None:
            self._accumulated_statistics_values[
                (key_facility, component, StatParams.TOTAL_OVERLOAD_POWER_TIME)] = 0

        if parameter_name == StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME or parameter_name is None:
            self._accumulated_statistics_values[
                (key_facility, component, StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME)] = 0

        if parameter_name == StatParams.TOTAL_TEMPERATURE_JUMPS or parameter_name is None:
            self._accumulated_statistics_values[
                (key_facility, component, StatParams.TOTAL_TEMPERATURE_JUMPS)] = 0

        if parameter_name == StatParams.TOTAL_VIBRATION_JUMPS or parameter_name is None:
            self._accumulated_statistics_values[
                (key_facility, component, StatParams.TOTAL_VIBRATION_JUMPS)] = 0

    def _compute_total_component_statistics_with_type_overload(self, key, value, parameter):
        settings = self._facility_controller_parameter_settings.get(
                (key[0], key[1], parameter))
        if settings is not None:
            # some parameters for the node may not be available
            normal_value_upper_bound = settings.get('normal_value_upper_bound')
            current_value = self._current_controller_parameters_values. \
                get((key[0], key[1], parameter)).get('value')
            if current_value > normal_value_upper_bound:
                period = self._time - self._time_previous
                self._accumulated_statistics_values[key] = value + period

    def _compute_total_component_statistics_with_type_jumps(self, key, value, parameter):
        # a jump will be considered the excess of the current value over the previous one
        # by more than jump_value_upper_bound times
        jump_value_upper_bound = self._facility_controller_parameter_settings.get(
            (key[0], key[1], parameter)).get('jump_value_upper_bound')
        last_value = self._last_current_controller_parameters_values.\
            get((key[0], key[1], parameter))
        current_value = self._current_controller_parameters_values. \
            get((key[0], key[1], parameter)).get('value')
        increase = 0
        if last_value is not None:
            if last_value > 0 and current_value > last_value:
                increase = current_value / last_value - 1
        if increase > jump_value_upper_bound:
            self._accumulated_statistics_values[key] = value + 1

    def _compute_new_facility_component_probabilities_failure(self, key, current_value):
        # 'distribution_parameters_faulty': (threshold_faulty, smoothness_change),
        # 'distribution_parameters_breakdown': (threshold_breakdown, smoothness_change),
        dict_setting = self._facility_controller_cumulated_statistics_settings.get(key)
        distribution_parameters_faulty = dict_setting.get('distribution_parameters_faulty')
        distribution_parameters_breakdown = dict_setting.get('distribution_parameters_breakdown')
        faulty = self._make_decision_failure_or_not(current_value, distribution_parameters_faulty)
        breakdown = self._make_decision_failure_or_not(current_value, distribution_parameters_breakdown)
        return faulty, breakdown

    @staticmethod
    def _get_probability_with_distribution(current_value, distribution, function_type):
        threshold = distribution[0]
        smoothness = distribution[1]
        if function_type == 'log':
            value_for_exp = (threshold - current_value) * smoothness
            # overflow error for very large exponent values
            if value_for_exp < 100:
                probability = 1 / (1 + np.exp(value_for_exp))
            else:
                probability = 0

            return probability
        # elif

    @staticmethod
    def _get_random_value_with_distribution(distribution, function_type='normal'):
        if function_type == 'normal':
            return max(0, np.random.normal(distribution[0], distribution[1]))

    @staticmethod
    def _make_decision_on_probability(probability):
        decision = 1
        random = np.random.random()
        if random > probability:
            decision = 0
        return decision

    def _make_decision_failure_or_not(self, current_value, distribution):
        probability = self._get_probability_with_distribution(current_value, distribution, 'log')
        decision = self._make_decision_on_probability(probability)
        return decision

    def _make_decision_running_or_stop_facility(self, key_facility):
        probability = self._facility_settings.get(key_facility).get('probability_running')
        decision_run = self._make_decision_on_probability(probability)
        return decision_run

    def _compute_new_value_controller_parameter(self, key, dict_settings, dict_state, probability_jump,
                                                value_distribution=None):
        if value_distribution is None:
            value_distribution = dict_settings.get('value_distribution')

        if dict_state['now_jumping']:
            # the jump is only one-time. After the jump, we must return to the previous regime
            dict_state['now_jumping'] = False
            current_value = self._last_current_controller_parameters_values.get(key)
        else:
            current_value = dict_state.get('value')

        # calculate the increment of the parameter value on which the current parameter depends.
        # It can be greater than 1 or less than 1.if = 1, then the value has not changed
        increment_of_main_parameter = self._compute_increment_of_main_parameter(dict_settings)

        new_value = self._get_random_value_with_distribution(value_distribution)
        new_value_debug = new_value
        # adjust the new value so that the time series is even
        diff = (new_value * increment_of_main_parameter - current_value) * dict_settings.get('speed_change')
        new_value = max(current_value + diff, 0)
        if new_value > 1000:
            print(new_value_debug)

        # make a jump with probability
        if self._make_decision_on_probability(probability_jump):
            new_value *= dict_settings.get('jump_value')
            dict_state['now_jumping'] = True
            print('jump ' + str(probability_jump))

        return new_value

    def _compute_increment_of_main_parameter(self, dict_settings):
        dependence = dict_settings.get('dependence')
        dependence_parameter_key = dependence[0]
        dependence_value = dependence[1]

        if dependence_parameter_key is None:
            increment = 1
        else:
            last_value = self._last_current_controller_parameters_values.get(dependence_parameter_key)
            current_value = self._current_controller_parameters_values.get(dependence_parameter_key).get('value')

            if last_value == 0 or last_value is None:
                increment = 1
            else:
                # Can increase by no more than 2 times
                increment = min((current_value / last_value - 1) * dependence_value + 1, 2)

        return increment


class SimulationParameters:
    def __init__(self):
        self.facility_controllers_parameters_settings = self.set_facility_controllers_parameters_settings()
        self.facility_simulation_settings = self.set_facility_simulation_settings()
        self.facility_settings = self.set_facility_settings()
        self.facility_location = self.set_facility_location()

    @staticmethod
    def set_facility_controllers_parameters_settings():
        structure = dict()

        # Задаем параметры для узлов станка 1001. Токарный станок CS6150
        # https://16k20.ru/catalog/tokarnye-stanki/CS6150-CS6150B-CS6150C-CS6250-CS6250B-CS6250C/
        # Узел 10011 - главный двигатель
        structure[1001, 10011, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(7.4, 1), normal_value_upper_bound=8)
        structure[1001, 10011, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1001, 10011, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1001, 10011, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1001, 10011, Parameters.POWER_CONSUMPTION))

        # 10012 - двигатель ускоренных перемещений по осям
        structure[1001, 10012, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(0.25, 0.05), normal_value_upper_bound=0.3)
        structure[1001, 10012, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1001, 10012, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1001, 10012, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1001, 10012, Parameters.POWER_CONSUMPTION))

        # 10013 - двигателя быстрого хода
        structure[1001, 10013, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(0.25, 0.05), normal_value_upper_bound=0.3)
        structure[1001, 10013, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1001, 10013, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1001, 10013, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1001, 10013, Parameters.POWER_CONSUMPTION))

        # 10014 - насос для охлаждающей жидкости
        structure[1001, 10014, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(0.05, 0.03), normal_value_upper_bound=0.1)
        structure[1001, 10014, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, value_distribution=(70, 5), normal_value_upper_bound=90,
            dependence_parameter=(1001, 10014, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1001, 10014, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1001, 10014, Parameters.POWER_CONSUMPTION))

        # 10015 - подшипник шпиндель
        structure[1001, 10015, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1001, 10011, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1001, 10015, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1001, 10011, Parameters.POWER_CONSUMPTION))

        # Задаем параметры для узлов станка 1002. Токарный станок C61100
        # https://16k20.ru/catalog/tokarnye-stanki/C61100/
        # Узел 10021 - Двигатель шпинделя
        structure[1002, 10021, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(22, 5), normal_value_upper_bound=25)
        structure[1002, 10021, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE,  dependence_parameter=(1002, 10021, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1002, 10021, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1002, 10021, Parameters.POWER_CONSUMPTION))

        # 10022 - двигатель ускоренных перемещений по осям
        structure[1002, 10022, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(1.5, 0.5), normal_value_upper_bound=1.7)
        structure[1002, 10022, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1002, 10022, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1002, 10022, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1002, 10022, Parameters.POWER_CONSUMPTION))

        # 10023 - помпа охлаждения
        structure[1002, 10023, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(0.15, 0.05), normal_value_upper_bound=0.18)
        structure[1002, 10023, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1002, 10023, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1002, 10023, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1002, 10023, Parameters.POWER_CONSUMPTION))

        # 10024 - подшипник шпиндель
        structure[1002, 10024, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1002, 10023, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1002, 10024, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1002, 10023, Parameters.POWER_CONSUMPTION))

        # Задаем параметры для узлов станка 1003. Широкоуниверсальный фрезерный станок X6232Cx16
        # https://16k20.ru/catalog/frezernye-stanki/X6232Cx16/
        # Узел 10031 - двигатель вертикального шпинделя
        structure[1003, 10031, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(3, 1), normal_value_upper_bound=4)
        structure[1003, 10031, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1003, 10031, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1003, 10031, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1003, 10031, Parameters.POWER_CONSUMPTION))

        # 10032 - двигателя горизонтального шпинделя
        structure[1003, 10032, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(5.5, 1), normal_value_upper_bound=7)
        structure[1003, 10032, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1003, 10032, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1003, 10032, Parameters.VIBRATION] = \
            SimulationParameters.add_settings_for_parameter(
                Parameters.VIBRATION, dependence_parameter=(1003, 10032, Parameters.POWER_CONSUMPTION))

        # 10033 - помпа охлаждения
        structure[1003, 10033, Parameters.POWER_CONSUMPTION] = SimulationParameters.add_settings_for_parameter(
            Parameters.POWER_CONSUMPTION, value_distribution=(0.125, 0.05), normal_value_upper_bound=0.15)
        structure[1003, 10033, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1003, 10033, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1003, 10033, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1003, 10033, Parameters.POWER_CONSUMPTION))

        # 10034 - подшипник шпиндель
        structure[1003, 10034, Parameters.TEMPERATURE] = SimulationParameters.add_settings_for_parameter(
            Parameters.TEMPERATURE, dependence_parameter=(1003, 10031, Parameters.POWER_CONSUMPTION), speed_change=0.3)
        structure[1003, 10034, Parameters.VIBRATION] = SimulationParameters.add_settings_for_parameter(
            Parameters.VIBRATION, dependence_parameter=(1003, 10031, Parameters.POWER_CONSUMPTION))

        return structure

    @staticmethod
    def add_settings_for_parameter(controller_parameter,  value_distribution=None, normal_value_upper_bound=None,
                                   dependence_parameter=None, dependence_value=0.9, speed_change=None):
        probability_jump = 0.01
        probability_jump_faulty = 0.4
        jump_value = 1.5
        jump_value_upper_bound = 0.3
        state_fixed_distribution = (20, 3)
        if speed_change is None:
            speed_change = 0.6
        if controller_parameter == Parameters.POWER_CONSUMPTION:
            if value_distribution is None:
                value_distribution = (7.4, 0.4)
            if normal_value_upper_bound is None:
                normal_value_upper_bound = 8
        elif controller_parameter == Parameters.TEMPERATURE:
            if value_distribution is None:
                value_distribution = (70, 10)
            if normal_value_upper_bound is None:
                normal_value_upper_bound = 100
        elif controller_parameter == Parameters.VIBRATION:
            if value_distribution is None:
                value_distribution = (400, 20)
            if normal_value_upper_bound is None:
                normal_value_upper_bound = 500
        structure = {'value_distribution': value_distribution, 'normal_value_upper_bound': normal_value_upper_bound,
                     'jump_value_upper_bound': jump_value_upper_bound, 'jump_value': jump_value,
                     'probability_jump': probability_jump, 'probability_jump_faulty': probability_jump_faulty,
                     'state_fixed_distribution': state_fixed_distribution, 'speed_change': speed_change,
                     'dependence': (dependence_parameter, dependence_value)}
        return structure

    @staticmethod
    def add_simulation_parameters(structure, facility_id, component_id, multiplier):
        structure[facility_id, component_id, StatParams.TIME_WORKED] = SimulationParameters\
            .get_settings_for_simulation_parameter(StatParams.TIME_WORKED, multiplier)
        structure[facility_id, component_id, StatParams.TOTAL_OVERLOAD_POWER_TIME] = SimulationParameters\
            .get_settings_for_simulation_parameter(StatParams.TOTAL_OVERLOAD_POWER_TIME, multiplier)
        structure[facility_id, component_id, StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME] = SimulationParameters\
            .get_settings_for_simulation_parameter(StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME, multiplier)
        structure[facility_id, component_id, StatParams.TOTAL_TEMPERATURE_JUMPS] = SimulationParameters\
            .get_settings_for_simulation_parameter(StatParams.TOTAL_TEMPERATURE_JUMPS, multiplier)
        structure[facility_id, component_id, StatParams.TOTAL_VIBRATION_JUMPS] = SimulationParameters\
            .get_settings_for_simulation_parameter(StatParams.TOTAL_VIBRATION_JUMPS, multiplier)

    @staticmethod
    def set_facility_simulation_settings():
        structure = dict()

        # Задаем параметры для узлов станка 1001. Токарный станок CS6150
        # Узел 10011 - главный двигатель
        SimulationParameters.add_simulation_parameters(structure, 1001, 10011, 1)
        # 10012 - двигатель ускоренных перемещений по осям
        SimulationParameters.add_simulation_parameters(structure, 1001, 10012, 1)
        # 10013 - двигателя быстрого хода
        SimulationParameters.add_simulation_parameters(structure, 1001, 10013, 1)
        # 10014 - насос для охлаждающей жидкости
        SimulationParameters.add_simulation_parameters(structure, 1001, 10014, 1)
        # 10015 - подшипник шпиндель
        SimulationParameters.add_simulation_parameters(structure, 1001, 10015, 1)

        # Задаем параметры для узлов станка 1002. Токарный станок C61100
        # Узел 10021 - Двигатель шпинделя
        SimulationParameters.add_simulation_parameters(structure, 1002, 10021, 1)
        # 10022 - двигатель ускоренных перемещений по осям
        SimulationParameters.add_simulation_parameters(structure, 1002, 10022, 1)
        # 10023 - помпа охлаждения
        SimulationParameters.add_simulation_parameters(structure, 1002, 10023, 1)
        # 10024 - подшипник шпиндель
        SimulationParameters.add_simulation_parameters(structure, 1002, 10024, 1)

        # Задаем параметры для узлов станка 1003. Широкоуниверсальный фрезерный станок X6232Cx16
        # Узел 10031 - двигатель вертикального шпинделя
        SimulationParameters.add_simulation_parameters(structure, 1003, 10031, 1)
        # 10032 - двигателя горизонтального шпинделя
        SimulationParameters.add_simulation_parameters(structure, 1003, 10032, 1)
        # 10033 - помпа охлаждения
        SimulationParameters.add_simulation_parameters(structure, 1003, 10033, 1)
        # 10034 - подшипник шпиндель
        SimulationParameters.add_simulation_parameters(structure, 1003, 10034, 1)

        return structure

    @staticmethod
    def get_settings_for_simulation_parameter(parameter, multiplier):
        faulty = (0, 0)
        breakdown = (0, 0)
        if parameter == StatParams.TIME_WORKED:
            faulty = (864000 * multiplier, 0.3)
            breakdown = (1728000 * multiplier, 0.3)
        elif parameter == StatParams.TOTAL_OVERLOAD_POWER_TIME:
            faulty = (3600 * multiplier, 0.5)
            breakdown = (7200 * multiplier, 0.5)
        elif parameter == StatParams.TOTAL_OVERLOAD_TEMPERATURE_TIME:
            faulty = (3600 * multiplier, 0.5)
            breakdown = (7200 * multiplier, 0.5)
        elif parameter == StatParams.TOTAL_TEMPERATURE_JUMPS:
            faulty = (30 * multiplier, 0.5)
            breakdown = (50 * multiplier, 0.5)
        elif parameter == StatParams.TOTAL_VIBRATION_JUMPS:
            faulty = (30 * multiplier, 0.5)
            breakdown = (50 * multiplier, 0.5)

        return {'distribution_parameters_faulty': faulty, 'distribution_parameters_breakdown': breakdown}

    @staticmethod
    def set_facility_settings():
        structure = dict()
        structure[1001] = {'probability_running': 0.8, 'time_running_distribution': (580, 30), 'time_repair': 240}
        structure[1002] = {'probability_running': 0.7, 'time_running_distribution': (420, 30), 'time_repair': 300}
        structure[1003] = {'probability_running': 0.6, 'time_running_distribution': (320, 30), 'time_repair': 300}

        return structure

    @staticmethod
    def set_facility_location():
        structure = dict()
        structure[1001] = {'department': 1, 'area': 1}
        structure[1002] = {'department': 1, 'area': 2}
        structure[1003] = {'department': 2, 'area': 3}

        return structure
