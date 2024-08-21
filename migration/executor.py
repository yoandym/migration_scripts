# -*- coding: utf-8 -*-

"""
This module provides the necessary classes and methods for data migration between instances via XMLRPC.
"""

import os, sys
import copy
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

from typing import Union

from colorama import Fore, Back, Style
from unidecode import unidecode

import odoorpc
import sqlite3

from tools import Pretty
from mapping import MigrationMap
from exceptions import TooDeepException, UnsupportedRelationException, NoDecoupledRelationException


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
    
    #: Options / Values to set on context. By default disables tracking and subscribe.
    record_create_options = {'tracking_disable': True, 'mail_create_nosubscribe': True}

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
        env_path = find_dotenv(usecwd=True)
        load_dotenv(dotenv_path=env_path)
                
        self.debug = debug
                
        self.recursion_mode = recursion_mode
                        
        if source is None:
            source = {
                "host": os.environ["SOURCE_HOST"],
                "port": os.environ["SOURCE_PORT"],
                "bd": os.environ["SOURCE_DB"],
                "protocol": os.environ.get("SOURCE_PROTOCOL", 'jsonrpc'),
                "user": os.environ["SOURCE_DB_USER"],
                "password": os.environ["SOURCE_DB_PASSWORD"],
            }

        if target is None:
            target = {
                "host": os.environ["TARGET_HOST"],
                "port": os.environ["TARGET_PORT"],
                "bd": os.environ["TARGET_DB"],
                "protocol": os.environ.get("TARGET_PROTOCOL", 'jsonrpc'),
                "user": os.environ["TARGET_DB_USER"],
                "password": os.environ["TARGET_DB_PASSWORD"],
            }
        
        # gets a logged in connection to the source server
        self.source_odoo = self.get_connection(source)
        
        # gets a logged in connection to the target server
        self.target_odoo = self.get_connection(target)
        
        self.migration_map = MigrationMap(self)
        
        self.run_id = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        working_dir = os.getcwd()
        
        # set log and tracking db file and path
        log_file_name = "%s.log" % self.run_id
        self.log_path = os.path.join(working_dir, log_file_name)
        

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
        odoo = odoorpc.ODOO(host=instance['host'], port=instance['port'], protocol=instance['protocol'])
        
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
        
        source_model = self.source_odoo.env[model_name]
        target_model = self.target_odoo.env[target_model_name]
        
        source_fields_to_read = list(search_keys.keys())
        target_fields_to_read = list(search_keys.values())
        
        source_recordset = source_model.browse(source_id)
        source_data = source_recordset[0]
        
        _data = False
        
        # search in target model by every search key
        for s_key, t_key in search_keys.items():
            _found = False
            if t_key.lower() == 'id':
                _found = target_model.search_count([['id', '=', source_id]])
                if _found:
                    recordset = target_model.browse(source_id)
                    _found = unidecode(recordset.display_name) == unidecode(source_data.display_name)
                    
                    if _found:
                        _data = [source_id]
                        break
            
            else:
                source_key_value = getattr(source_data, s_key) 
                if source_key_value:
                    _found = target_model.search([[t_key, '=', source_key_value]])
                    if _found:
                        _data = _found
                        break
        
        return _data
 
    def search_in_tracking_db(self, source_model_name: str, source_id: int) -> list:
        """
        Search for records (source_model_name and source_id) in the tracking database.
        If found return the target_model_name and target_id.

        Args:
            source_model_name (str): Source model name to search for.
            source_id (int): Source id to search for.

        Returns:
            list: A list with the target_model_name and target_id if found, an empty list otherwise.
        """
        cursor = self.tracking_db.cursor()
        cursor.execute('SELECT target_model_name, target_id FROM ids_tracking WHERE source_model_name = ? AND source_id = ?', (source_model_name, source_id))
        record = cursor.fetchone()
        return record if record else []
    
    def migrate(self, model_name: str, migration_map: Union[dict, list]=None, recursion_level: int=0, batch_size=50, source_ids: list=None, tracking_db=None) -> bool:
        """
        Migrate data from source to target

        Args:
            model_name (str): The model name to migrate.
            migration_map (Union[dict, list]): The migration map to use. Defaults to None.
            recursion_level (int): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.
            batch_size (int): The batch size to use when migrating a large dataset. Defaults to 100.
            source_ids (list): A list of source ids to migrate. If present it will migrate only the provided ids. Defaults to None.
            tracking_db (str): A tracking database file path to reuse it. Defaults to None (creates a new one).
        """
        
        if migration_map is None and self.migration_map.map is None:
            print('Migration map not provided')
            return False
        elif migration_map is not None:
            self.migration_map.normalice_fields(migration_map)
        
        # get or initialize the tracking db
        self._get_tracking_db(tracking_db)
        
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
                
        # get source ids to migrate 
        if not source_ids:
            ids = self.source_model.search([])
        else:
            ids = source_ids
        
        # take into consideration the batch size
        batches = [ids]
        if len(ids) > batch_size:
            batches = self._split_into_batches(ids, batch_size)
            
        for batch in batches:
            src_data = []
            tgt_data = []
            
            try:
                # get data from source instance
                recordset = self.source_model.browse(batch)
                src_data = recordset.read(source_fields)
                
                # format it to be feed in the target instance
                tgt_data = self._format_data(model_name=model_name, data=src_data, recursion_level=recursion_level)

                # creates the records at target instance
                res = self.target_model.create(tgt_data)
                
                self._track_ids(model_name, batch, self.migration_map.get_target_model(model_name), res)
                
                self._process_decoupled_relations()
                
                # print the results
                _message = 'Model %s IDs migrated: %s' % (model_name, batch)                
                print(_message)
                
            except Exception as e:
                result_message = 'Processing error for model % s. Source IDs: %s' % (model_name, batch)
                
                l = {"msg": result_message, "error": repr(e)}
                if self.debug:
                    l.update({"source_data": src_data, "target_data": tgt_data})
                Pretty.log(l, self.log_path, overwrite=True, mode='a')
                
                print(result_message)
                    
        return True
    
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
            fields = list(record.keys())
            has_a_decoupled_relation = self._has_decoupled_relation(fields)
            
            for column_name in fields:
                
                # drop decoupled relations fields, will be processed later
                if column_name in ["res_id"] and has_a_decoupled_relation:
                    record.pop(column_name)
                    continue
                
                # drop other unwanted fields
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
                        new_source_model_name = model_fields_metadata[column_name]['relation']
                        if recursion_level > 0:
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
                        new_source_model_name = model_fields_metadata[column_name]['relation']
                        if self.recursion_mode == 'w':
                            print('Removing %s.%s --> %s from migration because relation type not supported.' % (model_name, column_name, new_source_model_name))
                            record.pop(column_name)
                            continue
                        else:
                            raise UnsupportedRelationException('Relation type %s is not supported yet' % field_type)
                except Exception as e:
                    Pretty.log('Error processing %s.%s --> %s' % (model_name, column_name, new_source_model_name), self.log_path, overwrite=True, mode='a')
                    raise e
                
                # test for and do field name changes / transformations with callables
                field_mapping_value = model_fields_map[column_name]
                if column_name != field_mapping_value:
                    
                    # test for and process callables
                    # has to be done after the relational fields processing
                    # process the whole data set. 
                    # At map load time callables are detected for every field
                    if callable(field_mapping_value):
                        # update data before processing callables
                        _data[idx] = record
                        _data = field_mapping_value(self, _data)
                    else:
                        # do the field name change
                        record[field_mapping_value] = record.pop(column_name)
            
            _data[idx] = record
            
        return _data
    
    def _process_relation(self, model_name: str, relation_type: str, field_name: str, data: Union[dict, list], recursion_level: int = 0) -> Union[int, list]:
        """
        Process / traverses the relational fields in data

        Args:
            model_name (str): The model name to process relations for.
            relation_type (str): The type of relation to process.
            field_name (str): The field name to process.
            data (Union[dict, list]): The data to process.
            recursion_level (int): The recursion level to apply. Relational field deeper than recursion_level wont be considered/formatted. Defaults to 0.
        
        Returns:
            data (Union[int, list]): The data for the relational field ready to feed into the target instance.
        
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
        
        # if model has a decoupled relation, handle it like row by row
        has_a_decoupled_relation = self._has_decoupled_relation(model_field_list)
        
        if relation_type == 'many2many' or (relation_type == 'one2many' and has_a_decoupled_relation):
            
            _data = []
            
            # get the source data
            # data Ex: [35, 33, 34] Note the order is unknown/random 
            related_source_ids = data
            
            # turns outs that not every model has the automatic field create_date
            # if create_date is present, order by it, because its important for example for messages
            if "create_date" in model_fields_metadata.keys():
                related_source_ids = source_model.search([['id', 'in', data]], order='create_date ASC')
                
            related_source_recordset = source_model.browse(related_source_ids)
            related_source_data = related_source_recordset.read(model_field_list)
                               
            for record in related_source_data:
                record_id = record['id']
                
                # first search in the tracking db
                _found = self.search_in_tracking_db(model_name, record_id)
                
                if _found:
                    _data.append(_found[1])
                else:
                    # the search remote
                    _found = self.search_in_target(model_name=model_name, 
                                                    source_id=record_id, 
                                                    search_keys=search_keys, 
                                                    target_model_name=target_model_name)
                    if _found:
                        _data.append(_found[0])
                        
                        # tracking
                        self._track_ids(model_name, [record_id], target_model_name, [_found[0]])
                    else:
                        # data may contain new relations, so we have to format them
                        _new_data = self._format_data(model_name=model_name, 
                                                    data=record, 
                                                    recursion_level=recursion_level - 1)
                        
                        
                        _id = target_model.create(_new_data)
                        _data.append(_id[0])
                    
                        # tracking
                        self._track_ids(source_model_name=model_name, source_ids=[record_id], 
                                        target_model_name=target_model_name, target_ids=[_id[0]],
                                        has_decoupled_relation=has_a_decoupled_relation, update_required=has_a_decoupled_relation)
                                                        
        elif relation_type == 'one2many':
            _data = []
            
            # get the source data
            # data Ex: [35, 33, 34] Note the order is unknown/random 
            related_source_ids = data
            
            # turns outs that not every model has the automatic field create_date
            # if create_date is present, order by it, because its important for example for messages
            if "create_date" in model_fields_metadata.keys():
                related_source_ids = source_model.search([['id', 'in', data]], order='create_date ASC')
                
            related_source_recordset = source_model.browse(related_source_ids)
            related_source_data = related_source_recordset.read(model_field_list)

            # data may contain new relations, so we have to format them
            _new_data = self._format_data(model_name=model_name, data=related_source_data, recursion_level=recursion_level - 1)    
            _data = [(0, 0, e) for e in _new_data]
            
            #: TODO how to do tracking in this case?

        elif relation_type == 'many2one':
            
            # get the source data
            related_source_id, related_source_display_name = data # Ex: [33, 'MXN']                            
            
            #first search in the tracking db
            _found = self.search_in_tracking_db(model_name, related_source_id)
            
            if _found:
                _data = _found[1]
            else:
                # search it by every search key
                _found = self.search_in_target(model_name=model_name, 
                                                source_id=related_source_id, 
                                                search_keys=search_keys, 
                                                target_model_name=target_model_name)
                
                # if still not found, create it
                if not _found:
                    
                    related_source_recordset = source_model.browse(related_source_id)
                    related_source_data = related_source_recordset.read(model_field_list)[0]

                                        
                    # data may contain new relations, so we have to format them
                    new_target_data = self._format_data(model_name=model_name, data=related_source_data, recursion_level=recursion_level - 1)

                    # create the record in target instance/model
                    _found = target_model.create(new_target_data)

                _data = _found[0]
                
                # tracking
                has_a_decoupled_relation = self._has_decoupled_relation(model_field_list)
                self._track_ids(source_model_name=model_name, source_ids=[related_source_id], 
                                target_model_name=target_model_name, target_ids=[_data],
                                has_decoupled_relation=has_a_decoupled_relation, update_required=has_a_decoupled_relation)
        
        else:
            raise UnsupportedRelationException('%s relations are not supported yet', relation_type)
          
        return _data

    def _get_decoupled_relation_fields(self, model_name: str) -> list:
        """
        Get the fields names of the decoupled relation schema used in the model.
        
        Args:
            model_name (str): The model name to get the decoupled relation fields from.
        
        Returns:
            list: The fields names of the decoupled relation schema used in the model (model_field, id_field)
        """
        decoupled_relation_fields_v1 = ["model", "res_id"]
        decoupled_relation_fields_v2 = ["res_model", "res_id"]
        
        decoupled_relation_fields = None
        
        model_map = self.migration_map.get_mapping(model_name)
        field_list = model_map['fields'].keys()
        # if both fields are present in version, use it
        if all([field in field_list for field in decoupled_relation_fields_v1]):
            decoupled_relation_fields = decoupled_relation_fields_v1
        elif all([field in field_list for field in decoupled_relation_fields_v2]):
            decoupled_relation_fields = decoupled_relation_fields_v2
        else:
            raise NoDecoupledRelationException('No decoupled relation found in model %s' % model_name)
        
        return decoupled_relation_fields

    def _process_decoupled_relations(self):
        """
        Process / updates records with special fields used to make a decoupled relation to other models.
        This are fields that points to another record using a ``model``and ``res_id`` schema. 
        ( A record maybe not yet created when the model is being processed) 
        
        Example:
            - Models with a messages_ids field, pointing to a mail.message which in turn has the fields ``model`` and ``res_id``
              that points back to a parent/associated model

        """
                
        # get records with decoupled relations requiring an update
        cursor = self.tracking_db.cursor()
        cursor.execute('SELECT source_model_name, source_id, target_model_name, target_id FROM ids_tracking WHERE has_decoupled_relation = 1 AND update_required = 1')
        records = cursor.fetchall()
        
        for rec in records:
            try:
                source_model_name, source_id, target_model_name, target_id = rec
                source_model = self.source_odoo.env[source_model_name]
                target_model = self.target_odoo.env[target_model_name] 
                
                # Some models use a ``model`` field name while others use a ``res_model`` field name :|
                model_field, id_field = self._get_decoupled_relation_fields(source_model_name)
                decoupled_relation_fields = [model_field, id_field]
                
                source_recordset = source_model.browse(source_id)
                source_data = source_recordset.read(decoupled_relation_fields)
                source_data = source_data[0]
                
                related_model_name = source_data[model_field]
                related_id = source_data[id_field]
                
                # search in the ids_tracking db for the related record
                cursor.execute('SELECT source_model_name, source_id, target_model_name, target_id FROM ids_tracking WHERE source_model_name = ? AND source_id = ?', (related_model_name, related_id))
                related_rec = cursor.fetchone()
                if related_rec:
                    related_source_model_name, related_source_id, related_target_model_name, related_target_id = related_rec
                                        
                    target_model.write([target_id], {model_field: related_target_model_name, id_field: related_target_id})
                                        
                    # update the ids_tracking db
                    cursor.execute('UPDATE ids_tracking SET update_required = 0 WHERE source_model_name = ? AND source_id = ?', (source_model_name, source_id))
                    self.tracking_db.commit()
                else:
                    message = "Could not process decoupled relation. %s.id=%s --> %s.id=%s" % (source_model_name, source_id, target_model_name, target_id)
                    error = "Record not found in ids_tracking db. %s.id=%s" % (related_model_name, related_id)
                    log_entry = {'message': message, 'error': error}
                    Pretty.log(log_entry, self.log_path, overwrite=True, mode='a')
                    print(message)
            except Exception as e:
                
                message = "Could not process decoupled relation. %s.id=%s --> %s.id=%s" % (source_model_name, source_id, target_model_name, target_id)
                log_entry = {'message': message, 'error': repr(e)}
                
                Pretty.log(log_entry, self.log_path, overwrite=True, mode='a')
                print(message)

    def _init_tracking_db(self):
        """
        Initialize the ids tracking database
        """
        cursor = self.tracking_db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ids_tracking
                        (
                            source_model_name TEXT,
                            source_id INTEGER, 
                            target_model_name TEXT,
                            target_id INTEGER,
                            has_decoupled_relation BOOLEAN DEFAULT FALSE,
                            update_required BOOLEAN DEFAULT FALSE
                        )
                        ''')
        self.tracking_db.commit()

    def _get_tracking_db(self, tracking_db: str=None) -> None:
        # get or initialize the tracking db
        working_dir = os.getcwd()
        if not tracking_db:
            db_file_name = "%s.db" % self.run_id
            db_path = os.path.join(working_dir, db_file_name)
        
            # get a db connection and initialize it
            self.tracking_db = sqlite3.connect(db_path)
            self._init_tracking_db()
        else:
            self.tracking_db = sqlite3.connect(tracking_db)

    def _track_ids(self, source_model_name: str, source_ids: list, target_model_name: str, target_ids: list, has_decoupled_relation: bool=False, update_required:bool=False) -> None:
        """
        Track the ids of the migrated records into a sqlite database.
        Tracks also if a model / record has a decoupled relation using a ``model``and ``res_id`` schema.
        and if an update is required in the target instance.
        
        If a record has a decoupled relation, the model-res_id record may not exist yet in the target instance,
        so, after all the records are created, the res_id has to be updated.

        Args:
            source_model_name (str): The source model name.
            source_ids (list): The source ids.
            target_model_name (str): The target model name.
            target_ids (list): The target ids.
            has_decoupled_relation (bool): If the model has a decoupled relation using a ``model``and ``res_id`` schema. Defaults to False.
            update_required (bool): If an update is required in the target instance. Defaults to False.
        """
       
        cursor = self.tracking_db.cursor()
        
        for idx, source_id in enumerate(source_ids):
            try:
                target_id = target_ids[idx]
                cursor.execute('INSERT INTO ids_tracking VALUES (?, ?, ?, ?, ?, ?)', 
                                        (source_model_name, source_id, target_model_name, target_id, has_decoupled_relation, update_required))
                self.tracking_db.commit()
            except Exception as e:
                Pretty.log(repr(e), self.log_path, overwrite=True, mode='a')
                message = "Error tracking ids. %s.id=%s --> %s.id=%s" % (source_model_name, source_ids, target_model_name, target_ids)
                Pretty.log(message, self.log_path, overwrite=True, mode='a')
                print(message)

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
    
    def _has_decoupled_relation(self, fields: list) -> bool:
        """
        Check if there is decoupled relation schema with another model

        Args:
            fields (list): the fields list to check.

        Returns:
            bool: True if the model has a decoupled relation, False otherwise.
        """
        
        if ("model" in fields and "res_id" in fields) or \
            ("res_model" in fields and "res_id" in fields): # Yes! some models use a model field while others use a res_model field :|
            return True
        
        return False