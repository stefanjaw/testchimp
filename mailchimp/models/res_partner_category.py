from odoo import fields, api, models

class ResPartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    mailchimp_id = fields.Char('Mailchimp Id')

    def create_or_update_tags(self, values_dict, account=False):
        tag_ids = self
        for val in values_dict:
            tag_id = val.get('id')
            existing_list = self.search([('mailchimp_id', '=', tag_id)])
            val.update({'mailchimp_id': val.pop('id')})
            if not existing_list:
                existing_list = self.search([('name', '=', val.get('name'))])
                if not existing_list:
                    existing_list = self.create(val)
                else:
                    existing_list.write(val)
            else:
                existing_list.write(val)
            tag_ids += existing_list
        return tag_ids
