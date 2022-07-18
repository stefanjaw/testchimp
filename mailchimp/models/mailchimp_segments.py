# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MailChimpSegments(models.Model):
    _name = "mailchimp.segments"
    _description = "Mailchimp Segments"

    name = fields.Char("Name", required=True, copy=False, help="Name of your MailChimp Segments")
    mailchimp_id = fields.Char("MailChimp ID", readonly=True, copy=False)
    list_id = fields.Many2one("mailchimp.lists", string="Associated MailChimp List", ondelete='cascade', required=True, copy=False)

    _sql_constraints = [
        ('mailchimp_id_uniq', 'unique(mailchimp_id)', 'MailChimp ID must be unique per MailChimp Segments!'),
    ]
