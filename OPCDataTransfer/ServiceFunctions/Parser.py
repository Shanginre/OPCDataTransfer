# -*- coding: UTF-8 -*-

import argparse
import configparser
import datetime


class ArgParser:
    def __init__(self):
        self._parser = argparse.ArgumentParser()
        self._parser.add_argument('--settings_file_path', '-s', required=True,
                                  help='path to the file with program launch settings')
        self.namespace = self._parser.parse_args()

    def get_namespace(self):
        return self.namespace


class ConfParser:
    def __init__(self, path):
        self.path = path
        self._config = configparser.ConfigParser(allow_no_value=True)

    def get_settings(self):
        self._config.read(self.path)

        dict_settings = dict()
        for section in self._config.sections():
            for option in self._config.options(section):
                dict_settings[option] = self._get_option_value(section, option)
        dict_settings['config_file_path'] = self.path

        return dict_settings

    def _get_option_value(self, section, option):
        if option == 'frequency':
            return self._config.getfloat(section, option)
        elif option == 'plotting_required':
            return self._config.getboolean(section, option)
        elif option == 'diagram_series_len':
            return self._config.getint(section, option)
        elif option == 'verbose':
            return self._config.getboolean(section, option)
        elif option == 'debug':
            return self._config.getboolean(section, option)
        elif option == 'simulation_start_time':
            time_value = _parse_iso_datetime(self._config.get(section, option))
            return _datetime_to_float(time_value)
        elif option == 'simulation_time_step':
            return self._config.getint(section, option)
        else:
            return self._config.get(section, option).strip()


def _parse_iso_datetime(iso_time_string):
    return datetime.datetime.strptime(iso_time_string, '%Y-%m-%dT%H:%M:%S.%f')


def _datetime_to_float(time_value):
    return time_value.timestamp()
