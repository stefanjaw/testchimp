import re
import hashlib
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

EMAIL_PATTERN = '([^ ,;<@]+@[^> ,;]+)'


def _partner_split_name(partner_name):
    return [' '.join(partner_name.split()[:-1]), ' '.join(partner_name.split()[-1:])]


class massMailingContact(models.Model):
    _inherit = "mailing.contact"

    def get_partner(self, email):
        query = """
                SELECT id 
                  FROM res_partner
                WHERE LOWER(substring(email, '([^ ,;<@]+@[^> ,;]+)')) = LOWER(substring('{}', '([^ ,;<@]+@[^> ,;]+)')) order by id desc limit 1""".format(email.replace("'", "''"))
        self._cr.execute(query)
        return self._cr.fetchone() or False

    def open_contact_view(self):
        [action] = self.env.ref('base.action_partner_form').read()
        partner_record = self.get_partner(self.email)
        action['domain'] = [('id', 'in', partner_record)]
        return action

    @api.depends('subscription_list_ids', 'subscription_list_ids.mailchimp_id', 'subscription_list_ids.list_id')
    def _get_pending_for_export(self):
        available_mailchimp_lists = self.env['mailchimp.lists'].search([])
        lists = available_mailchimp_lists.mapped('odoo_list_id').ids
        for record in self:
            if record.subscription_list_ids.filtered(lambda x: x.list_id.id in lists and not x.mailchimp_id):
                record.pending_for_export = True
            else:
                record.pending_for_export = False

    @api.depends('email')
    def _compute_related_partner_id(self):
        for record in self:
            query = """
            SELECT id 
              FROM res_partner
            WHERE LOWER(substring(email, '([^ ,;<@]+@[^> ,;]+)')) = LOWER(substring('{}', '([^ ,;<@]+@[^> ,;]+)'))""".format(record.email)
            self._cr.execute(query)
            partner_record = self._cr.fetchone()
            if partner_record:
                record.related_partner_id = partner_record[0]
            else:
                record.related_partner_id = False

    pending_for_export = fields.Boolean(compute="_get_pending_for_export", string="Pending For Export", store=True)

    def _prepare_vals_for_merge_fields(self, mailchimp_list_id):
        res_partner_obj = self.env['res.partner']
        self.ensure_one()
        merge_fields_vals = {}
        partner_record = self.get_partner(self.email)
        partner_id = res_partner_obj.browse(partner_record)
        for custom_field in mailchimp_list_id.merge_field_ids:
            if custom_field.type == 'address' and partner_id:
                address = {'addr1': partner_id.street or '',
                           'addr2': partner_id.street2 or '',
                           'city': partner_id.city or '',
                           'state': partner_id.state_id.name if partner_id.state_id else '',
                           'zip': partner_id.zip or '',
                           'country': partner_id.country_id.code if partner_id.country_id else ''}
                merge_fields_vals.update({custom_field.tag: address})
            elif custom_field.tag == 'FNAME':
                merge_fields_vals.update({custom_field.tag: _partner_split_name(self.name)[0] if _partner_split_name(self.name)[0] else _partner_split_name(self.name)[1]})
            elif custom_field.tag == 'LNAME':
                merge_fields_vals.update({custom_field.tag: _partner_split_name(self.name)[1] if _partner_split_name(self.name)[0] else _partner_split_name(self.name)[0]})
            elif custom_field.type in ['date', 'birthday']:
                value = getattr(partner_id or self, custom_field.field_id.name) if custom_field.field_id and hasattr(partner_id or self, custom_field.field_id.name) else ''
                if value:
                    value = value.strftime(custom_field.date_format)
                merge_fields_vals.update({custom_field.tag: value or ''})
            else:
                value = getattr(partner_id or self, custom_field.field_id.name) if custom_field.field_id and hasattr(partner_id or self, custom_field.field_id.name) else ''
                if custom_field.type == 'text' and not isinstance(value, str):
                    value = str(value)
                merge_fields_vals.update({custom_field.tag: value or ''})
        return merge_fields_vals

    def action_export_to_mailchimp(self):
        available_mailchimp_lists = self.env['mailchimp.lists'].search([])
        lists = available_mailchimp_lists.mapped('odoo_list_id').ids
        for record in self:
            lists_to_export = record.subscription_list_ids.filtered(
                lambda x: x.list_id.id in lists and not x.mailchimp_id)
            for list in lists_to_export:
                mailchimp_list_id = list.list_id.mailchimp_list_id
                merge_fields_vals = record._prepare_vals_for_merge_fields(mailchimp_list_id)
                prepared_vals = {"email_address": record.email.lower(),
                                 "status": "unsubscribed" if list.opt_out else "subscribed",
                                 "merge_fields": merge_fields_vals,
                                 "tags": [tag.name for tag in record.tag_ids]}
                response = mailchimp_list_id.account_id._send_request('lists/%s/members' % mailchimp_list_id.list_id,
                                                                      prepared_vals, method='POST')
                if response.get('web_id', False):
                    email_address = response.get('email_address')
                    md5_email = hashlib.md5(email_address.encode('utf-8')).hexdigest()
                    list.write({'mailchimp_id': response.get('web_id', False), 'md5_email': md5_email})
        return True


    def action_update_to_mailchimp(self, subscription_list_ids=[]):
        available_mailchimp_lists = self.env['mailchimp.lists'].search([])
        lists = available_mailchimp_lists.mapped('odoo_list_id').ids
        for record in self:
            lists_to_export = subscription_list_ids or record.subscription_list_ids.filtered(
                lambda x: x.list_id.id in lists and x.mailchimp_id)
            for list in lists_to_export:
                mailchimp_list_id = list.list_id.mailchimp_list_id
                merge_fields_vals = record._prepare_vals_for_merge_fields(mailchimp_list_id)
                prepared_vals = {"email_address": record.email.lower(),
                                 "status": "unsubscribed" if list.opt_out else "subscribed",
                                 'merge_fields' : merge_fields_vals,}
                response = mailchimp_list_id.account_id._send_request(
                    'lists/%s/members/%s' % (mailchimp_list_id.list_id, list.md5_email),
                    prepared_vals, method='PATCH')
                if response.get('web_id', False):
                    email_address = response.get('email_address')
                    md5_email = hashlib.md5(email_address.encode('utf-8')).hexdigest()
                    list.write({'mailchimp_id': response.get('web_id', False), 'md5_email': md5_email})
                tag_res = record.update_tag_on_mailchimp(response, mailchimp_list_id, list.md5_email)
        return True

    def update_tag_on_mailchimp(self, response, mailchimp_list_id, md5_email):
        tag_list = []
        tags = response.get('tags', []) and [tag['name'] for tag in response.get('tags', [])] or []
        tag_name_list = self.tag_ids.mapped('name')
        unique_tags = list(set(tags + tag_name_list))
        for tag in unique_tags:
            if tag in tag_name_list:
                tag_dict = {'name': tag, 'status': 'active'}
            else:
                tag_dict = {'name': tag, 'status': 'inactive'}
            tag_list.append(tag_dict)
        tag_vals = {'tags': tag_list}
        tag_res = mailchimp_list_id.account_id._send_request('lists/%s/members/%s/tags' % (mailchimp_list_id.list_id, md5_email), tag_vals, method='POST')
        return tag_res

    def fetch_specific_member_data(self, mailchimp_list_id, md5_email):
        member_response = mailchimp_list_id.account_id._send_request('lists/%s/members/%s' % (mailchimp_list_id.list_id, md5_email), {}, method='GET')
        tag_list = member_response.get('tags', [])
        tag_ids = self.env['res.partner.category']
        if tag_list:
            tag_ids = self.env['res.partner.category'].create_or_update_tags(tag_list)
        return tag_ids
