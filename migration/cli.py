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

def migrate_crm_team():
    """
    A simple data migration for model crm.team model from odoo v14 to v17.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor()

    #: Model name to migrate
    model = 'crm.team'
    
    #: This is a simple migration so no need to make a full fields map, a simple list will do.
    fields = ['name', 'sequence', 'active', 'is_favorite', 'color', 'alias_name', 'alias_contact', 'invoiced_target']

    #: Do the migration
    ex.migrate(model, fields)

def migrate_payment_terms():
    """
    Migrate account.payment.term model from odoo v14 to v17.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor()

    #: Model name to migrate
    model = 'account.payment.term'
    
    #: This is a more advanced migration case so we use a full fields map.
    #: The model account.payment.term.lines needs some work: 
    #:  - field value can be only fixed or in percentage. We use a transformer function to fix this.
    #:    See account_payment_term_line_value_transformer function.
    #:  - field days renamed to nb_days. We use a field mapping to rename it.
    fields = ['name', 'active', 'note', {'line_ids': _account_payment_term_line_value_transformer}]

    #: Do the migration
    ex.migrate(model, fields)

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
    
def migrate_model(model, source_ids=None, batch_size=10, recursion=4, tracking_db=None, debug=False):
    """
    Migrate an Odoo model.

    Args:
        model (str): The model name to migrate.
        source_ids (_type_, optional): _description_. Defaults to None.
        batch_size (int, optional): The batch size for the migration (to avoid timeouts). Defaults to 10.
        recursion (int, optional): Recursion level for related models (how deep to go). Defaults to 4.
        tracking_db (str, optional): The path to a tracking db to reuse it. Defaults to None.
        debug (bool, optional): Debug mode (print/log extra data). Defaults to False.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor(debug=debug)
    
    #: Load the customized field map from the file
    file_path = _get_map_path_for_model(model)
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
    
    dotenv.load_dotenv()
    
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

    # create the parser for the "make-map" command
    parser_make_map = subparsers.add_parser('make-map', 
                                            help='Generate a migration map for the model')
    parser_make_map.add_argument('--model', type=str, required=True,
                                 help='The model to work with')
    parser_make_map.add_argument('--recursion', type=int, required=False,
                                 default=4, help='The recursion level to use (optional, integer, default 4)')

    # create the parser for the "make-tree" command
    parser_nake_tree = subparsers.add_parser('make-tree',
                                             help='Generates a relations tree for the model (useful to understand relations)')
    parser_nake_tree.add_argument('--model', type=str, required=True,
                                  help='The model to work with')
    parser_nake_tree.add_argument('--recursion', type=int, required=False,
                                  default=4, help='The recursion level to use (optional, integer, default 4)')
    
    args = parser.parse_args()
    
    return args

if __name__ == "__main__":
    
    args = _parse_args()
    
    if args.subcommand == 'test':
        test_instances(debug=args.debug)
    elif args.subcommand == 'migrate':
        migration_map = _get_map_path_for_model(model=args.model)
        migrate_model(model=args.model, source_ids=args.ids, batch_size=args.batch_size,
                      recursion=args.recursion, tracking_db=args.tracking_db, debug=args.debug)
    elif args.subcommand == 'make-map':
        make_a_map(model_name=args.model, recursion_level=args.recursion, debug=args.debug)
    elif args.subcommand == 'make-tree':
        make_a_tree(model_name=args.model, recursion_level=args.recursion)

