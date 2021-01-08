# -*- coding: UTF-8 -*-

import matplotlib.pyplot as plt
from OPCDataTransfer.Visualization import ArrayFunctions


class DataFigure:

    def __init__(self, codes_plotting_names_dict, opc_names_codes_dict, diagram_split_keys_string, diagram_series_len):
        self._diagram_split_keys_name_list = list()
        self._diagram_series_name_list = list()
        self._diagram_split_keys_relations = dict()
        self._figure = None
        self._split_keys_axes = None
        self._facility_keys_axes = None
        self._codes_plotting_names_dict = None
        self._x_points_number_in_history_list = None

        plt.ion()

        self._set_diagram_split_keys_name_list(diagram_split_keys_string)
        self._set_diagram_series_name_list(opc_names_codes_dict)
        self._set_diagram_split_keys_relations(opc_names_codes_dict)
        diagram_split_keys_list_of_tuples = list(self._diagram_split_keys_relations.keys())

        fig, axes = plt.subplots(nrows=len(diagram_split_keys_list_of_tuples))
        self._figure = fig
        # bind axes to diagram_split_keys
        self._split_keys_axes = dict(zip(diagram_split_keys_list_of_tuples, axes))

        self._codes_plotting_names_dict = codes_plotting_names_dict
        self._x_points_number_in_history_list = diagram_series_len * len(opc_names_codes_dict)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        plt.close()

    def _set_diagram_split_keys_name_list(self, diagram_split_keys_string):
        self._diagram_split_keys_name_list = diagram_split_keys_string.replace(' ', '').split(',')

    def _set_diagram_series_name_list(self, dict_opc_names_codes):
        if dict_opc_names_codes:
            dict_codes_first_value = next(iter(dict_opc_names_codes.values()))
            self._diagram_series_name_list = sorted(list(set(dict_codes_first_value.keys())
                                                         - set(self._diagram_split_keys_name_list)))

    def _set_diagram_split_keys_relations(self, dict_opc_names_codes):
        dataframe = ArrayFunctions.list_of_structures_to_pandas_dataframe(list(dict_opc_names_codes.values()))
        dataframe = ArrayFunctions.reorder_columns_in_dataframe(dataframe, self._diagram_split_keys_name_list
                                                                + self._diagram_series_name_list)
        dataframe = dataframe[self._diagram_split_keys_name_list + self._diagram_series_name_list]
        keys_dataframe = ArrayFunctions.find_unique_keys_in_dataframe(dataframe, self._diagram_split_keys_name_list)
        keys_list_dicts = keys_dataframe.to_dict('records')
        relations_dict = dict()
        for keys_dict in keys_list_dicts:
            filtered_dataframe = ArrayFunctions.select_rows_in_dataframe_by_dict(dataframe, keys_dict)
            relations_dict[tuple(keys_dict.values())] = filtered_dataframe.to_dict('records')
        self._diagram_split_keys_relations = relations_dict

    def plot_top_values_from_history_list(self, data_history_list):
        if not data_history_list:
            return

        dataframe = ArrayFunctions.list_of_structures_to_pandas_dataframe(
                    ArrayFunctions.get_last_n_rows_in_list(data_history_list, self._x_points_number_in_history_list))
        dataframe = ArrayFunctions.reorder_columns_in_dataframe(dataframe, self._diagram_split_keys_name_list
                                                                + self._diagram_series_name_list
                                                                + ['value', 'time'])
        dict_of_data_arrays, time_array = ArrayFunctions.split_pandas_dataframe_to_numpy_arrays_by_unique_keys(
            dataframe, self._diagram_split_keys_relations)
        self._plot_dict_of_arrays(dict_of_data_arrays, time_array)

    def _plot_dict_of_arrays(self, dict_of_data_arrays, time_array):
        for split_key_tuple, ax in self._split_keys_axes.items():
            ax.clear()
            ax.set_xlabel("time")
            ax.set_ylabel(self._get_string_name_of_tags('y_label', split_key_tuple))
            for series_key_dict in self._diagram_split_keys_relations[split_key_tuple]:
                array = dict_of_data_arrays[tuple(series_key_dict.values())]
                ax.plot(time_array, array,
                        label=self._get_string_name_of_tags('line_label', series_key_dict))
            ax.legend(loc='lower left', fontsize=8, shadow=False, ncol=2)
        # plt.pause(0.0001)
        plt.draw()
        plt.gcf().canvas.flush_events()

    def _get_string_name_of_tags(self, label_type, tag_codes):
        key_dict = dict()
        if label_type == 'y_label':
            key_dict = dict(zip(self._diagram_split_keys_name_list, tag_codes))
        elif label_type == 'line_label':
            for tag_name in self._diagram_series_name_list:
                key_dict[tag_name] = tag_codes[tag_name]

        name = ''
        for tag_name, tag_code in key_dict.items():
            if name:
                name += '; '
            name += self._get_opc_name_of_tag(tag_name, tag_code)
        return name

    def _get_opc_name_of_tag(self, tag_name, tag_code):
        opc_name = self._codes_plotting_names_dict.get((tag_name, tag_code))
        if opc_name is None:
            opc_name = ''
        return opc_name
