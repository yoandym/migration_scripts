========================================
Migrar datos entre instancias Odoo
========================================

.. toctree::
   :maxdepth: 3
   :caption: Contents:


Si la migracion a hacer es simple, esto es: los campos del modelo de origen y destino son iguales, puede usar el metodo migrate de la clase Executor casi directamente.

En cambio si la migracion tiene alguna complejidad, como por ejemplo, los campos del modelo de origen y destino no son de igual tipo de datos, o cambian de nombre o se dividen / fusionan, 
entonces debe crear un mapeo de campos y posiblemente una funcion de transformacion.

.. warning::
   En cualquier caso, tenga presente que para hacer uso del modulo debe crear su propio script de migracion, el cual debe importar las clases y funciones necesarias del modulo.

Una migracion de datos simple
--------------------------------------

A continuacion se muestra un ejemplo de migración de datos entre instancias Odoo:

1. Defina los datos de autenticacion para la instancia de origen y destino.

   Para ello puede:
   - Pasar los datos directamente al instanciar la clase *Executor*
   - Definirlos en un archivo de configuracion .env
   - Definirlos en variables de entorno

Para pasarlos directamente al instanciar la clase *Executor*:

.. code:: python
   
         source = {
            "host": "host1,
            "port": 8069,
            "bd": "v14_db_1",
            "user": "admin",
            "password":  "admin",
         }

         target = {
            "host": "host2,
            "port": 8069,
            "bd": "v17_db_2",
            "user": "admin",
            "password":  "admin",
         }

         from migration.migrate import Executor
         ex = Executor(source=source, target=target)


Para definirlos en un archivo de configuracion .env o en variables de entorno estas son las variables que debe definir:

.. code:: sh
   
      SOURCE_HOST="host1"
      SOURCE_PORT="8069"
      SOURCE_DB="v14_db_1"
      SOURCE_DB_USER="admin"
      SOURCE_DB_PASSWORD="admin"

      TARGET_HOST="host2"
      TARGET_PORT="8069"
      TARGET_DB="v17_db_2"
      TARGET_DB_USER="admin"
      TARGET_DB_PASSWORD="admin"

1. Seleccione el modelo y los campos que desea migrar. Ejemplo

.. code:: python

    model = 'crm.team'
    fields = ['name', 'sequence', 'active', 'is_favorite', 'color', 'alias_name', 'alias_contact', 'invoiced_target']



3. Ejecute el proceso de migración.

.. code:: python

   # importe la clase Executor
   from migration.migrate import Executor

   # instancie la clase Executor pasando los datos de autenticacion
   ex = Executor(source=source, target=target) 

   # instancie la clase Executor sin pasar los datos de autenticacion si estos fueron definidos en variables de entorno o en un archivo .env
   ex = Executor() 

   # Ejecute la migracion
   ex.migrate(model, fields)

Una migracion de datos intermedia
----------------------------------

Para el caso donde la migracion no sea tan simple porque algunos campos cambian de nombre solo debe hacer un mapeo de campos.

1. Siga las instrucciones iniciales de la migracion simple.
2. Cree el mapeo de campos entre las instancias de origen y destino. Esto es una lista de cadenas o diccionarios. Ejemplo:

.. code:: python

    model = 'account.payment.term'
    fields = ['name', 'active', {'note': 'description'}]

De esta forma, estariamos indicando que:
   - El campo 'name' de la instancia de origen no tuvo ningun cambio y se corresponde directmente al campo 'name' de la instancia de destino.
   - El campo 'active' de la instancia de origen no tuvo ningun cambio y se corresponde directmente al campo 'active' de la instancia de destino.
   - El campo 'note' de la instancia de origen cambio de nombre a 'description' en la instancia de destino.

3. Ejecute el proceso de migración.
   
.. code:: python

   # Ejecute la migracion
   ex.migrate(model, fields)

Una migracion de datos avanzada
--------------------------------------

Una migracion avanzada seria el caso donde es encesario hacer una o varias transformaciones a los datos de origen para que estos pueda ser correctamente migrados a la instancia de destino.

A continuacion se muestra un ejemplo:
