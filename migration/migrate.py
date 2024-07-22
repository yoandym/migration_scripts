# -*- coding: utf-8 -*-

"""
This module provides the necessary classes and methods for data migration between instances via XMLRPC.
"""

import os
import json
from dotenv import load_dotenv

from typing import Union

from colorama import Fore, Back, Style
from unidecode import unidecode

import odoorpc

from tools import Pretty


class Executor(object):
    """
    The Executor class is responsible for executing the migration process from a source instance to a target instance.
    It provides methods to establish connections to the source and target servers, migrate data, and perform other related operations.
    """

    source_odoo = None
    target_odoo = None
    
    model_name = None
    target_model_name = None
    
    source_model = None
    target_model = None
    
    fields_map = None
    
    transformers = {}
    
    relation_types = ['one2many', 'many2one', 'many2many']

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

    def test_login(self, instance) -> bool:
        """
        Test login in to instance
        
        Args:
            instance (dict): A dictionary with the connection parameters.
        
        Returns:
            bool: True if the login was successful, False otherwise.
        """
        print('INSTANCE [%s:%s]-[%s]' % (instance['host'], instance['port'], instance['bd']))
        
        try:                
            # gets a loggued in connection to the server
            odoo = self.get_connection(instance)
            
            Pretty.print('OK')
            
            return True
            
        except Exception as e:
            print(e)
            Pretty.print('FAILED', Pretty.FAILED_COLOR)
            
            return False
        
    def migrate(self, model_name: str, migration_map: Union[dict, list], recursion_level: int=0, batch_size=100):
        """
        Migrate data from source to target

        Args:
            model_name (str): The model name to migrate.
            migration_map (Union[dict, list]): A list of str or dict with fields mapping to migrate. Ex: ['field1', 'field2', {'field3': 'field3_target'}]
            recursion_level (int): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.
            batch_size (int): The batch size to use when migrating a large dataset. Defaults to 100.
        """

        # save data
        self.model_name = model_name
        self.migration_map = self._normalice_fields(migration_map)
        
        # match target context with source context to avoid translation and datetimes problems
        self._match_context()
        
        # gets the source and target models
        self.source_model = self.source_odoo.env[model_name]
        self.target_model_name = self.migration_map[model_name].get("target_model", model_name)
        self.target_model = self.target_odoo.env[self.target_model_name]
        
        # get the source and target fields for the migration
        main_model_fields_map = self.migration_map[model_name]["fields"]
        
        source_fields = list(main_model_fields_map.keys())
        target_fields = list(main_model_fields_map.values())
                
        # gets the source data taking into consideration the batch size
        ids = self.source_model.search([])
        batches = [ids]
        
        if len(ids) > batch_size:
            batches = self._split_into_batches(ids, batch_size)
            
        for batch in batches:
            recordset = self.source_model.browse(batch)
            data = recordset.read(source_fields)
            
            data = self._format_data(model_name=model_name, data=data, recursion_level=recursion_level)
                                
            # TODO: remove this code
            print("new data")
            Pretty.print(data)
            
            # creates the records at target instance
            res = self.target_model.create(data)
                    
            print('%s %s records migrated successfully' % (len(res), model_name))
        
        return True
    
    def get_fields(self, instance: int, model_name: str, required_only=False, summary_only=True) -> list:
        """
        Get fields for the model

        Args:
            instance (int): An int representing the instance to get the fields from (1: source, 2: target).
            model_name (str): The model to get the required fields.
            only_required (bool): If True, only the required fields are returned.
            summary_only (bool): If True, only the field names are returned insted of the full field metadata.

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
        if model_name in odoo.env:
            model = odoo.env[model_name]
        else:
            print('Model %s not found in the instance %s' % (model_name, odoo.host))
            return []
        
        # gets the fields
        fields = model.fields_get()
        
        # filter required fields
        if required_only:
            fields = [field for field in fields if fields[field]['required']]
        
        if summary_only:
            fields = list(fields.keys())
        
        return fields

    def _format_data(self, model_name: str, data: Union[dict, list], recursion_level: int = 0) -> dict:
        """
        Makes the data ready to be feed in the target instance:
            - Traverse relational fields.
            - Changes field names.
            - Executes callables.

        Args:
            model_name (str): The model name to migrate.
            data (Union[dict, list]): The data to format.
            recursion_level (int, optional): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.

        Returns:
            dict: The data properly formatted to be feed in the target instance.
        """
        
        # gets the fields mapping for the main model
        model_fields_map = self.migration_map[model_name]['fields']
        
        # get the source fields metadata
        model_field_list = list(model_fields_map.keys())
        source_model = self.source_odoo.env[model_name]
        model_fields_metadata = source_model.fields_get(model_field_list)
        
        # process relational fields
        for idx, record in enumerate(data):
            for column_name in list(record.keys()):
                if column_name not in model_field_list:
                    record.pop(column_name)
                    continue
                
                field_type = model_fields_metadata[column_name]["type"]
                                
                # test for and process relational fields
                if field_type in self.relation_types:
                    new_source_model_name = model_fields_metadata[column_name]['relation']
                    col_value = self._process_relation(model_name=new_source_model_name, 
                                                    relation_type=field_type, 
                                                    field_name=column_name,
                                                    data=record[column_name], 
                                                    recursion_level=recursion_level)
                    record[column_name] = col_value
                
                # test for and do field name changes
                field_mapping_value = model_fields_map[column_name]
                if column_name != field_mapping_value:
                    
                    # test for and process callables
                    # has to be done after the relational fields processing
                    # process the whole data set. 
                    # Internally it detects and executes the callables for every field
                    if callable(field_mapping_value):
                        data = field_mapping_value(self, data)
                    else:
                        # do the field name change
                        record[field_mapping_value] = record.pop(column_name)
            
        return data
    
    def _process_relation(self, model_name: str, relation_type: str, field_name: str, data: Union[dict, list], recursion_level: int = 0) -> dict:
        """
        Process / traverses the relational fields in data

        Args:
            model_name (str): The model name to process relations for.
            relation_type (str): The type of relation to process.
            field_name (str): The field name to process.
            data (Union[dict, list]): The data to process.
            recursion_level (int): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.
        
        Returns:
            data (dict): The data with the relational fields ready to be created in the target instance.
        """
                                        
        # dont process fields deeper than recursion_level
        if recursion_level > 0:
            
            # gets the fields mapping for the model
            model_fields_map = self.migration_map[model_name]['fields']
            
            # gets the source model to sync from
            source_model = self.source_odoo.env[model_name]
            
            # get the source fields metadata
            model_field_list = list(model_fields_map.keys())
            model_fields_metadata = source_model.fields_get(model_field_list)

            # get the target model and fields to sync to
            target_model_name = self.migration_map[model_name].get("target_model", model_name)
            target_model = self.target_odoo.env[target_model_name]
            target_field_list = list(self.migration_map[model_name]['fields'].values())
            
            # get the search keys. Default is id and name
            search_keys = self.migration_map[model_name].get("search_keys", {"id": "id", "name": "name"})

            if relation_type == 'one2many':
                
                # get the source data
                related_source_ids = data # Ex: [33, 34, 35]      
                related_source_recordset = source_model.browse(related_source_ids)
                related_source_data = related_source_recordset.read(model_field_list)
                                
                # data may contain new relations, so we have to format them
                data = self._format_data(model_name=model_name, data=related_source_data, recursion_level=recursion_level - 1)
                
                # final format
                data = [(0, 0, e) for e in data]



            elif relation_type == 'many2one':
                
                # get the source data
                related_source_id, related_source_display_name = data # Ex: [33, 'MXN']                            
                related_source_recordset = source_model.browse(related_source_id)
                related_source_data = related_source_recordset.read(model_field_list)[0]
                
                # try to find it by every search key
                _found = False
                for s_key, t_key in search_keys.items():
                    if t_key == 'id':
                        _found = target_model.search_count([['id', '=', related_source_id]])
                        if _found:
                            recordset = target_model.browse([related_source_id])
                            _found = unidecode(recordset.display_name) == unidecode(related_source_display_name)
                            
                            if _found:
                                data = related_source_id
                                break
                    else:
                        source_key_value = related_source_data[s_key]
                        _found = target_model.search([[t_key, '=', source_key_value]])
                        if _found:
                            _id = _found[0]
                            data = _id
                            break
                
                # if still not found, create it
                if not _found:
                    # get the data
                    recordset = source_model.browse(related_source_id)
                    new_source_data = recordset.read(model_field_list)
                    
                    # data may contain new relations, so we have to format them
                    new_source_data = self._format_data(model_name=model_name, data=new_source_data, recursion_level=recursion_level - 1)

                    # crete the record in target instance/model
                    _id, _displayname = target_model.create(new_source_data)[0]

                    data = _id
        
        else:
            print('Relational field %s to model %s, not processed because is deeper than recursion level' % (field_name, model_name))
                 
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
    
    def _normalice_fields(self, fields: Union[list, dict]) -> dict:
        """
        Normalice the fields list into the expected format, 
        which is: [{'source_field_name': 'target_field_name'}, {'source_field_name': transformer_function}, ...]
        
        Examples:
            in = ['name', {'days': 'nb_days'}, 'color']
            out = {'name': 'name', 'days': 'nb_days', 'color': 'color'}

            in = ['name', {'days': 'nb_days'}, {'color': color_transformer}]
            out = {'name': 'name', 'days': 'nb_days', 'color': color_transformer}


        Args:
            fields (Union[list, dict]): The fields list to normalice.

        Returns:
            fields (dict): The normaliced fields list.
        """
        _f = fields.copy()
        combined_dict = {}
        
        if isinstance(_f, list):
            for i, e in enumerate(_f):
                if type(e) == str:
                    e = {e: e}
                    _f[i] = e
            
            combined_dict = {k: v for d in _f for k, v in d.items()}
        elif isinstance(_f, dict):
            combined_dict = _f
            
        
        return combined_dict
    
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
    
    def load_fields_map(self, file_path: str) -> dict:
        """
        Load a fields map from a file.

        Args:
            file_path (str): The path to the file where the fields map is stored.

        Returns:
            dict: The fields map loaded from the file.
        """
        _d = None
        with open(file_path, 'r') as file:
            _d = json.load(file)
        
        # if _d references a callable try to get a pointer to it
        # _d is expected to contain {model_name: {fields:{field1:field1, field2:@callable_name, ...}, removed:[], new:[]}, ...
        for _model_name, _data in _d.items():
            for _field, _value in _data['fields'].items():
                if type(_value) == str and _value[0].strip(" ").startswith('@'):
                    _callable_name = _value[1:]
                    
                    # first search self.transformers
                    _callable_pointer = self.transformers.get(_callable_name, None)
                    # if not found, search in __main__
                    if _callable_pointer is None:
                        import __main__
                        _callable_pointer = getattr(__main__, _callable_name, None)
                        
                    if _callable_pointer is None:
                        raise Exception('Error: Callable %s not found' % _callable_name)
                        
                    _d[_model_name]['fields'][_field] = _callable_pointer
        return _d
    
    def make_fields_map(self, model_name:str, target_model_name:str = None, recursion_level: int=0) -> dict:
        """
        Make a fields map from a list of source and target fields.
        The output is intended to be feed to other migration methods / tools.
        
        Args:
            model_name (str): The main source model name to map from.
            target_model_name (str): The main target model name to map to.
            recursion_level (int): The recursion level to apply. This means that the map will be made for the related models/fields too.
                - If 0, no recursion will be applied.
                - If 1, only the first level of related models/fields will be mapped.
                - If 2, the first and second level of related models/fields will be mapped.
                - ...

        Returns:
            dict: A dict with the folling format: {modelname: {target_model, search_keys, fields, removed, new}, ...} where:
                - target_model is the target model name. You can modify it if you want to migrate to a different model name
                - search_keys is a **dict** with the keys to search for the records in the target model. Default is {'id': 'id', 'name': 'name'}. This is useful to avoid data dups.
                - fields is a **dict** with the fields mapping: {'source_field1': 'target_field1', 'source_field2': 'target_field2', ...}
                - removed is a **list** with the fields that are not in the target model. You can use this list to adjust the mappings.
                - new is a **list** with the fields that are not in the source model. You can use this list to adjust the mappings.
        """
        
        # model_name is actually the source model to migrate
        source_model_name = model_name
        
        # target_model_name can be None. Example if the user is not interested in recursion
        if target_model_name is None or target_model_name == '':
            target_model_name = model_name
                
        source_fields = self.get_fields(instance=1, model_name=source_model_name, summary_only=False)
        target_fields = self.get_fields(instance=2, model_name=target_model_name, summary_only=False)
        
        map = {}
        submap = {}
        removed_fields = list(source_fields.copy().keys())
        new_fields = list(target_fields.copy().keys())

        # # this is necceary cause the source or target fields maybe empty (because the model does not exist)
        field_list = list(source_fields.copy().keys())

        for field in field_list:
            if field in target_fields:
                
                field_type = source_fields[field]['type']
                if field_type in self.relation_types and recursion_level > 0:
                    # get source and target related model names
                    related_source_model_name = source_fields[field]['relation']
                    related_target_model_name = target_fields[field]['relation']
                    
                    # build a new map for the related models
                    new_map = self.make_fields_map(model_name=related_source_model_name, target_model_name=related_target_model_name, 
                                                       recursion_level=recursion_level - 1)
                    submap[field] = field
                    removed_fields.remove(field)
                    new_fields.remove(field)
                    
                    map.update(new_map)
                else:
                    submap[field] = field
                    removed_fields.remove(field)
                    new_fields.remove(field)
                
        map[source_model_name] = {
            "target_model": target_model_name,
            "search_keys": {"id": "id", "name": "name"}, # default search keys
            "fields": submap, "removed": removed_fields, "new": new_fields}
        
        return map
    
    def add_transformer(self, transformer, model: str, field: str, fields_map: dict=None) -> dict:
        """
        Add a transformer to the models / fields map.
        If no fields_map is provided, or the model / fields is not in the map, the transformer is added to the locals() so it can be used later. Ex at fields_map loading.

        Args:
            transformer (list): A transformer function / callable to add to the fields map.
            model (str): The model to add the transformer to.
            field (str): The field to add the transformer to.
            fields_map (dict): The fields map to add the transformers to. Defaults to None.

        Returns:
            dict: The updated fields map.
        """
        # if we got a fields_map, try add the transformer to it
        # if the provided model and field does not exist, return the fields_map as is and add the trasnformer to the locals()
        if fields_map and model in fields_map and field in fields_map[model]['fields']:
            fields_map[model]['fields'][field] = transformer
        
        # also add the transformer to the locals() so it can be used later
        self.transformers[transformer.__name__] = transformer
        return fields_map
           
    