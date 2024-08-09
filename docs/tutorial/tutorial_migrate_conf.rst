========================================
Configuration
========================================

.. toctree::
   :maxdepth: 3
   :caption: Contents:


Before you can migrate any data or do some migration maps, you must configure
the authentication data for the source and destination instances.

.. important::
   If your instances are secured with ssl, you must use the ``jsonrpc+ssl`` protocol.

Using a .env configuration file (recommended)
------------------------------------------------

Create a .env file in the root of the project with the following content:

.. code:: sh

      SOURCE_HOST="host1"
      SOURCE_PORT="8069"
      SOURCE_DB="v14_db_1"
      SOURCE_PROTOCOL="jsonrpc"
      SOURCE_DB_USER="admin"
      SOURCE_DB_PASSWORD="admin"

      TARGET_HOST="host2"
      TARGET_PORT="8069"
      TARGET_DB="v17_db_2"
      TARGET_PROTOCOL="jsonrpc"
      TARGET_DB_USER="admin"
      TARGET_DB_PASSWORD="admin"

Using environment variables
--------------------------------------

Define the exact same environment variables as in the .env file.
You can do this in the terminal or in a shell script.

Using python code
--------------------------------------

This is the least recommended way, and only available if you are developing
a custom python migration script.

.. code:: python

         source = {
            "host": "host1",
            "port": 8069,
            "bd": "v14_db_1",
            "user": "admin",
            "password":  "admin",
         }

         target = {
            "host": "host2",
            "port": 8069,
            "bd": "v17_db_2",
            "user": "admin",
            "password":  "admin",
         }

         from migration.migrate import Executor
         ex = Executor(source=source, target=target)
