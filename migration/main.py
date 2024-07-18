# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

from tools import PrettyPrint

from migrate import Executor


def account_payment_term_line_ids_transformer(executor: Executor, data: dict) -> dict:
    """
    This function format the data dict, only the line_ids field, according to odoo v17 account.payment.term.line_ids model.
    Changes to make:
    * We want only the fields: value, value_amount, days as nb_days, sequence
    * Rename the key 'days' to 'nb_days'
    * payment_term_lines values can be only fixed or in percentage, if %, it should have a total value_amount = 100.0

    Args:
        executor (Executor): The executor instance.
        data (dict): The data to format.

    Returns:
        dict: The formatted data for the target instance.
    """

    desired_keys = {"value", "value_amount", "days"}  # Define the keys you want to keep

    _d = data.copy()

    for record in _d:
        line_ids = record.get(
            "line_ids", []
        )  # line_ids is [(0, 0, {dict}), (0, 0, {dict}), ...]
        new_line_ids = []

        # to fix percentages
        keep_percent = False
        remaining_percent = 100.0

        for idx, element in enumerate(line_ids):
            cmd, id, line_ids_dict = element  # Get the components

            # Filter each line dict to keep only the desired keys
            filtered_line = {
                k: v for k, v in line_ids_dict.items() if k in desired_keys
            }

            # Rename the key 'days' to 'nb_days'
            if "days" in filtered_line:
                filtered_line["nb_days"] = filtered_line.pop("days")

            # if first element is a percent, then all elements should be in percent
            if idx == 0 and filtered_line.get("value") in ["percent", "balance"]:
                keep_percent = True

            if keep_percent:
                filtered_line["value"] = "percent"
                if filtered_line["value_amount"] == 0.0 or filtered_line.get(
                    "value"
                ) in ["balance", "fixed"]:
                    filtered_line["value_amount"] = remaining_percent
            remaining_percent -= filtered_line.get("value_amount")

            new_line_ids.append(
                (cmd, id, filtered_line)
            )  # Update the record with filtered line

        record["line_ids"] = new_line_ids  # Update the record with the new line_ids

    return _d


if __name__ == "__main__":
    
    # connection data is loaded from .env file
    ex = Executor()

    # teams
    # =================================================================================================
    # model = 'crm.team'
    # fields = ['name', 'sequence', 'active', 'is_favorite', 'color', 'alias_name', 'alias_contact', 'invoiced_target']

    # ex.migrate(source, target, model, fields)

    # payment terms
    # =================================================================================================
    # model = 'account.payment.term'
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
    model = "crm.lead"
    fields = [
        {"name": "name"},
        {"user_id": "user_id"},
        {"company_id": "company_id"},
        {"referred": "referred"},
        {"description": "description"},
        {"active": "active"},
        {"type": "type"},
        {"priority": "priority"},
        {"team_id": "team_id"},
        {"stage_id": "stage_id"},
        {"kanban_state": "kanban_state"},
        {"tag_ids": "tag_ids"},
        {"color": "color"},
        {"expected_revenue": "expected_revenue"},
        {"prorated_revenue": "prorated_revenue"},
        {"company_currency": "company_currency"},
        {"date_closed": "date_closed"},
        {"date_open": "date_open"},
        {"day_open": "day_open"},
        {"day_close": "day_close"},
        {"date_last_stage_update": "date_last_stage_update"},
        {"date_conversion": "date_conversion"},
        {"date_deadline": "date_deadline"},
        {"partner_id": "partner_id"},
        {"partner_is_blacklisted": "partner_is_blacklisted"},
        {"contact_name": "contact_name"},
        {"partner_name": "partner_name"},
        {"function": "function"},
        {"title": "title"},
        {"email_from": "email_from"},
        {"phone": "phone"},
        {"mobile": "mobile"},
        {"phone_mobile_search": "phone_mobile_search"},
        {"phone_state": "phone_state"},
        {"email_state": "email_state"},
        {"website": "website"},
        {"lang_id": "lang_id"},
        {"street": "street"},
        {"street2": "street2"},
        {"zip": "zip"},
        {"city": "city"},
        {"state_id": "state_id"},
        {"country_id": "country_id"},
        {"probability": "probability"},
        {"automated_probability": "automated_probability"},
        {"is_automated_probability": "is_automated_probability"},
        {"reveal_id": "reveal_id"},
        {"lead_mining_request_id": "lead_mining_request_id"},
        {"iap_enrich_done": "iap_enrich_done"},
        {"show_enrich_button": "show_enrich_button"},
        {"visitor_ids": "visitor_ids"},
        {"visitor_page_count": "visitor_page_count"},
        {"sale_amount_total": "sale_amount_total"},
        {"quotation_count": "quotation_count"},
        {"sale_order_count": "sale_order_count"},
        {"order_ids": "order_ids"},
        {"campaign_id": "campaign_id"},
        {"source_id": "source_id"},
        {"medium_id": "medium_id"},
        {"activity_ids": "activity_ids"},
        {"activity_state": "activity_state"},
        {"activity_date_deadline": "activity_date_deadline"},
        {"my_activity_date_deadline": "my_activity_date_deadline"},
        {"activity_exception_decoration": "activity_exception_decoration"},
        {"activity_exception_icon": "activity_exception_icon"},
        {"email_normalized": "email_normalized"},
        {"is_blacklisted": "is_blacklisted"},
        {"message_bounce": "message_bounce"},
        {"email_cc": "email_cc"},
        {"message_is_follower": "message_is_follower"},
        {"message_follower_ids": "message_follower_ids"},
        {"message_partner_ids": "message_partner_ids"},
        {"message_ids": "message_ids"},
        {"message_needaction": "message_needaction"},
        {"message_needaction_counter": "message_needaction_counter"},
        {"message_has_error": "message_has_error"},
        {"message_has_error_counter": "message_has_error_counter"},
        {"message_attachment_count": "message_attachment_count"},
        {"website_message_ids": "website_message_ids"},
        {"message_has_sms_error": "message_has_sms_error"},
        {"phone_sanitized": "phone_sanitized"},
        {"phone_sanitized_blacklisted": "phone_sanitized_blacklisted"},
        {"phone_blacklisted": "phone_blacklisted"},
        {"mobile_blacklisted": "mobile_blacklisted"},
        {"activity_user_id": "activity_user_id"},
        {"activity_type_id": "activity_type_id"},
        {"activity_type_icon": "activity_type_icon"},
        {"activity_summary": "activity_summary"},
        {"id": "id"},
        {"display_name": "display_name"},
        {"create_uid": "create_uid"},
        {"create_date": "create_date"},
        {"write_uid": "write_uid"},
        {"write_date": "write_date"},
    ]
    removed = [
        "user_email",
        "user_login",
        "activity_date_deadline_my",
        "date_action_last",
        "meeting_count",
        "lost_reason",
        "ribbon_message",
        "won_status",
        "days_to_convert",
        "days_exceeding_closing",
        "reveal_ip",
        "reveal_iap_credits",
        "reveal_rule_id",
        "message_channel_ids",
        "message_unread",
        "message_unread_counter",
        "message_main_attachment_id",
        "__last_update",
        "x_studio_categorizacin",
    ]
    new = [
        "duration_tracking",
        "activity_calendar_event_id",
        "has_message",
        "rating_ids",
        "user_company_ids",
        "lead_properties",
        "recurring_revenue",
        "recurring_plan",
        "recurring_revenue_monthly",
        "recurring_revenue_monthly_prorated",
        "recurring_revenue_prorated",
        "date_automation_last",
        "email_domain_criterion",
        "lang_code",
        "lang_active_count",
        "lost_reason_id",
        "calendar_event_ids",
        "duplicate_lead_ids",
        "duplicate_lead_count",
        "meeting_display_date",
        "meeting_display_label",
        "partner_email_update",
        "partner_phone_update",
        "is_partner_visible",
        "interest_selection_ids",
        "product_selection_ids",
        "allowed_questions_ids",
    ]

    # ex.migrate(source, target, model, fields)

    res = ex.make_fields_map(model_name=model)

    PrettyPrint(res)
