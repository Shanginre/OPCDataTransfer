#!/usr/bin/env python3.6
# -*- coding: UTF-8 -*-

from OPCDataTransfer import ConnectionOPC
from OPCDataTransfer import Loader
from OPCDataTransfer import LoaderType
from OPCDataTransfer import Visualization
from OPCDataTransfer.ServiceFunctions import ArgParser
from OPCDataTransfer import ConfParser
import time


def start_transfer_data_from_opc_server(conf_settings):
    plotting_required = conf_settings['plotting_required']

    # establish client connections with OPC server and data receiver
    with ConnectionOPC(conf_settings) as opc_client, \
            Loader(LoaderType.CLICKHOUSE_DRIVER, conf_settings, opc_client.get_parameters_name_string()) as loader:

        # initialize diagram
        if plotting_required:
            data_figure = Visualization.DataFigure(opc_client.get_codes_plotting_names_dict(),
                                                   opc_client.get_opc_names_codes_dict(),
                                                   conf_settings['diagram_split_keys'],
                                                   conf_settings['diagram_series_len'])
            data_history_list = list()

        loader.create_session()
        loader.connect()
        while True:
            # get current data from OPC server
            param_list = opc_client.get_list_of_current_values()

            # send the received data to the receiver (http service, database, etc.)
            loader.load_data(param_list)

            # display data on diagram
            if plotting_required:
                data_history_list.extend(param_list)
                data_figure.plot_top_values_from_history_list(data_history_list)

            time.sleep(opc_client.get_frequency())


def main():
    # parse startup parameters from the command line
    args_namespace = ArgParser().get_namespace()
    # read the run settings file
    conf_settings = ConfParser(args_namespace.settings_file_path).get_settings()

    start_transfer_data_from_opc_server(conf_settings)


if __name__ == '__main__':
    main()
