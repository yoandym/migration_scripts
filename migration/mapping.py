# -*- coding: utf-8 -*-

"""
This module provides the MigrationMap class and methods used to build and process a dict
with data used as a sort of migration schema for data migration between odoo instances.
"""

import json
from typing import Union

import treelib

from exceptions import MissingModelMappingException

class MigrationMap:
    """
    This class is used to define and handle the mapping between the source and destination models/fields.
    """
    
    transformers = None
    """
    A dict with transformer functions / callables that can be used to transform the data.

    A transformer function should have the following signature::
    
        def transformer(executor: Executor, data: list) -> dict
            pass

    """
    
    map = None
    """
    Containes the mapping between the source and destination models/fields.

    A map entry is a dict with the following structure::

        {
            'source_model_name': {
                'search_keys': {'source_field1': 'destination_field1', 
                                'source_field2': 'destination_field2', ...},
                'target_model': 'target_model_name',
                'fields': {
                    'source_field': 'destination_field',
                    ...
                },
                'removed': ['field1', 'field2', ...],
                'new': ['field1', 'field2', ...]
            }
        }

    """
    
    #: Default fields to search for a record in the source and target model.
    default_search_keys = {"name": "name"}


    def __init__(self, executor: object=None):
        """ Initialize the MigrationMap class.

        Args:
            executor (object, optional): Holds an instance of 
            an ``Executor`` ( it provides a connection to the source and 
            destination databases and other tools). Defaults to None.
        """
        self.map = {}
        self.transformers = []
        self.excutor = None

    def get_mapping(self, source_model_name: str= None):
        """
        Get the mapping for a model.
        If no model is specified, return the whole map.

        Args:
            source_model_name (str, optional): The name of the source model.

        Raises:
            MissingModelMappingException: Raised when ``source_model_name`` is not in the map.

        Returns:
            dict: The mapping for the source model.
        """
        try:
            return self.map[source_model_name]
        except KeyError:
            raise MissingModelMappingException("There is no mapping for model '{}'".format(source_model_name))
    
    def get_target_model(self, source_model_name: str) -> str:
        """
        Get the target model name for the source model.

        Args:
            source_model_name (str): The source model name.

        Returns:
            str: The target model name.
        """
        return self.get_mapping(source_model_name).get("target_model", source_model_name)
    
    def get_search_keys(self, source_model_name: str) -> dict:
        """
        Get the search keys for the source model.

        Args:
            source_model_name (str): The source model name.

        Raises:
            MissingModelMappingException: Raised when ``source_model_name`` is not in the map.

        Returns:
            dict: The search keys for the source model.
        """
        return self.get_mapping(source_model_name).get("search_keys", self.default_search_keys)
    
    def add_transformer(self, transformer, model: str, field: str) -> dict:
        """
        Add a transformer to the models / fields map.
        If no fields_map is provided, or the model / fields is not in the map, the transformer is added to the locals() so it can be used later. Ex at fields_map loading.

        Args:
            transformer (list): A transformer function / callable to add to the fields map.
            model (str): The model to add the transformer to.
            field (str): The field to add the transformer to.

        Returns:
            dict: The updated fields map.
        """
        # if we got a fields_map, add the transformer to it
        # if the provided model and field does not exist, return the fields_map as is and add the trasnformer to the locals()
        if self.map and \
            model in self.map and \
            field in self.map[model]['fields']:
            self.map[model]['fields'][field] = transformer
        
        # keep a ref to the transformer so it can be used later
        self.transformers[transformer.__name__] = transformer
        return self.map

    def model_tree(self, model_name: str, recursion_level: int=0) -> dict:
        """
        Make a relation tree for the model until the recursion level.

        Args:
            model_name (str): The model name to make the relation tree for.
            recursion_level (int): The recursion level to apply. Defaults to 0.

        Returns:
            dict: The relation tree for the model.
        """
        
        def _build_tree(_model_name, from_field=None, _level=None):
            
            tree = treelib.Tree()
            
            if _level is None:
                _level = 0
                node = tree.create_node(tag=_model_name)
            else:
                tag = "%s->%s" % (from_field, _model_name)
                node = tree.create_node(tag=tag)
                        
            if _level == recursion_level:
                return tree
                
            # get odoo model and field metadata
            source_model = self.source_odoo.env[_model_name]
            field_metadata = source_model.fields_get()
            
            # build tree
            for field, field_data in field_metadata.items():
                field_type = field_data['type']
                if field_type in self.relation_types:
                    
                    new_model = field_data['relation']
                    
                    tag = "%s->%s" % (field, _model_name)
                    
                    new_tree = _build_tree(_model_name=new_model, from_field=field, _level=_level + 1)
                    tree.paste(nid=node.identifier, new_tree=new_tree)
            
            return tree
                
        return _build_tree(model_name)

    def generate_full_map(self, model_name:str, target_model_name:str = None, recursion_level: int=0) -> dict:
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
                - modelname is the source model name.
                - target_model is the target model name. You can modify it if you want to migrate to a different model name
                - search_keys is a **dict** with the keys to search for the records in the target model. Default is {'id': 'id', 'name': 'name'}. This is useful to avoid data dups.
                - fields is a **dict** with the fields mapping: {'source_field1': 'target_field1', 'source_field2': 'target_field2', ...}
                - removed is a **list** with the fields that are not in the target model. You can use this list to adjust the mappings.
                - new is a **list** with the fields that are not in the source model. You can use this list to adjust the mappings.
        """
        
        if self.executor is None:
            raise Exception('Error: No executor instance provided. Cant make the fields map.')
        
        # model_name is actually the source model to migrate
        source_model_name = model_name
        
        # target_model_name can be None. Example if the user is not interested in recursion
        if target_model_name is None or target_model_name == '':
            target_model_name = model_name
                
        source_fields = self.executor.get_fields(instance=1, model_name=source_model_name, summary_only=False)
        target_fields = self.executor.get_fields(instance=2, model_name=target_model_name, summary_only=False)
        
        map = {}
        submap = {}
        removed_fields = list(source_fields.copy().keys())
        new_fields = list(target_fields.copy().keys())

        # # this is necceary cause the source or target fields maybe empty (because the model does not exist)
        field_list = list(source_fields.copy().keys())

        for field in field_list:
            if field in target_fields:
                include_field_in_map = True
                
                # test for and process relational fields
                field_type = source_fields[field]['type']
                if field_type in self.executor.relation_types:
                    if recursion_level > 0:
                        # get source and target related model names
                        related_source_model_name = source_fields[field]['relation']
                        try:
                            related_target_model_name = target_fields[field]['relation']
                        except KeyError:
                            related_target_model_name = related_source_model_name
                            print('Warning: Source Field %s.%s poiting to %s is not a relation in target instance.' % (model_name, field, related_source_model_name))
                            print('You have to adjust the fields map with a transformer function or remove the field from the map.')
                        else: # if no errors
                            # build a new map for the related models
                            new_map = self.make_fields_map(model_name=related_source_model_name, target_model_name=related_target_model_name, 
                                                            recursion_level=recursion_level - 1)                        
                            map.update(new_map)
                    elif self.executor.recursion_mode == 'w':
                        include_field_in_map = False
                        print('Warning: Field %s.%s is a relation and current recursion level is not enougth. Skipping it from map/migration.' % (model_name, field))
                    elif self.executor.recursion_mode == 'h':
                        include_field_in_map = False
                        raise Exception('Error: Field %s.%s is a relation and current recursion level is not enougth. Cant traverse it. Aborting.' % (model_name, field))
                    else:
                        raise Exception('Error: Invalid recursion mode %s. Use "h" for halt or "w" for warn.' % self.executor.recursion_mode)
                
                # should i include the field in the map?
                if include_field_in_map:
                    submap[field] = field
                    removed_fields.remove(field)
                    new_fields.remove(field)
                
        map[source_model_name] = {
            "target_model": target_model_name,
            "search_keys": self.default_search_keys, # default search keys
            "fields": submap, "removed": removed_fields, "new": new_fields}
        
        self.map = map
        return map
    
    def load_from_file(self, file_path: str) -> dict:
        """
        Load a migration map from a file.

        Args:
            file_path (str): The path to the file where the fields map is stored.

        Returns:
            dict: The fields map loaded from the file.
        """
        _d = None
        with open(file_path, 'r') as file:
            _d = json.load(file)
        
        # _d is expected to contain {model_name: {fields:{field1:field1, field2:@callable_name, ...}, removed:[], new:[]}, ...
        for _model_name, _data in _d.items():
            for _field, _value in _data['fields'].items():
                
                # if its a callable get a ref to it
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
        
        self.map = _d
        return _d
    
    def normalice_fields(self, fields: Union[list, dict]) -> dict:
        """
        Normalice the given fields into the expected format, 
        which is: [{'source_field_name1': 'target_field_name1'}, {'source_field_name2': transformer_function}, ...]
        
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
            
        self.map = combined_dict
        return combined_dict