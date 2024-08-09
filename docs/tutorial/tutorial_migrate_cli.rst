=================================================
Migrate data using the CLI
=================================================

.. toctree::
   :maxdepth: 3
   :caption: Contents:


You can use the provided CLI to migrate data between Odoo instances.

These are the steps to do a simple data migration between Odoo instances:

1. Define :doc:`the authentication data <tutorial_migrate_conf>` for
   the source and destination instances.
2. Select the model and fields you want to migrate
   and :doc:`create a migration map <tutorial_migrate_map>`

   Example:

.. code:: sh

   python3 -m migration.cli make-map --model crm.team --recursion=3

1. Execute the migration cli command. Example:

.. code:: sh

   python3 -m migration.cli migrate --model crm.team --recursion=3


.. important::
   You can see the full cli command options by running:

   python3 -m migration.cli migrate --help
