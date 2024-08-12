========================================
Generate a Migration Map
========================================

.. toctree::
   :maxdepth: 3
   :caption: Contents:

To do a migration, you need a migration map. That is, a some kind of schema
that specify the models and fields to be migrated and the transformations to
be applied.

There are some examples of migration maps included in the package. You can find
them in the ``migration_scripts/maps`` directory.

If there is no example migration map for your model, you need to create one.
But before creating a migration map, you need
to :doc:`configure authentication data <tutorial_migrate_conf>`.

There are some ways to create a migration map:

1. Using the CLI. (recommended)

.. code:: sh

   python -m migration.cli make-map --model account.payment.term

This will create a migration map for the ``account.payment.term`` model inside
a ``maps`` directory in the current working directory.

To see other available options, run:

.. code:: sh

   python -m migration.cli make-map -h

2. Create a simple field mapping between the source and destination instances.
   This is a list or dictionary and is obsviously only used if you are
   developing a custom migration script.

   Example:

   .. code:: python

      model = 'account.payment.term'
      fields = ['name', 'active', {'note': 'description'}]

   In this way, we would be indicating that:
      - The ``name`` and ``active`` fields from the source instance had no
        changes and corresponds directly to the ``name`` and ``active`` fields
        of the target instance.
      - The 'note' field from the source instance was renamed to 'description'
        in the destination instance.

3. Call the ``generate_full_map()`` method in your custom migration script.

   Example:

.. code:: python

   ex = Executor(debug=False)
   res = ex.migration_map.generate_full_map(model_name='crm.lead', recursion_level=4)

.. important::

   A file migration map is an andvanced tool, use it when:
      - It is necessary to perform one or several transformations to the source
        data so that they can be correctly imported into the destination instance.
      - It is necessary to create a complete map of the fields due to changes in
        the names of both fields and models.
      - When it is necessary to create a complete map of the fields to specify
        search keys in the destination model and thus avoid
        duplicates.

   You can find some examples of these in the reference documentation of the cli module.
