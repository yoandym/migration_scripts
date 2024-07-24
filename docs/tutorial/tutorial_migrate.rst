========================================
Migrate data between Odoo instances
========================================

.. toctree::
   :maxdepth: 3
   :caption: Contents:


If the migration to be done is simple, that is: the fields of the source and
destination model are the same, you can use the migrate method of the Executor
class almost directly.

However, if the migration has some complexity, such as, the
fields of the source and destination model are not of the same data type, or
they change names or are split / merged, then you must create a field mapping
and possibly a transformation function.

.. Note::
   In any case, keep in mind that to use the module you must create
   your own migration script, which must import the necessary classes and
   functions from the module.

A simple data migration
--------------------------------------

Below is an example of data migration between Odoo instances:

1. Define the authentication data for the source and destination instances.

   To do this, you can:
   - Pass the data directly when instantiating the *Executor* class
   - Define them in a .env configuration file
   - Define them in environment variables

To pass them directly when instantiating the *Executor* class:

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


To define them in a .env configuration file or in environment variables these
are the variables you must define:

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

2. Select the model and fields you want to migrate. Example

.. code:: python

    model = 'crm.team'
    fields = ['name', 'sequence', 'active', 'is_favorite', 'color',
               'alias_name', 'alias_contact', 'invoiced_target']



3. Execute the migration process.
   
.. code:: python

   # importe la clase Executor
   from migration.migrate import Executor

   # instancie la clase Executor pasando los datos de autenticacion
   ex = Executor(source=source, target=target)

   # instancie la clase Executor sin pasar los datos de autenticacion si estos
   # fueron definidos en variables de entorno o en un archivo .env
   ex = Executor()

   # Ejecute la migracion
   ex.migrate(model, fields)


An intermediate data migration
-------------------------------

For cases where the migration is not so simple because some fields change
names, you only need to create a field mapping.

1. Follow the initial instructions for a simple migration.
2. Create the field mapping between the source and destination instances.
   This is a list of strings or dictionaries. Example:

.. code:: python

    model = 'account.payment.term'
    fields = ['name', 'active', {'note': 'description'}]

In this way, we would be indicating that:
   - The 'name' field from the source instance did not have any changes and
     corresponds directly to the 'name' field of the destination instance.
   - The 'active' field from the source instance did not have any changes and
     corresponds directly to the 'active' field of the destination instance.
   - The 'note' field from the source instance was renamed to 'description'
     in the destination instance.

3. Execute the migration process.

.. code:: python

   # Ejecute la migracion
   ex.migrate(model, fields)

An advanced data migration
--------------------------------------

An advanced migration would be when:
   - It is necessary to perform one or several transformations to the source
     data so that they can be correctly imported into the destination instance.
   - It is necessary to create a complete map of the fields due to changes in
     the names of both fields and models.
   - When it is necessary to create a complete map of the fields to specify
     search keys in the destination model and thus avoid
     duplicates.

You can find some of these in the reference documentation of the main module.
