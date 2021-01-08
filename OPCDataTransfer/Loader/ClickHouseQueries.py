# -*- coding: UTF-8 -*-


def create_database_if_not_exists(client, db_name):
    client.execute(
        'CREATE DATABASE IF NOT EXISTS '+db_name
    )


def create_table_if_not_exists(client, ClickHouse_table_create_query):
    if ClickHouse_table_create_query != '':
        client.execute(ClickHouse_table_create_query)


def insert_values_into_table(client, db_name, table_name, list_data, parameters_name_string):
    full_table_name = db_name + '.' + table_name
    client.execute(
        'INSERT INTO ' + full_table_name + ' (' + parameters_name_string + ') VALUES',
        list_data
    )
