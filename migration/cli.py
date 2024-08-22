# -*- coding: utf-8 -*-

"""
Command line tool to migrate data from one Odoo instance to another::

    usage: cli.py [-h] [--debug] {test,migrate,make-map,make-tree} ...

    Odoo Data Migration cli tools.

    positional arguments:
        {test,migrate,make-map,make-tree}
                        sub-command help
    test                Perform a test login to the source and target instances
    migrate             Migrate an odoo model
    make-map            Generate a migration map for the model
    make-tree           Generates a relations tree for the model (useful to understand relations)

    options:
        -h, --help            show this help message and exit
        --debug               Enable debug mode
"""

import os
import copy

import argparse

from tools import Pretty

from executor import Executor    
    
    

def _account_payment_term_line_value_transformer(executor: Executor, data: list) -> list:
    """
    To migrate account/payment.term.lines from odoo v14 to v17.
    
    Changes to make:
        - Field value can be only fixed or in percentage.
        - if value == percentage, then value_amount should have a total / sum of 100.0

    Args:
        executor (Executor): The executor instance.
        data (list): The data to format. All model records at once.

    Returns:
        list: The formatted data for the target instance.
    """

    line_ids = data.copy()
    new_line_ids = []

    # to fix percentages
    keep_percent = False
    remaining_percent = 100.0

    for idx, element in enumerate(line_ids):

        # if first element is a percent, then all elements should be in percent
        if idx == 0 and element.get("value") in ["percent", "balance"]:
            keep_percent = True

        if keep_percent:
            element["value"] = "percent"
            if element["value_amount"] == 0.0 or element.get("value") in ["balance", "fixed"]:
                element["value_amount"] = remaining_percent
        remaining_percent -= element.get("value_amount")

        new_line_ids.append(element)

    return new_line_ids

def _crm_lead_categorizacin_transformer(executor: Executor, data: list) -> dict:
    """
    To migrate a custom crm.lead model from odoo v14 to v17.
    
    Changes to make:
        - Custom Field x_studio_categorizacin merges with field description.

    Args:
        executor (Executor): The executor instance.
        data (list): The data to format. All model records at once.

    Returns:
        dict: The formatted data for the target instance.
    """
    _data = []
    for idx, record in enumerate(data):
        
        # process the description field
        description = record.get("description", "")
        if not isinstance(description, str):
            description = ""
        else:
            description = description.replace("\n", "<br>")

        # process the x_studio_categorizacin field                
        x_studio_categorizacin = record.pop("x_studio_categorizacin", "")
        if not isinstance(x_studio_categorizacin, str):
            x_studio_categorizacin = ""
        
        record["description"] = description + "\n" + x_studio_categorizacin
        
        _data.append(record)
            
    return _data

def remove_phantoms(tracking_db, model=None) -> None:
    """
    Remove records that dont exists in the target instance.
    
    Args:
        tracking_db (str): The path to a tracking db to use.
        model (str, optional): The model to work with. Defaults to None (remove phantoms for all models)
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor()

    #: Do the thing
    result = ex.remove_phantom_ids(model, tracking_db)
    
    if result:
        Pretty.print("Phantom ids removed from tracking db:")
        Pretty.print(result)
    elif model:
        Pretty.print("No phantom ids found in tracking db for model %s" % model)
    else:
        Pretty.print("No phantom ids found in tracking db")


def process_decoupled(tracking_db: str, migration_map: str) -> None:
    """
    Process decoupled records from tracking db.
    
    Args:
        tracking_db (str): The path to a tracking db to use.
        migration_map (str): The path to a file migration map to use.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor()
    
    #: Do the migration
    ex.get_tracking_db(tracking_db)
    ex.migration_map.load_from_file(migration_map)
    result = ex.process_decoupled_relations()
    
    if result:
        Pretty.print("Records processed from tracking db:")
        Pretty.print(result)
    else:
        Pretty.print("0 records updated.")


def _get_map_path_for_model(model: str) -> str:
    """
    Search a migration map for a model.
    Search the current (call directory) maps folder for a file with the model name.
    If not found, search the distributed maps directory for a file with the model name.
    
    Args:
        model (str): The model name.
    
    Returns:
        str: The full file path of the migration map for the model.
    """
    # first: search the directory from where the script is called
    _dir = os.getcwd()
    _dir = os.path.join(_dir, "maps")
    _map = os.path.join(_dir, model + ".json")
    
    if os.path.exists(_map):
        return _map
    
    # second: search the distributed maps directory
    else: 
        # get this file path 
        _dir = os.path.dirname(os.path.abspath(__file__))
        
        # up one level to the migration_scripts folder
        _dir = os.path.dirname(_dir)
        
        # and then enter de maps folder
        _dir = os.path.join(_dir, "maps")
        
        _map = os.path.join(_dir, model + ".json")
        if os.path.exists(_map):
            return _map
        else:
            return None    
    
def migrate_model(model, source_ids=None, batch_size=10, recursion=4, tracking_db=None, migration_map=None, debug=False):
    """
    Migrate an Odoo model.

    Args:
        model (str): The model name to migrate.
        source_ids (_type_, optional): _description_. Defaults to None.
        batch_size (int, optional): The batch size for the migration (to avoid timeouts). Defaults to 10.
        recursion (int, optional): Recursion level for related models (how deep to go). Defaults to 4.
        tracking_db (str, optional): The path to a tracking db to reuse it. Defaults to None.
        migration_map (str, optional): The path to a file migration map to use. Defaults to None.
        debug (bool, optional): Debug mode (print/log extra data). Defaults to False.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor(debug=debug)
    
    #: Load the customized field map from the file
    file_path = migration_map or _get_map_path_for_model(model)
    ex.migration_map.load_from_file(file_path=file_path)
    
    #: Do the migration.
    ex.migrate(model, batch_size=batch_size, recursion_level=recursion, source_ids=source_ids, tracking_db=tracking_db)

def make_a_map(model_name: str, recursion_level: int, debug=False):
    """
    Generate a file with a migration map for a model and its relations.
    
    Args:
        model_name (str): The model name.
        recursion_level (int): The recursion level.
    Returns:
        None
    """
    ex = Executor(debug=debug)
    res = ex.migration_map.generate_full_map(model_name=model_name, recursion_level=recursion_level)
    
    _dir = os.getcwd()
    _dir = os.path.join(_dir, "maps")
    
    # create directory if not exists
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    
    file_path = os.path.join(_dir, model_name + ".json")
    Pretty.log(res, file_path=file_path)

def make_a_tree(model_name: str, recursion_level: int):
    """
    Generate a file with a tree map for a model.
    
    Args:
        model_name (str): The model name.
        recursion_level (int): The recursion level.
    
    Returns:
        None
    """
    ex = Executor(debug=True)
    res = ex.migration_map.model_tree(model_name=model_name, recursion_level=recursion_level)
    
    _dir = os.getcwd()
    _dir = os.path.join(_dir, "maps")
    
    # create directory if not exists
    if not os.path.exists(_dir):
        os.makedirs(_dir)
    
    file_path = os.path.join(_dir, model_name +"_tree.txt")
    
    res.save2file(file_path)

def test_instances(debug: bool=False):
    """
    Test login to the source and target instances.
    """
    import os
    import dotenv
    
    env_path = dotenv.find_dotenv(usecwd=True)
    dotenv.load_dotenv(dotenv_path=env_path)
    
    source = {
        "host": os.environ["SOURCE_HOST"],
        "port": os.environ["SOURCE_PORT"],
        "bd": os.environ["SOURCE_DB"],
        "protocol": os.environ.get("SOURCE_PROTOCOL", 'jsonrpc'),
        "user": os.environ["SOURCE_DB_USER"],
        "password": os.environ["SOURCE_DB_PASSWORD"],
    }
    
    target = {
        "host": os.environ["TARGET_HOST"],
        "port": os.environ["TARGET_PORT"],
        "bd": os.environ["TARGET_DB"],
        "protocol": os.environ.get("TARGET_PROTOCOL", 'jsonrpc'),
        "user": os.environ["TARGET_DB_USER"],
        "password": os.environ["TARGET_DB_PASSWORD"],
    }
                
    ex = Executor(debug=debug)
    ex.test_login(instance=source)
    ex.test_login(instance=target)
    
def _parse_args():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: The parsed arguments.
    """
    
    parser = argparse.ArgumentParser(description="Odoo Data Migration tools.")
    parser.add_argument('--debug', required=False, action="store_true", help='Enable debug mode')
    
    subparsers = parser.add_subparsers(dest="subcommand", help='sub-command help')
    
    # create the parser for the "test" command
    parser_test = subparsers.add_parser('test', help='Perform a test login to the source and target instances')
    
    # create the parser for the "migrate" command
    parser_migrate = subparsers.add_parser('migrate', help='Migrate an odoo model')
    parser_migrate.add_argument('--model', type=str, required=True,
                                help='The model to work with')
    parser_migrate.add_argument('--ids', type=int, nargs='+', required=False,
                                default=None, help='IDs to migrate. The whole model is migrated if no ids provided (optional, integers space separated)')
    parser_migrate.add_argument('--batch-size', type=int, required=False,
                                default=10, help='The batch size for the migration (optional, integer, default 10)')
    parser_migrate.add_argument('--recursion', type=int, required=False,
                                default=4, help='The recursion level for the migration (optional, integer, default 4)')
    parser_migrate.add_argument('--tracking-db', type=str, required=False,
                                default=None, help='The path to a tracking db to reuse it (optional, string)')
    parser_migrate.add_argument('--migration-map', type=str, required=False,
                                default=None, help='The path to a file migration map to use (optional, string, default: search for a map file with the same model name to migrate)')

    # create the parser for the "make-map" command
    parser_make_map = subparsers.add_parser('make-map', 
                                            help='Generate a migration map for the model')
    parser_make_map.add_argument('--model', type=str, required=True,
                                 help='The model to work with')
    parser_make_map.add_argument('--recursion', type=int, required=False,
                                 default=4, help='The recursion level to use (optional, integer, default 4)')

    # create the parser for the "make-tree" command
    parser_make_tree = subparsers.add_parser('make-tree',
                                             help='Generates a relations tree for the model (useful to understand relations)')
    parser_make_tree.add_argument('--model', type=str, required=True,
                                  help='The model to work with')
    parser_make_tree.add_argument('--recursion', type=int, required=False,
                                  default=4, help='The recursion level to use (optional, integer, default 4)')
    
    
    # create the parser for the "remove-phantoms" command
    parser_phantoms = subparsers.add_parser('remove-phantoms',
                                             help='Removes records that dont exists in the target instance')
    parser_phantoms.add_argument('--model', type=str, required=False, default=None,
                                  help='The model to work with (optional, string, default: removes phantoms for all models)')
    parser_phantoms.add_argument('--tracking-db', type=str, required=False,
                                default=None, help='The path to a tracking db to use (optional, string)')
 
    # create the parser for the "process-decoupled" command
    parser_decoupled = subparsers.add_parser('process-decoupled',
                                             help='Removes records that dont exists in the target instance')
    parser_decoupled.add_argument('--tracking-db', type=str, required=True,
                                help='The path to a tracking db to use (string)')
    parser_decoupled.add_argument('--migration-map', type=str, required=True,
                                help='The path to a file migration map to use (string)')
    
    args = parser.parse_args()
    
    return args

if __name__ == "__main__":
    
    args = _parse_args()
    
    if args.subcommand == 'test':
        test_instances(debug=args.debug)
    elif args.subcommand == 'migrate':
        migrate_model(model=args.model, source_ids=args.ids, batch_size=args.batch_size,
                      recursion=args.recursion, tracking_db=args.tracking_db,
                      migration_map=args.migration_map, debug=args.debug)
    elif args.subcommand == 'make-map':
        make_a_map(model_name=args.model, recursion_level=args.recursion, debug=args.debug)
    elif args.subcommand == 'make-tree':
        make_a_tree(model_name=args.model, recursion_level=args.recursion)
    elif args.subcommand == 'remove-phantoms':
        remove_phantoms(model=args.model, tracking_db=args.tracking_db)
    elif args.subcommand == 'process-decoupled':
        process_decoupled(tracking_db=args.tracking_db, migration_map=args.migration_map)

