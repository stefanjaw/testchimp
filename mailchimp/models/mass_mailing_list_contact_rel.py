from odoo import api, fields, models, _


class MassMailingContactListRel(models.Model):
    _inherit = 'mailing.contact.subscription'

    @api.depends('list_id')
    def _compute_mailchimp_list_id(self):
        mailchimp_list_obj = self.env['mailchimp.lists']
        for record in self:
            list_id = mailchimp_list_obj.search([('odoo_list_id', '=', record.list_id.id)], limit=1)
            record.mailchimp_list_id = list_id.id

    mailchimp_id = fields.Char("MailChimp ID", readonly=1, copy=False)
    mailchimp_list_id = fields.Many2one("mailchimp.lists", compute="_compute_mailchimp_list_id", string="MailChimp List", store=True)
    md5_email = fields.Char("MD5 Email", readonly=1, copy=False)
