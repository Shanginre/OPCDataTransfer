from setuptools import setup, find_packages

long_description = "Python [ETL (extract-transform-load)](https://en.wikipedia.org/wiki/Extract,_transform,_load) " \
                   "script for reading data from OPC-server and sending it to the recipient (database, " \
                   "message broker, HTTP service, etc.) for further processing and storage.  " \
                   "The script works with OPC protocols based on Windows technologies (OLE, " \
                   "ActiveX, COM/DCOM), since they are the most common in the industry."

setup(
    name="OPCDataTransfer",
    version="1.1.1",
    author="Roman Shangin",
    author_email="shanginre@gmail.com",
    description="Python ETL script for reading data from OPC-server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Shanginre/OPCDataTransfer",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows"
    ],
    install_requires=[
        'OpenOPC-Python3x', 'pypiwin32', 'clickhouse_driver', 'requests', 'pandas', 'matplotlib'
    ],
    python_requires='>=3.6-32',
    entry_points={
       'console_scripts': [
           'DataTransfer = OPCDataTransfer.DataTransfer:main',
           'DataWriterToOPC = OPCDataTransfer.Simulation.WrightToOPC:main'
           ]
    }
)
