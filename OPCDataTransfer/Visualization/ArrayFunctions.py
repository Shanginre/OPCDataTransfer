# -*- coding: UTF-8 -*-

import pandas as pd
import numpy as np
import datetime


def list_of_structures_to_pandas_dataframe(data_list):
    return pd.DataFrame(data_list)


def list_of_structures_to_numpy_array(data_list):
    values = [tuple(each.values()) for each in data_list]
    array = np.array(values)
    return array


def get_last_n_rows_in_list(data_list, num_rows):
    if len(data_list) <= num_rows:
        return data_list
    else:
        return data_list[-num_rows:]


def find_unique_keys_in_dataframe(dataframe, keys_list):
    keys_dataframe = dataframe[keys_list].drop_duplicates().sort_values(by=keys_list)
    return keys_dataframe


def number_rows_in_array(array):
    return np.shape(array)[0]


def dataframe_to_list_of_tuples(dataframe):
    return list(map(tuple, dataframe.to_numpy()))


def select_rows_in_dataframe_by_dict(dataframe, filter_dict):
    return dataframe[np.logical_and.reduce([dataframe[k] == v for k, v in filter_dict.items()])]


def reorder_columns_in_dataframe(dataframe, ordered_name_list):
    return dataframe[ordered_name_list]


def split_pandas_dataframe_to_numpy_arrays_by_unique_keys(dataframe, split_keys_relations_list):
    dict_of_data = {}
    filtered_dataframe_by_key = pd.DataFrame()
    for split_key, key_dicts_list in split_keys_relations_list.items():
        for key_dict in key_dicts_list:
            filtered_dataframe_by_key = select_rows_in_dataframe_by_dict(dataframe, key_dict)
            dict_of_data[tuple(key_dict.values())] = filtered_dataframe_by_key['value'].to_numpy()

    # The time grid is the same for all values
    time_array = _convert_to_time(filtered_dataframe_by_key['time'].to_numpy())

    return dict_of_data, time_array


def _convert_to_time(time_array):
    time_arr_formatted = np.empty(len(time_array), dtype=np.dtype('U10'))
    for i in range(len(time_array)):
        value = time_array[i]
        if type(value) == np.dtype('str'):
            time_arr_formatted[i] = value.split(' ')[1].split(':', 1)[1]
        elif type(value) == np.dtype('float'):
            time_arr_formatted[i] = str(datetime.timedelta(seconds=value)).split(',')[1].split('.')[0].split(':', 1)[1]

    return time_arr_formatted
