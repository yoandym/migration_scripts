===================================================================
Migrate data using a custom python script
===================================================================

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

A simple data migration
--------------------------------------

Below is an example of simple data migration between Odoo instances:

1. :doc:`Define authentication data <tutorial_migrate_conf>` for the
   source and destination instances.
2. Select the model and fields you want to migrate. Example

.. code:: python

    model = 'crm.team'
    fields = ['name', 'sequence', 'active', 'is_favorite', 'color',
               'alias_name', 'alias_contact', 'invoiced_target']

3. Execute the migration process. The whole code would look like this:

.. code:: python

   # import Executor
   from migration.migrate import Executor

   # instantiate Executor. In this case, the auth data was defined at .env
   ex = Executor()

   model = 'crm.team'
   fields = ['name', 'sequence', 'active', 'is_favorite', 'color',
               'alias_name', 'alias_contact', 'invoiced_target']

   # execute the migration
   ex.migrate(model, fields)


An intermediate data migration
-------------------------------

For cases where the migration is not so simple because some fields change
names, you only need to create a field mapping.

1. Follow the initial instructions for a simple migration.
2. Create the field mapping between the source and destination instances.
   This is a list or dictionary. Example:

.. code:: python

    model = 'account.payment.term'
    fields = ['name', 'active', {'note': 'description'}]

In this way, we would be indicating that:
   - The ``name`` and ``active`` fields from the source instance had no
     changes and corresponds directly to the ``name`` and ``active`` fields
     of the target instance.
   - The 'note' field from the source instance was renamed to 'description'
     in the destination instance.

1. Execute the migration process.

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
