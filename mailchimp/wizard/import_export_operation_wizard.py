# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ImportExportOperation(models.TransientModel):
    _name = "mailchimp.import.export.operation"
    _description = "Import/Export Operation"

    account_ids = fields.Many2many('mailchimp.accounts', required=True,
                                   help="Select Account from which you want to perform import/export operation")

    get_lists = fields.Boolean("Lists/Audiences", help="Obtains available lists from MailChimp")
    get_templates = fields.Boolean("Templates", help="Get a list of an account's available templates.")
    get_campaigns = fields.Boolean("Campaigns", help="Get a list of campaigns.")
    camp_since_last_changed = fields.Datetime("Fetch Campaigns Since Last Change", copy=False)

    @api.model
    def default_get(self, fields):
        res = super(ImportExportOperation, self).default_get(fields)
        account = self.env['mailchimp.accounts'].search([],limit=1)
        res.update({'account_ids': [(6, 0, account.ids)],'camp_since_last_changed':account.camp_since_last_changed})
        return res


    def process_operation(self):
        for account in self.account_ids:
            if self.get_lists:
                account.import_lists()
            if self.get_templates:
                account.import_templates()
            if self.get_campaigns:
                account.with_context(camp_since_last_changed=self.camp_since_last_changed).import_campaigns()
        return True
