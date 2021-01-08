#!/usr/bin/env python3.6
# -*- coding: UTF-8 -*-

from OPCDataTransfer import ConnectionOPC
from OPCDataTransfer import Simulation
from OPCDataTransfer import Visualization
from OPCDataTransfer.ServiceFunctions import ArgParser
from OPCDataTransfer import ConfParser
import time


def start_writing_data_to_opc_server(conf_settings):
    plotting_required = conf_settings['plotting_required']

    # establish a client connection with OPC server
    with ConnectionOPC(conf_settings) as opc_client:

        # initialize simulation model
        model_parameters = Simulation.SimulationParameters()
        simulation_model = Simulation.SimulationModel(model_parameters.facility_controllers_parameters_settings,
                                                      model_parameters.facility_simulation_settings,
                                                      model_parameters.facility_settings)

        # initialize diagram
        if plotting_required:
            data_figure = Visualization.DataFigure(opc_client.get_codes_plotting_names_dict(),
                                                   opc_client.get_opc_names_codes_dict(),
                                                   conf_settings['diagram_split_keys'],
                                                   conf_settings['diagram_series_len'])

        current_time = conf_settings['simulation_start_time']
        simulation_time_step = conf_settings['simulation_time_step']
        while True:
            # generate new data from simulation model
            simulation_model.make_model_iteration(current_time)

            # send data to OPC server
            list_opc_data = opc_client.convert_simulation_data_to_opc_data(
                 simulation_model.get_current_controller_parameters_values_list())
            opc_client.write(list_opc_data)

            # display data on diagram
            if plotting_required:
                data_figure.plot_top_values_from_history_list(simulation_model.get_data_history_list())

            current_time += simulation_time_step
            time.sleep(opc_client.get_frequency())


def main():
    # parse startup parameters from the command line
    args_namespace = ArgParser().get_namespace()
    # read the run settings file
    conf_settings = ConfParser(args_namespace.settings_file_path).get_settings()

    start_writing_data_to_opc_server(conf_settings)


if __name__ == '__main__':
    main()
