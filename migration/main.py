# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

from tools import Pretty

from migrate import Executor


def account_payment_term_line_value_transformer(executor: Executor, data: dict) -> dict:
    """
    This function format the data dict, one record at a time.
    Made for odoo v17 account.payment.term.line_ids model.
    
    Changes to make:
    * payment_term_lines values can be only fixed or in percentage, if %, it should have a total value_amount = 100.0

    Args:
        executor (Executor): The executor instance.
        data (dict): The data to format.

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


def crm_lead_categorizacin_transformer(executor: Executor, data: dict) -> dict:
    pass


if __name__ == "__main__":

    # connection data is loaded from .env file
    ex = Executor()

    # teams
    # =================================================================================================
    model = 'crm.team'
    # fields = ['name', 'sequence', 'active', 'is_favorite', 'color', 'alias_name', 'alias_contact', 'invoiced_target']

    # ex.migrate(source, target, model, fields)

    # payment terms
    # =================================================================================================
    model = 'account.payment.term'
    # fields = ['name', 'active', 'note', {'line_ids': account_payment_term_line_ids_transformer}]

    # ex.migrate(source, target, model, fields)

    # partners
    # =================================================================================================
    # model = "res.partner"
    # fields = [
    #     {"name": "name"},
    #     {"date": "date"},
    #     {"title": "title"}, # this field is a Many2one relation
    #     # {"parent_id": "parent_id"},  # this field is a Many2one relation
    #     {"ref": "ref"},
    #     {"lang": "lang"},
    #     {"tz": "tz"},
    #     {"vat": "vat"},
    #     {"website": "website"},
    #     {"comment": "comment"},
    #     {"credit_limit": "credit_limit"},
    #     {"active": "active"},
    #     {"employee": "employee"},
    #     {"function": "function"},
    #     {"type": "type"},
    #     {"street": "street"},
    #     {"street2": "street2"},
    #     {"zip": "zip"},
    #     {"city": "city"},
    #     {"state_id": "state_id"}, # this field is a Many2one relation
    #     {"country_id": "country_id"}, # this field is a Many2one relation
    #     {"partner_latitude": "partner_latitude"},
    #     {"partner_longitude": "partner_longitude"},
    #     {"mobile": "mobile"},
    #     {"is_company": "is_company"},
    #     {"industry_id": "industry_id"}, # this field is a Many2one relation
    #     {"company_type": "company_type"},
    #     {"color": "color"},
    #     {"partner_share": "partner_share"},
    #     {"company_name": "company_name"},
    #     {"barcode": "barcode"},
    #     {"email": "email"},
    #     {"phone": "phone"},
    #     {"signup_token": "signup_token"},
    #     {"signup_type": "signup_type"},
    #     {"signup_expiration": "signup_expiration"},
    #     {"signup_valid": "signup_valid"},
    #     {"signup_url": "signup_url"},
    #     {"additional_info": "additional_info"},
    #     {"credit": "credit"},
    #     {"debit": "debit"},
    #     {"debit_limit": "debit_limit"},
    #     {"currency_id": "currency_id"}, # this field is a Many2one relation
    #     {"invoice_warn": "invoice_warn"},
    #     {"invoice_warn_msg": "invoice_warn_msg"},
    #     {"supplier_rank": "supplier_rank"},
    #     {"customer_rank": "customer_rank"},
    #     {"sale_warn": "sale_warn"},
    #     {"sale_warn_msg": "sale_warn_msg"},
    #     {"is_blacklisted": "is_blacklisted"},
    #     {"phone_blacklisted": "phone_blacklisted"},
    #     {"mobile_blacklisted": "mobile_blacklisted"},
    #     {"create_date": "create_date"},
    # ]

    # ex.migrate(model, fields, batch_size=100)
   
    # leads
    # =================================================================================================
    # model = "crm.lead"

    recursion = 1

    res = ex.make_fields_map(model_name=model, recursion_level=recursion)
    file_path = "./" + model + ".txt"
    Pretty.log(res, file_path=file_path)
    
    # ex.add_transformer(model=model, 
    #                    field="x_studio_categorizacin", transformer=crm_lead_categorizacin_transformer)
    # ex.add_transformer(model="account.payment.term", 
    #                    field="line_ids", transformer=account_payment_term_line_ids_transformer)
    
    _map = ex.load_fields_map(file_path=file_path)
    
    ex.migrate(model, _map, batch_size=5, recursion_level=recursion)
    
