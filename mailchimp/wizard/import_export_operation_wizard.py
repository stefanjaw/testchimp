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

    @api.model
    def default_get(self, fields):
        res = super(ImportExportOperation, self).default_get(fields)
        accounts = self.env['mailchimp.accounts'].search([])
        res.update({'account_ids': [(6, 0, accounts.ids)]})
        return res


    def process_operation(self):
        for account in self.account_ids:
            if self.get_lists:
                account.import_lists()
            if self.get_templates:
                account.import_templates()
            if self.get_campaigns:
                account.import_campaigns()
        return True
