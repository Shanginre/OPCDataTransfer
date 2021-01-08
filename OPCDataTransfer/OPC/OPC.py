#!/usr/bin/env python3.6
# -*- coding: UTF-8 -*-

import OpenOPC
import pywintypes
import datetime
from builtins import print
import json
import copy
import logging
import os


class ConnectionOPC:

    def __init__(self, conf_settings):
        self._debug = None
        self._logger = None
        self._verbose = None
        self._frequency = None
        self._client = None
        self._param_list = None
        self._dict_codes_plotting_names = None
        self._dict_opc_names_codes = None
        self._dict_code_keys_opc_names = None
        self._parameters_name_string = None

        self._debug = conf_settings['debug']
        self._set_logger(conf_settings)
        self._verbose = conf_settings['verbose']
        self._set_frequency(conf_settings)

        self._set_opc_client(conf_settings['opc_server'])

        # get a list of all parameter names from the OPC server
        self._param_list = self._client.list(conf_settings['tags_branch_opc_server'], recursive=True)
        # get dictionaries of tag codes and their OPC names
        tags_settings_dicts = self._get_settings_dicts(conf_settings)
        self._set_dict_codes_plotting_names(tags_settings_dicts['codes_and_plotting_names'])
        self._dict_opc_names_codes = tags_settings_dicts['opc_names_and_codes']
        self._set_dict_code_keys_opc_names()
        self._set_parameters_name_string()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        groups = self._client.groups()
        self._client.remove(copy.deepcopy(list(groups)))
        self._client.close()
        self._print('OPC client close the connection')

    def write(self, list_data_string):
        try:
            self._client.write(list_data_string)
        except OpenOPC.TimeoutError:
            self._print("Timeout error OPC occured")

    def _print(self, message):
        if self._verbose:
            print(message)
        if self._debug:
            self._logger.info(message)

    def get_list_of_current_values(self):
        current_date_string = datetime.datetime.now()
        param_array = list()
        try:
            if not self._client.groups():
                # Read 1 times the values and determine the group of opc tags, which will continue to use
                for name, value, quality, timeRecord in self._client.iread(self._param_list, group='Group0', update=1):
                    param_array.append(self._get_dict_from_opc_data(name, value, current_date_string))
            else:
                for name, value, quality, timeRecord in self._client.iread(group='Group0', update=1):
                    param_array.append(self._get_dict_from_opc_data(name, value, current_date_string))

            if self._debug or self._verbose:
                self._print('Data has been read from the OPC')
                for item in param_array:
                    self._print(item)
        except OpenOPC.TimeoutError:
            self._print("OPC TimeoutError occured")

        return param_array

    def convert_simulation_data_to_opc_data(self, current_values_list):
        list_opc_values = list()
        for value_dict in current_values_list:
            cur_time = value_dict.pop('time', None)
            cur_value = value_dict.pop('value', None)

            opc_tag_name = self._get_opc_tag_name(value_dict)

            list_opc_values.append((opc_tag_name, cur_value))

            if self._debug or self._verbose:
                self._print((opc_tag_name, cur_value, cur_time))
        return list_opc_values

    def _set_opc_client(self, opc_server_name):
        pywintypes.datetime = pywintypes.TimeType
        self._client = OpenOPC.client()
        self._client.connect(opc_server_name)
        self._print('connected to OPC server ' + opc_server_name)

    def _set_logger(self, conf_settings):
        if self._debug:
            logs_file_path = conf_settings['logs_file_path']
            if not logs_file_path:
                logs_file_path = os.path.abspath(
                    os.path.realpath(
                        os.path.join(os.path.dirname(os.path.realpath(__file__)), '../Data/logs.log')))

            debug_level_string = conf_settings['debug_level']
            if debug_level_string:
                debug_level = logging.getLevelName(debug_level_string)
            else:
                debug_level = logging.DEBUG

            logging.basicConfig(level=debug_level,
                                format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                                filename=logs_file_path)
            self._logger = logging.getLogger(__name__)

    def _set_frequency(self, conf_settings):
        frequency = conf_settings['frequency']
        if frequency is None:
            self._frequency = 5
            self._print('data refresh rate is set by default ' + str(self._frequency))
        else:
            self._frequency = frequency

    def get_frequency(self):
        return self._frequency

    @staticmethod
    def _get_settings_dicts(conf_settings):
        # TODO in production, preferably an HTTP request
        tags_settings_file_path = conf_settings['tags_settings_file_path']
        if not tags_settings_file_path:
            tags_settings_file_path = os.path.abspath(
                os.path.realpath(
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), '../Data/tags_settings_sample.json')))

        with open(tags_settings_file_path, 'r') as read_file:
            tags_settings_dicts = json.load(read_file)

        return tags_settings_dicts

    def _set_dict_codes_plotting_names(self, dict_codes_plotting_names):
        dict_with_tuple_keys = dict()
        for tag_name, list_codes_plotting_names in dict_codes_plotting_names.items():
            for code_plotting_name_dict in list_codes_plotting_names:
                dict_with_tuple_keys[(tag_name, code_plotting_name_dict['key'])] = code_plotting_name_dict['value']
        self._dict_codes_plotting_names = dict_with_tuple_keys

    def _set_dict_code_keys_opc_names(self):
        dict_with_tuple_keys = dict()
        for opc_name, codes_dict in self._dict_opc_names_codes.items():
            dict_with_tuple_keys[self._get_sorted_tuple_values_from_dict(codes_dict)] = opc_name
        self._dict_code_keys_opc_names = dict_with_tuple_keys

    def get_codes_plotting_names_dict(self):
        return self._dict_codes_plotting_names

    def get_opc_names_codes_dict(self):
        return self._dict_opc_names_codes

    def _get_dict_from_opc_data(self, parameter_name, value, current_date_string):
        dict_param_value = {**self._dict_opc_names_codes.get(parameter_name),
                            'value': value,
                            'time': current_date_string}
        return dict_param_value

    @staticmethod
    def _get_sorted_tuple_values_from_dict(_dict):
        values_list = list()
        for k in sorted(_dict.keys()):
            values_list.append(_dict[k])
        return tuple(values_list)

    def _get_opc_tag_name(self, value_dict):
        keys_tuple = self._get_sorted_tuple_values_from_dict(value_dict)
        return self._dict_code_keys_opc_names.get(keys_tuple)

    def _set_parameters_name_string(self):
        if self._dict_opc_names_codes:
            dict_codes_first_value = next(iter(self._dict_opc_names_codes.values()))
            self._parameters_name_string = ','.join(list(dict_codes_first_value.keys())) + ',value,time'
        else:
            self._parameters_name_string = ''

    def get_parameters_name_string(self):
        return self._parameters_name_string
