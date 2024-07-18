# -*- coding: utf-8 -*-

"""
Este modulo provee las clases y metodos necesarios para la migracion de datos entre instancias via XMLRPC
"""

import os
from dotenv import load_dotenv

from colorama import Fore, Back, Style
from unidecode import unidecode

import odoorpc

from tools import PrettyPrint


class Executor(object):
    """
    The Executor class is responsible for executing the migration process from a source instance to a target instance.
    It provides methods to establish connections to the source and target servers, migrate data, and perform other related operations.
    """

    source_odoo = None
    target_odoo = None
    
    model_name = None
    
    source_model = None
    target_model = None
    
    fields_map = None

    def __init__(self, source: dict=None, target: dict=None) -> None:
        """
        Initializes a new instance of the Migrate class.

        Args:
            source (dict): A dictionary containing the connection details for the source server.
            target (dict): A dictionary containing the connection details for the target server.
        """
        
        load_dotenv()

        if source is None:
            source = {
                "host": os.environ["SOURCE_HOST"],
                "port": os.environ["SOURCE_PORT"],
                "bd": os.environ["SOURCE_DB"],
                "user": os.environ["SOURCE_DB_USER"],
                "password": os.environ["SOURCE_DB_PASSWORD"],
            }

        if target is None:
            target = {
                "host": os.environ["TARGET_HOST"],
                "port": os.environ["TARGET_PORT"],
                "bd": os.environ["TARGET_DB"],
                "user": os.environ["TARGET_DB_USER"],
                "password": os.environ["TARGET_DB_PASSWORD"],
            }
        
        # gets a logged in connection to the source server
        self.source_odoo = self.get_connection(source)
        
        # gets a logged in connection to the target server
        self.target_odoo = self.get_connection(target)

    def get_connection(self, instance):
        """
        Get the connection to the server

        Args:
            instance (dict): A dictionary with the connection parameters.

        Returns:
            odoorpc.ODOO: The connection to the server.
        """
        
        # Prepare the connection to the server
        odoo = odoorpc.ODOO(host=instance['host'], port=instance['port'])
        
        # Login
        odoo.login(instance['bd'], instance['user'], instance['password'])
        
        return odoo

    def test_login(self, instance):
        """
        Test login in to instance
        """
        print('INSTANCE [%s:%s]-[%s]' % (instance['host'], instance['port'], instance['bd']))
        
        try:                
            # gets a loggued in connection to the server
            odoo = self.get_connection(instance)
            
            PrettyPrint('OK')
            
        except Exception as e:
            print(e)
            PrettyPrint('FAILED', PrettyPrint.FAILED_COLOR)
        
    def migrate(self, model_name, fields_map, batch_size=100):
        """
        Migrate data from source to target

        Args:
            model_name (str): The model name to migrate.
            fields_map (list): A list of str or dict with fields mapping to migrate. Ex: ['field1', 'field2', {'field3': 'field3_target'}]
        """
        
        # match target context with source context to avoid translation and datetimes problems
        self._match_context()
        
        # gets the source and target models
        self.source_model = self.source_odoo.env[model_name]
        self.target_model = self.target_odoo.env[model_name]
        
        # get the source and target fields for the migration
        self.fields_map = self._normalice_fields(fields_map)
        source_fields = list(self.fields_map.keys())
        target_fields = list(self.fields_map.values())
                
        # gets the source data taking into consideration the batch size
        ids = self.source_model.search([])
        batches = [ids]
        
        if len(ids) > batch_size:
            batches = self._split_into_batches(ids, batch_size)
            
        for batch in batches:
            recordset = self.source_model.browse(batch)
            data = recordset.read(source_fields)
                    
            # process relational fields
            data = self._process_relations(source_fields, data)
            
            # call callables 
            data = self._process_callables(data)
            
            # TODO: remove this code
            print("new data")
            PrettyPrint(data)
            
            # creates the records at target instance
            res = self.target_model.create(data)
                    
            print('%s %s records migrated successfully' % (len(res), model_name))
        
        return True
    
    def get_fields(self, instance: int, model_name: str, required_only=False, summary_only=True) -> list:
        """
        Get all or required fields for the model

        Args:
            instance (int): An int representing the instance to get the fields from (1: source, 2: target).
            model_name (str): The model to get the required fields.
            only_required (bool): If True, only the required fields are returned.

        Returns:
            list: The fields for the model.
        """
        # gets a loggued in connection to the server
        if instance == 1:
            odoo = self.source_odoo
        elif instance == 2:
            odoo = self.target_odoo
        else:
            print('Invalid instance value. Use 1 for source and 2 for target.')
        
        # gets the model
        model = odoo.env[model_name]
        
        # gets the fields
        fields = model.fields_get()
        
        # filter required fields
        if required_only:
            fields = [field for field in fields if fields[field]['required']]
        
        if summary_only:
            fields = list(fields.keys())
        
        return fields

    def _process_relations(self, fields: list, data: dict) -> dict:
        """
        Process the relational fields in the data

        Args:
            fields (list): The fields to migrate.
            data (dict): The data to migrate.
        
        Returns:
            data (dict): The data with the relational fields ready to be created in the target instance.
        """
        
        # gets the fields metadata
        source_fields_metadata = self.source_model.fields_get(fields)
        
        # iterate over the fields to detect relation fields
        for record in data:
            for column_name in record.keys():
                
                # do not process empty value fields
                if record[column_name] == False:
                    continue
                
                # this is necessary because some fields are not in the metada fields list (ex: id)
                if column_name in source_fields_metadata.keys():
                    
                    field_type = source_fields_metadata[column_name]['type']

                    if field_type in ['one2many', 'many2one']:
                        # gets the new target model to sync
                        new_source_model = self.source_odoo.env[source_fields_metadata[column_name]['relation']]
                        new_target_model = self.target_odoo.env[source_fields_metadata[column_name]['relation']]
                        
                        # clean the fields list (remove implicit and relational fields)
                        new_fields = list(new_source_model.fields_get().keys())
                        new_fields = self._remove_implicit_fields(new_fields)
                        new_fields = self._remove_relational_fields(new_source_model, new_fields)
                       
                        if field_type == 'one2many':
                            
                            # get the data
                            target_ids = record[column_name]
                            recordset = new_source_model.browse(target_ids)
                            new_target_data = recordset.read(new_fields)
                            
                            # replace the source ids with data
                            record[column_name] = [(0, 0, e) for e in new_target_data]

                        elif field_type == 'many2one':
                            
                            target_id, target_value = record[column_name] # Ex: [33, 'MXN']
                            
                            # first try with a perfect match: id and display_name
                            _found = new_target_model.search_count([['id', '=', target_id]])
                            recordset = None
                            if _found:
                                recordset = new_target_model.browse([target_id])
                                _found = unidecode(recordset.display_name) == unidecode(target_value)
                                
                                if _found:
                                    record[column_name] = target_id
                            
                            # if not found, try to find by display_name
                            if not _found:
                                _found = new_target_model.name_search(name=target_value, operator='=')
                                
                                if _found: # [[22, 'TURISMO']]
                                    target_id, target_value = _found[0]
                                    record[column_name] = target_id
                            
                            # if still not found, create it
                            if not _found:
                                # get the data
                                recordset = new_source_model.browse(target_id)
                                new_target_data = recordset.read(new_fields)
                                
                                # crete the record in target instance/model
                                _id = new_target_model.create(new_target_data)

                                record[column_name] = _id[0]
                            
        return data
    
    def _remove_implicit_fields(self, fields):
        """
        Remove implicit fields from the fields list

        Args:
            fields (list): The fields list to remove implicit fields from.

        Returns:
            fields (list): The list without implicit fields.
        """
        implicit_fields = ['id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update']
        
        return [field for field in fields if field not in implicit_fields]
    
    def _remove_relational_fields(self, odoo_model, fields):
        """
        Remove relational fields from the fields list

        Args:
            odoo_model (odoorpc.models.Model): The model to remove relational fields from.
            fields (list): The fields list to remove relational fields from.

        Returns:
            fields (list): The list without relational fields.
        """
        relations_to_remove = ['many2one', 'one2many', 'many2many']
        
        fields_metadata = odoo_model.fields_get(fields)
        
        return [field for field in fields if fields_metadata[field]['type'] not in relations_to_remove]
    
    def _normalice_fields(self, fields: list) -> dict:
        """
        Normalice the fields list into the expected format, which is: [{'source_field_name': 'target_field_name'}, ...]
        
        Example:
            ['name', {'days': 'nb_days'}, 'color'] -> [{'name': 'name'}, {'days': 'nb_days'}, {'color': 'color'}]

        Args:
            fields (list): The fields list to normalice.

        Returns:
            fields (dict): The normaliced fields list.
        """
        _f = fields.copy()
        
        for i, e in enumerate(_f):
            if type(e) == str:
                e = {e: e}
                _f[i] = e
        
        combined_dict = {k: v for d in _f for k, v in d.items()}
        return combined_dict
    
    def _process_callables(self, data: dict) -> dict:
        """
        Call the present callables in self.fields_map to get the data to migrate in the right format.
        self.fields_map is a dict with format: {'source_field1': callable, 'source_field2': 'target_field2', ...}

        Args:
            data (dict): The data to migrate.
        
        Returns:
            data (dict): The data with the callables processed.
        """
        _d = data.copy()
        
        for k, v in self.fields_map.items():
            if callable(v):
                _d = v(self, _d)
        
        return _d

    def _split_into_batches(self, large_list: list, batch_size: int) -> list:
        """
        Splits a large list into smaller batches of a specified size.

        Args:
            large_list (list): The large list to be split into batches.
            batch_size (int): The size of each batch.

        Returns:
            list: A list of batches, where each batch is a sublist of the original list.
        """
        batches = []
        for i in range(0, len(large_list), batch_size):
            batch = large_list[i:i + batch_size]
            batches.append(batch)
        return batches
    
    def _match_context(self, source_odoo: odoorpc.ODOO=None, target_odoo: odoorpc.ODOO=None) -> bool:
        """
        Apply the source context to the target odoo instance to avoid translation and datetimes problems.

        Args:
            source_odoo (odoorpc.ODOO): The source odoorpc.ODOO instance to copy context from.
            target_odoo (odoorpc.ODOO): The target odoorpc.ODOO instance to apply context to.

        Returns:
            bool: True if everything went ok.
        """
        
        if source_odoo is None:
            source_odoo = self.source_odoo
        if target_odoo is None:
            target_odoo = self.target_odoo
        
        if source_odoo is None or target_odoo is None:
            return False
        
        _to_match = ['lang', 'tz']
        
        for key in _to_match:
            target_odoo.env.context[key] = source_odoo.env.context[key]
                
        return True
    
    def make_fields_map(self, model_name:str = None) -> dict:
        """
        Make a fields map from a list of source and target fields.
        Intended to be feed to other migration methods / tools.
        
        Args:
            model_name (str): The model name to make the fields map.

        Returns:
            dict: A dict with: map, removed and new fields.
        """
        
        if model_name is None:
            model_name = self.model_name
        
        source_fields = self.get_fields(instance=1, model_name=model_name)
        target_fields = self.get_fields(instance=2, model_name=model_name)

        
        map = []
        removed_fields = source_fields.copy()
        new_fields = target_fields.copy()

        for field in source_fields:
            if field in target_fields:
                map.append({field: field})
                removed_fields.remove(field)
                new_fields.remove(field)
                
        return {'fields': map, 'removed': removed_fields, 'new': new_fields}