# -*- coding: utf-8 -*-

import os
import copy

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
        if "x_studio_categorizacin" in record:
            description = record.get("description", "")
            if not isinstance(description, str):
                description = ""
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

def migrate_res_partner():
    """
    Migrate res.partner model from odoo v14 to v17.
    """
    
    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor(debug=True)

    #: Model name to migrate
    model = 'res.partner'
    
    #: The model has some relations so we use **Recursion** set to 1 to migrate upto one layer of related models.
    recursion = 4

    #: Generate the field map 
    # res = ex.migration_map.generate_full_map(model_name=model, recursion_level=recursion)
    
    #: Save the field map to a file for customization.
    #: Its save to run this many times since Pretty.log(), by default, doesn´t overwrite the file.
    file_path = "./" + model + ".json"
    # Pretty.log(res, file_path=file_path)
    
    #: Load the customized field map from the file
    ex.migration_map.load_from_file(file_path=file_path)

    #: Do the migration. There are about 20k records so we use a batch size of 10 to avoid timeouts.
    ex.migrate(model, batch_size=10, recursion_level=recursion)

def migrate_crm_lead():
    """
    Migrate crm.lead model from odoo v14 to v17.
    
    This is a more advanced migration case. Here we use:
    
        - An auto generated fields map to simplify the process.
        - Recursion to migrate also related models.
        - A transformer function to merge custom field x_studio_categorizacin with field description.
          See ``_crm_lead_categorizacin_transformer`` function.

    """

    #: No parameter given to Executor so connection data is loaded from .env file
    ex = Executor(debug=True)

    #: Model name to migrate
    model = 'crm.lead'
    
    
    #: Migrate upto 3 layers of related models.
    #: lead -> partner -> mail.message -> partner
    recursion = 4

    #: Generate the field map 
    # res = ex.migration_map.generate_full_map(model_name=model, recursion_level=recursion)
    
    #: Save the field map to a file for customization.
    #: Its save to run this many times since Pretty.log(), by default, doesn´t overwrite the file.
    file_path = "./" + model + ".json"
    # Pretty.log(res, file_path=file_path)
    
    # ex.add_transformer(model=model, 
    #                    field="x_studio_categorizacin", transformer=crm_lead_categorizacin_transformer)
    # ex.add_transformer(model="account.payment.term", 
    #                    field="line_ids", transformer=account_payment_term_line_ids_transformer)
    
    #: Load the customized field map from the file
    ex.migration_map.load_from_file(file_path=file_path)
    
    #: Do the migration. There are about 1k records so we use a batchs avoid timeouts.
    ex.migrate(model, batch_size=10, recursion_level=recursion)
    
def migrate_some_ids(model, source_ids):
    
    ex = Executor(debug=True)
    
    recursion = 3

    # res = ex.migration_map.generate_full_map(model_name=model, recursion_level=recursion)
    
    file_path = "./" + model + ".json"
    # Pretty.log(res, file_path=file_path)
        
    ex.migration_map.load_from_file(file_path=file_path)
    
    
    ex.migrate(model, batch_size=10, recursion_level=recursion, source_ids=source_ids)

def make_a_map(model_name: str, recursion_level: int):
    """
    Generate a file with a field map for a model.
    
    Args:
        model_name (str): The model name.
        recursion_level (int): The recursion level.
    Returns:
        None
    """
    ex = Executor(debug=True)
    res = ex.migration_map.generate_full_map(model_name=model_name, recursion_level=recursion_level)
    file_path = "./" + model_name + ".json"
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
    file_path = "./" + model_name + "_tree.txt"
    res.save2file(file_path)


def test_instances(use_ssl: bool=False):
    
    import os
    import dotenv
    
    dotenv.load_dotenv()
    
    source = {
        "host": os.environ["SOURCE_HOST"],
        "port": os.environ["SOURCE_PORT"],
        "bd": os.environ["SOURCE_DB"],
        "protocol": 'jsonrpc+ssl' if use_ssl else 'jsonrpc',
        "user": os.environ["SOURCE_DB_USER"],
        "password": os.environ["SOURCE_DB_PASSWORD"],
    }
    
    target = {
        "host": os.environ["TARGET_HOST"],
        "port": os.environ["TARGET_PORT"],
        "bd": os.environ["TARGET_DB"],
        "protocol": 'jsonrpc+ssl' if use_ssl else 'jsonrpc',
        "user": os.environ["TARGET_DB_USER"],
        "password": os.environ["TARGET_DB_PASSWORD"],
    }
                
    ex = Executor(use_ssl=use_ssl, debug=False)
    # ex.test_login(instance=source)
    ex.test_login(instance=target)
    


if __name__ == "__main__":
    
    # gwt current path 
    current_path = os.path.dirname(os.path.abspath(__file__))
    # up one level to the migration_scripts folder
    os.chdir(os.path.dirname(current_path))
    # and then enter de maps folder
    os.chdir("maps")
    
    # test_instances(use_ssl=False)

    migrate_res_partner()   
    # migrate_crm_lead()
   
    # migrate_some_ids(model="crm.lead", source_ids=[29825])
    
    # make_a_map(model_name="mail.message", recursion_level=2)
   
    # make_a_tree("mail.message", 1)
