from odoo.http import request
from odoo import http
import logging
import hashlib

_logger = logging.getLogger(__name__)


class MailChimp(http.Controller):

    @http.route('/mailchimp/webhook/notification/<string:token>', type='http', auth="public", csrf=False, sitemap=False)
    def mailchimp_api(self, token=False, **kwargs):
        # TODO : Work with multi databases.
        mailchimp_account_obj = request.env['mailchimp.accounts'].sudo()
        account_id = mailchimp_account_obj.search([('webhook_token','=',token)])
        if not token or not account_id:
            return 'FAILURE'
        contact_obj = request.env['mailing.contact'].sudo()
        mass_mailling_obj = request.env['mailing.mailing'].sudo()
        mailchimp_list_obj = request.env['mailchimp.lists'].sudo()
        if kwargs.get('data[merges][EMAIL]', False):
            email_address = kwargs['data[merges][EMAIL]']
            mailchimp_id = kwargs['data[web_id]']
            event = kwargs.get('type', False)
            contact_id = contact_obj.search(['|', ('email', '=', email_address), ('subscription_list_ids.mailchimp_id', '=', mailchimp_id)], limit=1)
            mailchimp_list_id = mailchimp_list_obj.search([('list_id', '=', kwargs['data[list_id]'])])
            if not mailchimp_list_id or mailchimp_list_id and mailchimp_list_id.account_id != account_id:
                return 'FAILURE'
            name = email_address
            if kwargs.get('data[merges][FNAME]', False) or kwargs.get('data[merges][LNAME]', False):
                name = "%s %s" % (kwargs.get('data[merges][FNAME]'), kwargs.get('data[merges][LNAME]'))
            md5_email = hashlib.md5(email_address.encode('utf-8')).hexdigest()
            merge_field_dict = {}
            update_partner_required = True
            for custom_field in mailchimp_list_id.merge_field_ids:
                tag = custom_field.tag
                if custom_field.type == 'address':
                    address_dict = {
                        'addr1': kwargs.get('data[merges][{}][addr1]'.format(tag), ''),
                        'addr2': kwargs.get('data[merges][{}][addr2]'.format(tag), ''),
                        'city': kwargs.get('data[merges][{}][city]'.format(tag), ''),
                        'state': kwargs.get('data[merges][{}][state]'.format(tag), ''),
                        'zip': kwargs.get('data[merges][{}][zip]'.format(tag), ''),
                        'country': kwargs.get('data[merges][{}][country]'.format(tag), ''),
                    }
                    merge_field_dict.update({tag: address_dict})
                else:
                    merge_field_dict.update({tag: kwargs.get('data[merges][{}]'.format(tag), '')})
            if kwargs.get('data[action]', '') != 'delete':
                tag_ids = contact_id.fetch_specific_member_data(mailchimp_list_id, md5_email)
                prepared_vals_for_create_partner = mailchimp_list_id._prepare_vals_for_to_create_partner(merge_field_dict)
                prepared_vals_for_create_partner.update({'category_id': [(6, 0, tag_ids.ids)]})
                if not contact_id:
                    if prepared_vals_for_create_partner:
                        mailchimp_list_id.update_partner_detail(name, email_address, prepared_vals_for_create_partner)
                    update_partner_required = False
                    contact_id = contact_id.create({'name': name, 'email': email_address, 'country_id': prepared_vals_for_create_partner.get('country_id', False) or False})
                if contact_id and kwargs.get('data[action]', '') != 'delete':
                    if tag_ids or not tag_ids and contact_id.tag_ids:
                        contact_id.write({'tag_ids': [(6, 0, tag_ids.ids)]})
                    if update_partner_required:
                        mailchimp_list_id.update_partner_detail(name, email_address, prepared_vals_for_create_partner, old_email=contact_id.email)
                    vals = {'list_id': mailchimp_list_id.odoo_list_id.id, 'contact_id': contact_id.id, 'mailchimp_id': mailchimp_id, 'md5_email': md5_email}
                    existing_define_list = contact_id.subscription_list_ids.filtered(
                        lambda x: x.list_id.id == mailchimp_list_id.odoo_list_id.id)
                    if existing_define_list:
                        existing_define_list.write(vals)
                    else:
                        contact_id.subscription_list_ids.create(vals)
                if event == 'unsubscribe':
                    mass_mailling_obj.update_opt_out(contact_id.email, mailchimp_list_id.odoo_list_id.ids, True)
                elif event == 'subscribe':
                    mass_mailling_obj.update_opt_out(contact_id.email, mailchimp_list_id.odoo_list_id.ids, False)
                elif event == 'cleaned':
                    request.env['mail.blacklist'].sudo()._add(email_address)
                    mass_mailling_obj.update_opt_out(contact_id.email, mailchimp_list_id.odoo_list_id.ids, True)
                elif event == 'profile':
                    name = "%s %s" % (kwargs.get('data[merges][FNAME]'), kwargs.get('data[merges][LNAME]'))
                    contact_id.write({'name': name, 'email': kwargs.get('data[merges][EMAIL]')})
            if kwargs.get('data[action]', '') == 'delete':
                if len(contact_id.list_ids) > 1:
                    contact_id.write({'list_ids': [(3, mailchimp_list_id.odoo_list_id.id)]})
                else:
                    contact_id.unlink()
            request._cr.commit()
            return 'SUCCESS'
        return 'FAILURE'
