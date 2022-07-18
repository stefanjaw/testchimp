from odoo import api, fields, models, _


class MassMailingList(models.Model):
    _inherit = "mailing.list"

    def _compute_mailchimp_list_id(self):
        mailchimp_list_obj = self.env['mailchimp.lists']
        for record in self:
            list_id = mailchimp_list_obj.search([('odoo_list_id', '=', record.id)])
            if list_id:
                record.mailchimp_list_id = list_id.id
            else:
                record.mailchimp_list_id = False

    mailchimp_list_id = fields.Many2one('mailchimp.lists', compute='_compute_mailchimp_list_id',
                                        string="Associated MailChimp List")
