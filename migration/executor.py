# -*- coding: utf-8 -*-

"""
This module provides the necessary classes and methods for data migration between instances via XMLRPC.
"""

import os, sys
import copy
from datetime import datetime
from dotenv import load_dotenv

from typing import Union

from colorama import Fore, Back, Style
from unidecode import unidecode

import odoorpc
import treelib

from tools import Pretty
from mapping import MigrationMap
from exceptions import TooDeepException, UnsupportedRelationException


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
    
    #: An instance of MigrationMap
    migration_map = None
    
    recursion_mode = None
    """ 
    The recursion mode to use while traversing relations. Defaults to "w".
        - h: Halt. Will raise an exception if cant traverse a relation because of recursion level
        - w: Warn. Warn, wipe the field from map, and keep running, 
        if cant traverse a relationbecause of recursion level
    """
        
    #: Set the relation types to traverse
    relation_types = ['one2many', 'many2one', 'many2many']
    
    #: Options / Values to set on context. By default sets tracking **'tracking_disable' = True**.
    record_create_options = {'tracking_disable': True}
    
    #: Directory to save logs
    log_path = None
                

    def __init__(self, source: dict=None, target: dict=None, debug: bool=False, recursion_mode: str="w") -> None:
        """
        Initializes a new instance of the Executor class.

        Args:
            source (dict): A dictionary containing the connection details for the source server.
            target (dict): A dictionary containing the connection details for the target server.
            debug (bool): If True, the debug mode will be enabled. Defaults to False.
            recursion_mode (str): The recursion mode to apply. Defaults to "w".
                - h: Halt, if cant traverse a relation because of recursion level
                - w: Warn, and wipe the field from map, if cant traverse a relation because of recursion level
        """
        
        load_dotenv()
                
        self.debug = debug
                
        self.recursion_mode = recursion_mode
        
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
        
        self.migration_map = MigrationMap(self)
        
        self.run_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        # set log file name to current os date time
        log_file_name = "%s.log" % self.run_id
        self.log_path = os.path.join(os.path.dirname(__file__), log_file_name)

    @property
    def debug(self):
        """
        Get the debug mode.

        Returns:
            bool: True if debug mode is enabled, False otherwise.
        """
        return self._debug

    @debug.setter
    def debug(self, value: bool):
        """
        Set the debug mode = True to print stack traces on error

        Args:
            value (bool): True to enable debug mode, False to disable it.
        """
        self._debug = value
        if self._debug:
            sys.tracebacklimit = 1000
        else:
            sys.tracebacklimit = 0

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
        
    def migrate(self, model_name: str, migration_map: Union[dict, list]=None, recursion_level: int=0, batch_size=50, source_ids: list=None) -> bool:
        """
        Migrate data from source to target

        Args:
            model_name (str): The model name to migrate.
            migration_map (Union[dict, list]): The migration map to use. Defaults to None.
            recursion_level (int): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.
            batch_size (int): The batch size to use when migrating a large dataset. Defaults to 100.
            source_ids (list): A list of source ids to migrate. If present it will migrate only the provided ids. Defaults to None.
        """
        
        if migration_map is None and self.migration_map.map is None:
            print('Migration map not provided')
            return False
        elif migration_map is not None:
            self.migration_map.normalice_fields(migration_map)

        # save data
        self.model_name = model_name
        
        # match target context with source context to avoid translation and datetimes problems
        self._match_context()
        
        # gets the source and target models
        self.source_model = self.source_odoo.env[model_name]
        self.target_model_name = self.migration_map.get_target_model(model_name)
        self.target_model = self.target_odoo.env[self.target_model_name]
        
        # get the source and target fields for the migration
        main_model_fields_map = self.migration_map.get_mapping(model_name)["fields"]
        
        source_fields = list(main_model_fields_map.keys())
        target_fields = list(main_model_fields_map.values())
                
        # get the source data 
        if not source_ids:
            ids = self.source_model.search([])
        else:
            ids = source_ids
        
        # take into consideration the batch size
        batches = [ids]
        if len(ids) > batch_size:
            batches = self._split_into_batches(ids, batch_size)
            
        for batch in batches:
            
            try:
                # get data from source instance
                recordset = self.source_model.browse(batch)
                data = recordset.read(source_fields)
                
                # format it to be feed in the target instance
                data = self._format_data(model_name=model_name, data=data, recursion_level=recursion_level)

                # creates the records at target instance
                res = self.target_model.create(data)
                
                # print the results
                batch_ids = [rec["name"] if "name" in rec else "No Name" for rec in data]
                result_message = '%s %s migrated successfully: %s' % (len(res), model_name, batch_ids)
                
                print(result_message)
                
            except Exception as e:
                batch_ids = batch
                result_message = 'Batch processing error. Source instance ids: %s' % batch_ids
                
                Pretty.log(result_message, self.log_path, overwrite=True, mode='a')
                Pretty.log(repr(e), self.log_path, overwrite=True, mode='a')

                if self.debug:
                    Pretty.log(data, self.log_path, overwrite=True, mode='a')
                
                print(result_message)
                    
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
        Formats the data to be feed in the target instance:
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
        model_fields_map = self.migration_map.get_mapping(model_name)['fields']
        
        # get the source fields metadata
        model_field_list = list(model_fields_map.keys())
        source_model = self.source_odoo.env[model_name]
        model_fields_metadata = source_model.fields_get(model_field_list)
        
        # ensure data consistency
        _data = copy.deepcopy(data)
        if isinstance(_data, dict):
            _data = [_data]
        
        for idx, record in enumerate(_data):
            for column_name in list(record.keys()):
                
                # drop unwanted fields
                if column_name not in model_field_list:
                    record.pop(column_name)
                    continue
                
                field_type = model_fields_metadata[column_name]["type"]
                
                # drop empty fields. Case 1: A relation without data
                if field_type in self.relation_types and record[column_name] in [False, None, '', []]:
                    record.pop(column_name)
                    continue
                
                # drop empty fields. Case 2: A non boolean field with False value
                if field_type != "bool" and record[column_name] != 0 and record[column_name] in [False, None, '', []]:
                    record.pop(column_name)
                    continue
                                
                # test for and process relational fields
                try:
                    if field_type in self.relation_types:
                        if recursion_level > 0:
                            new_source_model_name = model_fields_metadata[column_name]['relation']
                            col_value = self._process_relation(model_name=new_source_model_name, 
                                                            relation_type=field_type, 
                                                            field_name=column_name,
                                                            data=record[column_name], 
                                                            recursion_level=recursion_level)
                            record[column_name] = col_value
                        elif self.recursion_mode == 'w':
                            print('Removing %s.%s --> %s from migration because of recursion level.' % (model_name, column_name, new_source_model_name))
                            record.pop(column_name)
                            continue
                        else:
                            raise TooDeepException('Can´t traverse relational field %s to model %s, either remove it from map or increase recursion level' % (column_name, model_name))
                    elif 'relation' in model_fields_metadata[column_name]:
                        if self.recursion_mode == 'w':
                            print('Removing %s.%s --> %s from migration because relation type not supported.' % (model_name, column_name, new_source_model_name))
                            record.pop(column_name)
                            continue
                        else:
                            raise UnsupportedRelationException('Relation type %s is not supported yet' % field_type)
                except Exception as e:
                    Pretty.log('Error processing %s.%s --> %s' % (model_name, column_name, new_source_model_name), self.log_path, overwrite=True, mode='a')
                    raise e
                
                # test for and do field name changes
                field_mapping_value = model_fields_map[column_name]
                if column_name != field_mapping_value:
                    
                    # test for and process callables
                    # has to be done after the relational fields processing
                    # process the whole data set. 
                    # At map load time callables are detected for every field
                    if callable(field_mapping_value):
                        _data = field_mapping_value(self, _data)
                    else:
                        # do the field name change
                        record[field_mapping_value] = record.pop(column_name)
            
        return _data
    
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
        
        Exceptions:
            TooDeepException: If the recursion level is not enough to process the relational field, and recursion_mode is set to Halt.
            UnsupportedRelationException: If the relation type is not supported, and recursion_mode is set to Halt.
            
            .. important:: If recursion_mode is set to ``Warn``, no exception is throw and the field is removed from data
        """
                                                
        # gets the fields mapping for the model
        model_fields_map = self.migration_map.get_mapping(model_name)['fields']
        
        # gets the source model to sync from
        source_model = self.source_odoo.env[model_name]
        
        # get the source fields metadata
        model_field_list = list(model_fields_map.keys())
        model_fields_metadata = source_model.fields_get(model_field_list)

        # get the target model and fields to sync to
        target_model_name = self.migration_map.get_target_model(model_name)
        target_model = self.target_odoo.env[target_model_name]
        target_field_list = list(model_fields_map.values())
        
        # get the search keys
        search_keys = self.migration_map.get_search_keys(model_name)

        if relation_type == 'one2many' or relation_type == 'many2many':
            
            # get the source data
            related_source_ids = data # Ex: [33, 34, 35] 
            related_source_recordset = source_model.browse(related_source_ids)
            related_source_data = related_source_recordset.read(model_field_list)
                    
                    
            _data = []
            for record in related_source_data:
                record_id = record['id']
                # search it by every search key
                _found = self.search_in_target(model_name=model_name, 
                                                source_id=record_id, 
                                                search_keys=search_keys, 
                                                target_model_name=target_model_name)
                if _found:
                    _data.append(_found[0])
                else:
                    # data may contain new relations, so we have to format them
                    _new_data = self._format_data(model_name=model_name, 
                                                    data=record, 
                                                    recursion_level=recursion_level - 1)
                    _id = target_model.create(_new_data)
                    _data.append(_id[0])
            

        elif relation_type == 'many2one':
            
            # get the source data
            related_source_id, related_source_display_name = data # Ex: [33, 'MXN']                            
            related_source_recordset = source_model.browse(related_source_id)
            related_source_data = related_source_recordset.read(model_field_list)[0]
            
            # search it by every search key
            _found = self.search_in_target(model_name=model_name, 
                                            source_id=related_source_id, 
                                            search_keys=search_keys, 
                                            target_model_name=target_model_name)
            
            # if still not found, create it
            if not _found:
                                    
                # data may contain new relations, so we have to format them
                new_target_data = self._format_data(model_name=model_name, data=related_source_data, recursion_level=recursion_level - 1)

                # create the record in target instance/model
                _found = target_model.create(new_target_data)

            _data = _found[0]
        
        else:
            raise UnsupportedRelationException('%s relations are not supported yet', relation_type)
          
        return _data
    
    def search_in_target(self, model_name: str, source_id: int, target_model_name: str=None, search_keys: dict=None) -> list:
        """ 
        Search for records in the target model using ``search keys``
        
        Args:
            model_name (str): The souce model name where data came from.
            source_id (int): The record id, from source, whose ``search_keys`` are going to be searched in the target model.
            target_model_name (str, optional): The target model name to search in. Defaults to None.
                If no target_model_name is provided, look for in migration_map, else the same ``model_name`` is used.
            search_keys (dict, optional): The search keys to use. Defaults to None.
                If no search_keys is provided, look for in migration_map, else the ``default_search_keys`` are used.

        Returns:
            list: The list of ids found in the target model.
        """
        if target_model_name is None:
            target_model_name = self.migration_map.get_target_model(model_name)
        
        if search_keys is None:
            search_keys = self.migration_map.get_search_keys(model_name)
        
        source_model = self.source_model.env[model_name]
        target_model = self.target_odoo.env[target_model_name]
        
        source_fields_to_read = list(search_keys.keys())
        target_fields_to_read = list(search_keys.values())
        
        source_recordset = source_model.browse(source_id)
        source_data = source_recordset.read(source_fields_to_read)[0]
        
        _found = False
        _data = False
        
        # search in target model by every search key
        for s_key, t_key in search_keys.items():
            if t_key == 'id':
                _found = target_model.search_count([['id', '=', source_id]])
                if _found:
                    recordset = target_model.browse(source_id)
                    _found = unidecode(recordset.display_name) == unidecode(source_data.display_name)
                    
                    if _found:
                        _data = [source_id]
                        break
            
            else:
                source_key_value = source_data[s_key]
                _found = target_model.search([[t_key, '=', source_key_value]])
                if _found:
                    _data = _found
                    break
        
        return _data
    
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
        
        target_odoo.env.context.update(self.record_create_options)
                
        return True
    
    def delayed_update(self, model, field, data: dict) -> int:
        """
        Create a message record in the target instance with security rights / access rules in mind.
        That is, the author and creator is the same user

        Args:
            data (dict): The data to create the record with.

        Returns:
            int: The id of the created record.
        """
        return self.target_model.create(data)