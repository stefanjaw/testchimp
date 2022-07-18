# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ParterExportMailchimp(models.TransientModel):
    _name = 'partner.export.mailchimp'
    _description = "Partner Export Mailchimp"

    odoo_list_ids = fields.Many2many('mailchimp.lists', string='MailChimp Lists', domain=[('odoo_list_id', '!=', False)])

    def get_mailing_contact_id(self, partner_id, force_create=False):
        mailing_contact_obj = self.env['mailing.contact']
        if not partner_id.email:
            return False
        query = """
                SELECT id 
                  FROM mailing_contact
                WHERE LOWER(substring(email, '([^ ,;<@]+@[^> ,;]+)')) = LOWER(substring('{}', '([^ ,;<@]+@[^> ,;]+)'))""".format(
            partner_id.email.replace("'","''"))
        self._cr.execute(query)
        contact_id = self._cr.fetchone()
        contact_id = contact_id[0] if contact_id else False
        prepared_vals = {'name': partner_id.name, 'email': partner_id.email, 'tag_ids': [(6, 0, partner_id.category_id.ids)], 'country_id': partner_id.country_id.id}
        if not contact_id:
            contact_id = mailing_contact_obj.search([('email', '=', partner_id.email)], limit=1)
            contact_id = contact_id and contact_id.id or False
        if contact_id:
            contact_id = mailing_contact_obj.browse(contact_id)
            contact_id.write(prepared_vals)
        if not contact_id and force_create:
            contact_id = mailing_contact_obj.create(prepared_vals)
        return contact_id.id

    def action_export_partner_mailchimp(self):
        mailing_contact_obj = self.env['mailing.contact']
        partner_ids = self.env['res.partner'].search([('id', 'in', self._context.get('active_ids', []))])
        for partner_id in partner_ids:
            for odoo_list_id in self.odoo_list_ids:
                contact_id = self.get_mailing_contact_id(partner_id, force_create=True)
                if contact_id:
                    contact_id = mailing_contact_obj.browse(contact_id)
                    if odoo_list_id.id not in contact_id.subscription_list_ids.mapped('list_id').mapped('mailchimp_list_id').ids:
                        vals = {'list_id': odoo_list_id.odoo_list_id.id, 'contact_id': contact_id.id}
                        contact_id.subscription_list_ids.create(vals)
                        contact_id.action_export_to_mailchimp()
        return True

    def action_update_partner_mailchimp(self):
        mailing_contact_obj = self.env['mailing.contact']
        partner_ids = self.env['res.partner'].search([('id', 'in', self._context.get('active_ids', []))])
        for partner_id in partner_ids:
            contact_id = self.get_mailing_contact_id(partner_id)
            if contact_id:
                contact_id = mailing_contact_obj.browse(contact_id)
                contact_id.action_update_to_mailchimp()
        return True
