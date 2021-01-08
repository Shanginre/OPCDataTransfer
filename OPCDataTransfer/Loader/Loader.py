# -*- coding: UTF-8 -*-

from enum import Enum
from OPCDataTransfer.Loader import ClickHouseQueries
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout
from clickhouse_driver import Client as ClickHouse_client
from clickhouse_driver.errors import SocketTimeoutError
from builtins import print
import logging


class LoaderType(Enum):
    HTTP = 1
    KAFKA = 2
    CLICKHOUSE_DRIVER = 3


class Loader:
    def __init__(self, sender_type, conf_settings, parameters_name_string):
        self._debug = None
        self._logger = None
        self._verbose = None
        self._type = None
        self._destination = None
        self._user = None
        self._password = None
        self._database = None
        self._table = None
        self._clickhouse_table_create_query = None
        self._session = None
        self._parameters_name_string = None

        self._debug = conf_settings['debug']
        self._set_logger(conf_settings)
        self._verbose = conf_settings['verbose']
        self._type = sender_type
        self._destination = conf_settings['host']
        self._user = conf_settings['user'] if conf_settings['user'] else 'default'
        self._password = conf_settings['password'] if conf_settings['password'] else ''
        self._database = conf_settings['database_name'] if conf_settings['database_name'] else 'default'
        self._table = conf_settings['table_name'] if conf_settings['table_name'] else 'facility_sensor_logs'
        self._clickhouse_table_create_query = conf_settings['clickhouse_table_create_query']
        self._parameters_name_string = parameters_name_string

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._type == LoaderType.HTTP:
            self._session.close()
            self._print('HTTP session has been closed')
        elif self._type == LoaderType.CLICKHOUSE_DRIVER:
            self._session.disconnect()
            self._print('ClickHouse session has been closed')

    def _print(self, message):
        if self._verbose:
            print(message)
        if self._debug:
            self._logger.info(message)

    def create_session(self):
        if self._type == LoaderType.HTTP:
            self._session = requests.Session()
            self._print('HTTP session created')
        elif self._type == LoaderType.CLICKHOUSE_DRIVER:
            self._session = ClickHouse_client(host=self._destination,
                                              user=self._user,
                                              password=self._password,
                                              database=self._database)
            self._print('ClickHouse client session created')

    def connect(self):
        if self._type == LoaderType.HTTP:
            http_adapter = HTTPAdapter(max_retries=3)
            self._session.mount(self._destination, http_adapter)
        elif self._type == LoaderType.CLICKHOUSE_DRIVER:
            try:
                ClickHouseQueries.create_database_if_not_exists(self._session, self._database)
                ClickHouseQueries.create_table_if_not_exists(self._session,
                                                             self._clickhouse_table_create_query)
            except SocketTimeoutError as ste:
                self._print('ClickHouse SocketTimeoutError ' + str(ste))

    def load_data(self, data):
        if not data:
            return

        if self._type == LoaderType.HTTP:
            try:
                self._session.post(self._destination, json=data, timeout=5)
                self._print('send ' + str(len(data)) + ' values by HTTP')
            except Timeout:
                self._print('The request timed out')
            except ConnectionError as ce:
                self._print(ce)
        elif self._type == LoaderType.CLICKHOUSE_DRIVER:
            try:
                ClickHouseQueries.insert_values_into_table(self._session,
                                                           self._database,
                                                           self._table,
                                                           data,
                                                           self._parameters_name_string)
                self._print('insert ' + str(len(data)) + ' values into ClickHouse table')
            except SocketTimeoutError as ste:
                self._print('ClickHouse SocketTimeoutError ' + str(ste))

    def _set_logger(self, conf_settings):
        if self._debug:
            logs_filename = conf_settings['logs_file_path'] if conf_settings['logs_file_path'] else 'logs.log'
            debug_level = conf_settings['debug_level'] if conf_settings['debug_level'] else 'DEBUG'
            logging.basicConfig(level=logging.getLevelName(debug_level),
                                format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                                filename=logs_filename)
            self._logger = logging.getLogger(__name__)
