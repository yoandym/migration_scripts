# -*- coding: utf-8 -*-

import os
import copy

from tools import Pretty

from executor import Executor    
    
    

def _account_payment_term_line_value_transformer(executor: Executor, data: list) -> dict:
    """
    To migrate account/payment.term.lines from odoo v14 to v17.
    
    Changes to make:
        - Field value can be only fixed or in percentage.
        - if value == percentage, then value_amount should have a total / sum of 100.0

    Args:
        executor (Executor): The executor instance.
        data (list): The data to format. All model records at once.

    Returns:
        dict: The formatted data for the target instance.
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
    _data = copy.deepcopy(data)
    for record in _data:
        if "x_studio_categorizacin" in record:
            description = record.get("description", "")
            if not isinstance(description, str):
                description = ""
            x_studio_categorizacin = record.pop("x_studio_categorizacin", "")
            if not isinstance(x_studio_categorizacin, str):
                x_studio_categorizacin = ""
            
            record["description"] = description + "\n" + x_studio_categorizacin
            
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
    
    
def data_test():
    
    ex = Executor(debug=True)

    model = 'res.country.state'
    
    recursion = 1

    res = ex.migration_map.generate_full_map(model_name=model, recursion_level=recursion)
    
    file_path = "./" + model + ".json"
    Pretty.log(res, file_path=file_path)
        
    # ex.migration_map.load_from_file(file_path=file_path)
    
    # ex.migrate(model, batch_size=10, recursion_level=recursion)

if __name__ == "__main__":
    
    # gwt current path 
    current_path = os.path.dirname(os.path.abspath(__file__))
    # up one level to the migration_scripts folder
    os.chdir(os.path.dirname(current_path))
    # and then enter de maps folder
    os.chdir("maps")

    migrate_res_partner()   
    # migrate_crm_lead()
   
    # data_test()