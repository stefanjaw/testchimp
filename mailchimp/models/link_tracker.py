from odoo import fields,models

class LinkTracker(models.Model):
    _inherit = 'link.tracker'

    mailchimp_id = fields.Char('MailChimp ID',ondelete='cascade')
    mailchimp_link_clicks = fields.Integer('Total Clicks')