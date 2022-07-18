# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MailChimpMergeFields(models.Model):
    _name = "mailchimp.merge.fields"
    _description = "Mailchimp Merge Fields"

    name = fields.Char("Name", required=True, copy=False, help="Name of your MailChimp Merge Fields")
    merge_id = fields.Char("Merge ID", readonly=True, copy=False)
    tag = fields.Char("Merge Field Tag", help="The tag used in Mailchimp campaigns and for the /members endpoint.")
    type = fields.Selection(
        [('text', 'Text'), ('number', 'Number'), ('address', 'Address'), ('phone', 'Phone'), ('date', 'Date'), ('radio', 'Radio'), ('dropdown', 'Dropdown'),
         ('birthday', 'Birthday'), ('zip', 'Zip'), ('imageurl', 'ImageURL'), ('url', 'URL')])
    date_format = fields.Char('Date Format', copy=False)
    required = fields.Boolean("Required?", copy=False, help="Merge field is required or not.")
    public = fields.Boolean("Visible?", copy=False, help="Whether the merge field is displayed on the signup form.")
    default_value = fields.Char("Default Value", help="The default value for the merge field if null.")
    display_order = fields.Char("Display Order", help="The order that the merge field displays on the list signup form.")
    list_id = fields.Many2one("mailchimp.lists", string="Associated MailChimp List", ondelete='cascade', required=True, copy=False)
    field_id = fields.Many2one('ir.model.fields', string='Odoo Field', help="""Odoo will fill value of selected field while contact is going to export or update""",
                               domain="[('model_id.model', '=', 'res.partner'), ('ttype', 'not in', ['one2many','many2one','many2many'])]")

    _sql_constraints = [
        ('merge_id_list_id_uniq', 'unique(merge_id, list_id)', 'Merge ID must be unique per MailChimp Lists!'),
    ]
