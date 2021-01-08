# OPC Data Transfer

[![PyPI](https://img.shields.io/pypi/v/OPCDataTransfer)](https://pypi.org/project/OPCDataTransfer/)
![Platform](https://img.shields.io/badge/Platform-win--32-lightgrey)
[![License](https://img.shields.io/pypi/l/OPCDataTransfer)](https://en.wikipedia.org/wiki/MIT_License)

[ETL (extract-transform-load)](https://en.wikipedia.org/wiki/Extract,_transform,_load) скрипт на python для чтения данных из OPC-сервера и отправки их получателю (база данных, 
брокер сообщений, HTTP-сервис и т.д.) для последующей обработки и хранения. 

Основная область применения – [IIOT (Industrial Internet of Things)](https://en.wikipedia.org/wiki/Industrial_internet_of_things). 
Технология OPC является де-факто стандартом в промышленности и часто используются в SCADA системах для взаимодействия с 
программируемыми логическими контроллерами (далее ПЛК) установленными на оборудовании.

Скрипт предназначен для работы с OPC протоколами, базирующимися на Windows-технологиях (OLE, ActiveX, COM/DCOM), так как 
они наиболее распространены в отрасли.

## Кейс использования

На узлах промышленного оборудования установлены сенсоры, регистрирующие параметры работы: уровень вибрации, температура, 
потребляемая мощность и т.д. Сенсоры подключены к ПЛК, который смонтирован на оборудовании. На каждой единице оборудования 
могут быть несколько сенсоров и один или несколько ПЛК. Далее ПЛК по различным протоколам (ModBus TCP/RTU, CAN, TCP/IP и т.д.) 
отправляют полученные от сенсоров данные в OPC сервер, где они далее используются в SCADA системе.

ETL скрипт с заданной периодичностью считывает данные из OPC сервера и отправляет их для последующей обработки. На данный 
момент в скрипте поддерживаются несколько типов приемников:

- [ClickHouse](https://clickhouse.tech/docs/en/). Быстрая колоночная СУБД для big data. Для интеграции используется 
[ClickHouse Python Driver](https://github.com/mymarilyn/clickhouse-driver), который реализует нативный протокол ClickHouse, работающий по TCP/IP.
- HTTP-сервис (REST-API). Произвольный HTTP -сервис, который принимает данные для последующей обработки. Используется библиотека Requests.

## Установка

Установка через pip:
```
python -m pip install OPCDataTransfer
```
Если вы клонируете репозиторий, необходимо установить требуемые библиотеки:
```
python -m pip install -r requirements.txt
```
Поскольку скрипт предназначен для работы с протоколами, базирующимися на Windows-технологиях, то скрипт необходимо 
инсталлировать и запускать на машине под управлением Windows. Рекомендуется использовать 32-разрядную версию Python 3.


## Запуск скрипта и настройки

Скрипт DataTransfer.py запускается с обязательным параметром --settings_file_path, в котором указывается полный путь к 
файлу настроек в формате .ini. В файле /Data/run_settings_sample.ini содержатся примеры таких настроек. 

Для удобства отладки и тестирования ETL cкрипта создан вспомогательный скрипт /Simulation/WrightToOPC.py, 
который симулирует параметры работы узлов промышленного оборудования и пишет данные в OPC-сервер. Структура симулируемых параметров, 
отправляемых в OPC сервер, фиксирована: facility, component, parameter, value, time.

Для тестирования работы ETL скрипта рекомендуется использовать [MatrikonOPC Simulation Server](https://www.matrikonopc.com/products/opc-drivers/opc-simulation-server.aspx). 
Пример настроек параметров OPC-сервера в файле /Data/opc_settings.xml.

При использовании ClickHouse как приемника данных максимальная пропускная способность приложения (чтение из OPC и загрузка 
в приемник) составила 16 тыс. строк. в секунду, где строка данных имела структуру: facility, component, parameter, value, time.


## Как использовать в продакшене

Скрипт рекомендуется запускать на той машине, где работает OPC-сервер, так как это повышает стабильность и скорость работы с OPC-сервером. 

Можно запускать скрипт как службу Windows. Для этого нужно создать bat файл, запускающий скрипт и создать службу Windows, 
исполняющую этот bat файл. Для создания службы из bat файла можно воспользоваться [srvany](https://docs.microsoft.com/en-us/troubleshoot/windows-client/deployment/create-user-defined-service)
или [NSSM](https://github.com/kirillkovalenko/nssm).

Так же можно использовать части скрипта в составе ETL конвейеров, например, сделанных на [Airflow](https://github.com/apache/airflow) 
или [Luigi](https://github.com/spotify/luigi):
```python
import OPCDataTransfer
conf_settings = OPCDataTransfer.ConfParser(settings_file_path).get_settings()

# run ETL script with settings read from .ini file
OPCDataTransfer.start_transfer_data_from_opc_server(conf_settings)

# get current data from OPC server
opc_client = OPCDataTransfer.ConnectionOPC(conf_settings)
param_list = opc_client.get_list_of_current_values()
```