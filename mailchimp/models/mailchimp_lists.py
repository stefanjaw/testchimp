import logging
import hashlib

_logger = logging.getLogger(__name__)
from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError, Warning
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

EMAIL_PATTERN = '([^ ,;<@]+@[^> ,;]+)'
unwanted_data = ['_links', 'modules']
replacement_of_key = [('id', 'list_id')]
DATE_CONVERSION = ['date_created', 'last_sub_date', 'last_unsub_date', 'campaign_last_sent']

NOT_REQUIRED_ON_UPDATE = ['color', 'list_id', 'web_id', 'from_name', 'from_email', 'subject', 'partner_id', 'account_id',
                          'date_created', 'list_rating', 'auto_export_filter', 'auto_export_contact', 'segment_ids', 'merge_field_ids', 'member_since_last_changed',
                          'subscribe_url_short', 'subscribe_url_long', 'beamer_address', 'id', 'display_name',
                          'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update', '__last_update',
                          'statistics_ids', 'stats_overview_ids', 'stats_audience_perf_ids', 'stats_campaign_perf_ids',
                          'stats_since_last_campaign_ids', 'lang_id', 'odoo_list_id', 'last_create_update_date', 'is_update_required', 'contact_ids', 'subscription_contact_ids',
                          'mailchimp_list_id']


class MassMailingList(models.Model):
    _inherit = "mailing.list"

    def _compute_contact_nbr(self):
        if self.ids:
            self.env.cr.execute('''
                select
                    list_id, count(*)
                from
                    mailing_contact_list_rel r
                    left join mailing_contact c on (r.contact_id=c.id)
                    left join mail_blacklist bl on c.email_normalized = bl.email and bl.active
                where
                    list_id in %s AND
                    COALESCE(r.opt_out,FALSE) = FALSE
                    AND c.email_normalized IS NOT NULL
                    AND bl.id IS NULL
                group by
                    list_id
            ''', (tuple(self.ids),))
            data = dict(self.env.cr.fetchall())
            for mailing_list in self:
                mailing_list.contact_nbr = data.get(mailing_list.id, 0)
        else:
            self.contact_nbr = 0

    contact_nbr = fields.Integer(compute="_compute_contact_nbr", string='Number of Contacts')


class MailChimpLists(models.Model):
    _name = "mailchimp.lists"
    _inherits = {'mailing.list': 'odoo_list_id'}
    _description = "MailChimp Audience"

    def _compute_contact_unsub_nbr(self):
        if self.ids:
            self.env.cr.execute('''
                select
                    list_id, count(*)
                from
                    mailing_contact_list_rel r
                    left join mailing_contact c on (r.contact_id=c.id)
                    left join mail_blacklist bl on c.email_normalized = bl.email and bl.active
                where
                    list_id in %s AND
                    COALESCE(r.opt_out,TRUE) = TRUE
                    AND c.email_normalized IS NOT NULL
                    AND bl.id IS NULL
                group by
                    list_id
            ''', (tuple(self.odoo_list_id.ids),))
            data = dict(self.env.cr.fetchall())
            for mailing_list in self:
                mailing_list.contact_unsub_nbr = data.get(mailing_list.odoo_list_id.id, 0)
        else:
            self.contact_unsub_nbr = 0

    def _compute_contact_cleaned_nbr(self):
        if self.ids:
            self.env.cr.execute('''
                select
                    list_id, count(*)
                from
                    mailing_contact_list_rel r
                    left join mailing_contact c on (r.contact_id=c.id)
                    left join mail_blacklist bl on c.email_normalized = bl.email and bl.active
                where
                    list_id in %s
                    AND c.email_normalized IS NOT NULL
                    AND bl.id IS NOT NULL
                group by
                    list_id
            ''', (tuple(self.odoo_list_id.ids),))
            data = dict(self.env.cr.fetchall())
            for mailing_list in self:
                mailing_list.contact_cleaned_nbr = data.get(mailing_list.odoo_list_id.id, 0)
        else:
            self.contact_cleaned_nbr = 0

    def _compute_contact_total_nbr(self):
        if self.ids:
            self.env.cr.execute('''
                select
                    list_id, count(*)
                from
                    mailing_contact_list_rel r
                    left join mailing_contact c on (r.contact_id=c.id)
                    left join mail_blacklist bl on c.email_normalized = bl.email and bl.active
                where
                    list_id in %s
                    AND c.email_normalized IS NOT NULL
                    AND bl.id IS NULL
                group by
                    list_id
            ''', (tuple(self.odoo_list_id.ids),))
            data = dict(self.env.cr.fetchall())
            for mailing_list in self:
                mailing_list.contact_total_nbr = data.get(mailing_list.odoo_list_id.id, 0)
        else:
            self.contact_total_nbr = 0

    def _is_update_required(self):
        for record in self:
            if record.write_date and record.last_create_update_date and record.write_date > record.last_create_update_date:
                record.is_update_required = True
            else:
                record.is_update_required = False

    # name = fields.Char("Name", required=True, help="This is how the list will be named in MailChimp.")
    color = fields.Integer('Color Index', default=0)
    list_id = fields.Char("Audience ID", copy=False, readonly=True)
    web_id = fields.Char("Website Identification", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Contact", ondelete='restrict')
    permission_reminder = fields.Text("Permission Reminder", help="Remind recipients how they signed up to your list.")
    use_archive_bar = fields.Boolean("Use Archive Bar",
                                     help="Whether campaigns for this list use the Archive Bar in archives by default.")

    notify_on_subscribe = fields.Char("Email Subscribe Notifications To",
                                      help="The email address to send subscribe notifications to. \n Additional email addresses must be separated by a comma.")
    notify_on_unsubscribe = fields.Char("Email Unsubscribe Notifications To",
                                        help="The email address to send unsubscribe notifications to. \n Additional email addresses must be separated by a comma.")
    date_created = fields.Datetime("Creation Date", readonly=True)
    list_rating = fields.Selection([('0', '0'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')],
                                   "List Rating")
    email_type_option = fields.Boolean("Let users pick plain-text or HTML emails.",
                                       help="Whether the list suports multiple formats for emails. When set to true, subscribers can choose whether they want to receive HTML or plain-text emails. When set to false, subscribers will receive HTML emails, with a plain-text alternative backup.")
    subscribe_url_short = fields.Char("Subscribe URL Short", readonly=True)
    subscribe_url_long = fields.Char("Subscribe URL Long", readonly=True,
                                     help="The full version of this list’s subscribe form (host will vary).")
    beamer_address = fields.Char("Beamer Address", readonly=True)
    visibility = fields.Selection([('pub', 'Yes. My campaigns are public, and I want them to be discovered.'),
                                   ('prv', 'No, my campaigns for this list are not public.')], default='pub',
                                  help="Whether this list is public or private.")
    double_optin = fields.Boolean("Enable double opt-in",
                                  help="Whether or not to require the subscriber to confirm subscription via email.")
    has_welcome = fields.Boolean("Send a Final Welcome Email",
                                 help="Whether or not this list has a welcome automation connected. Welcome Automations: welcomeSeries, singleWelcome, emailFollowup.")
    marketing_permissions = fields.Boolean("Enable GDPR fields",
                                           help="Whether or not the list has marketing permissions (eg. GDPR) enabled.")
    from_name = fields.Char("Default From Name", required=True)
    from_email = fields.Char("Default From Email Address", required=True)
    subject = fields.Char("Default Email Subject")
    lang_id = fields.Many2one('res.lang', string="Language")

    odoo_list_id = fields.Many2one('mailing.list', string='Odoo Mailing List', required=True,
                                   ondelete="cascade")
    contact_unsub_nbr = fields.Integer(compute="_compute_contact_unsub_nbr", string='Number of Unsubscribed Contacts')
    contact_cleaned_nbr = fields.Integer(compute="_compute_contact_cleaned_nbr", string='Number of Cleaned Contacts')
    contact_total_nbr = fields.Integer(compute="_compute_contact_total_nbr", string='Number of Total Contacts')
    statistics_ids = fields.One2many('mailchimp.lists.stats', 'list_id', string="Statistics",
                                     help="Stats for the list. Many of these are cached for at least five minutes.")
    stats_overview_ids = fields.One2many('mailchimp.lists.stats', 'list_id', string="Statistics",
                                         help="Stats for the list. Many of these are cached for at least five minutes.")
    stats_audience_perf_ids = fields.One2many('mailchimp.lists.stats', 'list_id', string="Statistics",
                                              help="Stats for the list. Many of these are cached for at least five minutes.")
    stats_campaign_perf_ids = fields.One2many('mailchimp.lists.stats', 'list_id', string="Statistics",
                                              help="Stats for the list. Many of these are cached for at least five minutes.")
    stats_since_last_campaign_ids = fields.One2many('mailchimp.lists.stats', 'list_id', string="Statistics",
                                                    help="Stats for the list. Many of these are cached for at least five minutes.")
    account_id = fields.Many2one("mailchimp.accounts", string="Account", required=True)
    last_create_update_date = fields.Datetime("Last Create Update")
    write_date = fields.Datetime('Update on', index=True, readonly=True)
    is_update_required = fields.Boolean("Update Required?", compute="_is_update_required")
    member_since_last_changed = fields.Datetime("Fetch Member Since Last Change", copy=False)
    segment_ids = fields.One2many("mailchimp.segments", 'list_id', string="Segments", copy=False)
    merge_field_ids = fields.One2many("mailchimp.merge.fields", 'list_id', string="Merge Fields", copy=False)
    auto_export_contact = fields.Boolean("Auto Export Contact?", copy=False)
    auto_export_filter = fields.Char('Apply Filter', help="This condition according to filter records", default='[["email","!=",False]]')

    def unlink(self):
        odoo_lists = self.mapped('odoo_list_id')
        super(MailChimpLists, self).unlink()
        return odoo_lists.unlink()

    def action_view_recipients(self):
        action = self.env.ref('mass_mailing.action_view_mass_mailing_contacts').read()[0]
        action['domain'] = [('list_ids', 'in', self.odoo_list_id.ids)]
        ctx = {'default_list_ids': [self.odoo_list_id.id]}
        if self.env.context.get('show_total', False):
            ctx.update({'search_default_filter_not_email_bl': 1})
            action['context'] = ctx
        if self.env.context.get('show_sub', False):
            ctx.update({'search_default_filter_valid_email_recipient': 1})
            action['context'] = ctx
        if self.env.context.get('show_unsub', False):
            ctx.update({'search_default_unsub_contact': 1})
            action['context'] = ctx
        if self.env.context.get('show_cleaned', False):
            ctx.update({'search_default_cleaned_contact': 1})
            action['context'] = ctx
        return action

    @api.model
    def _prepare_vals_for_update(self):
        self.ensure_one()
        # prepared_vals = {}
        # for field_name in self.fields_get_keys():
        #     if hasattr(self, field_name) and field_name not in NOT_REQUIRED_ON_UPDATE:
        #         prepared_vals.update({field_name: getattr(self, field_name)})
        prepared_vals = {
            'permission_reminder': self.permission_reminder,
            'use_archive_bar': self.use_archive_bar,
            'notify_on_subscribe': self.notify_on_subscribe or '',
            'notify_on_unsubscribe': self.notify_on_unsubscribe or '',
            'email_type_option': self.email_type_option,
            'visibility': self.visibility,
            'double_optin': self.double_optin,
            'has_welcome': self.has_welcome,
            'marketing_permissions': self.marketing_permissions,
            'name': self.name, }
        partner_id = self.partner_id
        prepared_vals['contact'] = {'company': partner_id.name or '', 'address1': partner_id.street or '',
                                    'address2': partner_id.street2 or '', 'city': partner_id.city or '',
                                    'state': partner_id.state_id and partner_id.state_id.name or '', 'zip': partner_id.zip or '',
                                    'country': partner_id.country_id and partner_id.country_id.code or '', 'phone': partner_id.phone or ''}
        prepared_vals['campaign_defaults'] = {'from_name': self.from_name, 'from_email': self.from_email,
                                              'subject': self.subject or '', 'language': self.lang_id.iso_code or ''}
        return prepared_vals

    def export_in_mailchimp(self):
        for list in self:
            prepared_vals = list._prepare_vals_for_update()
            response = list.account_id._send_request('lists', prepared_vals, method='POST')
            if response and response.get('id'):
                list.write({'list_id': response.get('id')})
                list.create_or_update_list(values_dict=response, account=list.account_id)
        return True

    def update_in_mailchimp(self):
        for list in self:
            prepared_vals = list._prepare_vals_for_update()
            response = list.account_id._send_request('lists/%s' % list.list_id, prepared_vals, method='PATCH')
            list.write({'last_create_update_date': fields.Datetime.now()})
        return True

    @api.model
    def _find_partner(self, location):
        partners = self.env['res.partner']
        state = self.env['res.country.state']
        domain = []
        if 'address1' in location and 'city' in location and 'company' in location:
            domain.append(('name', '=', location['company']))
            domain.append(('street', '=', location.get('address1') or False))
            domain.append(('city', '=', location.get('city') or False))
            if location.get('state'):
                domain.append(('state_id.name', '=', location.get('state') or False))
            if location.get('zip'):
                domain.append(('zip', '=', location.get('zip') or False))
            partners = partners.search(domain, limit=1)
        if not partners:
            country_id = self.env['res.country'].search([('code', '=', location['country'])], limit=1)
            if country_id and location['state']:
                state = self.env['res.country.state'].search(
                    ['|', ('name', '=', location['state']), ('code', '=', location['state']),
                     ('country_id', '=', country_id.id)], limit=1)
            elif location['state']:
                state = self.env['res.country.state'].search(
                    ['|', ('name', '=', location['state']), ('code', '=', location['state'])],
                    limit=1)
            vals = {'name': location.pop('company'), 'street': location.pop('address1'),
                    'street2': location.pop('address2'), 'state_id': state.id, 'country_id': country_id.id,'zip':location.get('zip')}
            partners = partners.create(vals)
        return partners

    def create_or_update_list(self, values_dict, account=False):
        list_id = values_dict.get('id')
        existing_list = self.search([('list_id', '=', list_id)])
        stats = values_dict.pop('stats', {})
        values_dict.update(values_dict.pop('campaign_defaults'))
        lang_id = self.env['res.lang'].search([('iso_code', '=', values_dict.pop('language', 'en'))])
        for item in unwanted_data:
            values_dict.pop(item)
        for old_key, new_key in replacement_of_key:
            values_dict[new_key] = values_dict.pop(old_key)
        for item in DATE_CONVERSION:
            if values_dict.get(item, False) == '':
                values_dict[item] = False
            if values_dict.get(item, False):
                values_dict[item] = account.covert_date(values_dict.get(item))
        values_dict.update({'account_id': account.id})
        partner = self._find_partner(values_dict.pop('contact'))
        values_dict.update(
            {'partner_id': partner.id, 'lang_id': lang_id.id, 'list_rating': str(values_dict.pop('list_rating', '0'))})
        if not existing_list:
            existing_list = self.create(values_dict)
        else:
            existing_list.write(values_dict)
        existing_list.create_or_update_statistics(stats)
        # existing_list.fetch_members()
        existing_list.fetch_segments()
        existing_list.fetch_merge_fields()
        existing_list.write({'last_create_update_date': fields.Datetime.now()})
        return True

    def import_lists(self, account=False):
        if not account:
            raise Warning("MailChimp Account not defined to import lists")
        response = account._send_request('lists', {}, method='GET', params={'count': 1000})
        for list in response.get('lists'):
            self.create_or_update_list(list, account=account)
        return True

    def refresh_list(self):
        if not self.account_id:
            raise Warning("MailChimp Account not defined to Refresh list")
        response = self.account_id._send_request('lists/%s' % self.list_id, {})
        self.create_or_update_list(response, account=self.account_id)
        return True

    def create_or_update_statistics(self, stats):
        self.ensure_one()
        self.statistics_ids.unlink()
        for item in DATE_CONVERSION:
            if stats.get(item, False):
                stats[item] = self.account_id.covert_date(stats.get(item))
            else:
                stats[item] = False
        stats.pop('date_created')
        self.write({'statistics_ids': [(0, 0, stats)]})
        return True

    def fetch_merge_fields(self):
        mailchimp_merge_field_obj = self.env['mailchimp.merge.fields']
        if not self.account_id:
            raise Warning("MailChimp Account not defined to Fetch Merge Field list")
        count = 1000
        offset = 0
        merge_field_list = []
        prepared_vals = {}
        while True:
            prepared_vals.update({'count': count, 'offset': offset,
                                  'fields': 'merge_fields.merge_id,merge_fields.tag,merge_fields.name,merge_fields.type,merge_fields.required,merge_fields.default_value,merge_fields.public,merge_fields.display_order,merge_fields.list_id,merge_fields.options'})
            response = self.account_id._send_request('lists/%s/merge-fields' % self.list_id, {}, params=prepared_vals)
            if len(response.get('merge_fields')) == 0:
                break
            if isinstance(response.get('merge_fields'), dict):
                merge_field_list = [response.get('merge_fields')]
            else:
                merge_field_list += response.get('merge_fields')
            offset = offset + 1000
        merge_field_to_remove_ids = self.merge_field_ids
        for merge_field in merge_field_list:
            if not merge_field.get('merge_id', False):
                continue
            # merge_field_id = mailchimp_merge_field_obj.search([('merge_id', '=', merge_field.get('merge_id')), ('list_id', '=', self.id)])
            merge_field_id = self.merge_field_ids.filtered(lambda x: x.merge_id == str(merge_field.get('merge_id')))
            merge_field.update({'list_id': self.id})
            options = merge_field.pop('options', {})
            if options.get('date_format'):
                date_format = options.get('date_format')
                date_format = date_format.replace("MM", '%m')
                date_format = date_format.replace("DD", '%d')
                date_format = date_format.replace("YYYY", '%Y')
                merge_field.update({'date_format': date_format})
            if not merge_field_id:
                mailchimp_merge_field_obj.create(merge_field)
            if merge_field_id:
                merge_field_id.write(merge_field)
            merge_field_to_remove_ids -= merge_field_id
        if merge_field_to_remove_ids:
            merge_field_to_remove_ids.unlink()
        return merge_field_list

    def fetch_segments(self):
        mailchimp_segments_obj = self.env['mailchimp.segments']
        if not self.account_id:
            raise Warning("MailChimp Account not defined to Fetch Segments list")
        count = 1000
        offset = 0
        segments_list = []
        prepared_vals = {}
        while True:
            prepared_vals.update({'count': count, 'offset': offset})
            response = self.account_id._send_request('lists/%s/segments' % self.list_id, {}, params=prepared_vals)
            if len(response.get('segments')) == 0:
                break
            if isinstance(response.get('segments'), dict):
                segments_list = [response.get('segments')]
            else:
                segments_list += response.get('segments')
            offset = offset + 1000
        for segment in segments_list:
            if not segment.get('id', False):
                continue
            segment_id = mailchimp_segments_obj.search([('mailchimp_id', '=', segment.get('id'))])
            name = segment.get('name')
            if segment.get('type') == 'static':
                name = "Tags : %s" % name
            vals = {'mailchimp_id': segment.get('id'), 'name': name, 'list_id': self.id}
            if not segment_id:
                mailchimp_segments_obj.create(vals)
            if segment_id:
                segment_id.write(vals)
        return segments_list

    def _prepare_vals_for_to_create_partner(self, merge_field_vals):
        prepared_vals = {}
        for custom_field in self.merge_field_ids:
            if custom_field.type == 'address':
                address_dict = merge_field_vals.get(custom_field.tag)
                if not address_dict:
                    continue
                state_id = False
                country = self.env['res.country'].search([('code', '=', address_dict.get('country', ''))], limit=1)
                if country:
                    state_id = self.env['res.country.state'].search(
                        ['|', ('name', '=', address_dict['state']),
                         ('code', '=', address_dict['state']),
                         ('country_id', '=', country.id)], limit=1)
                prepared_vals.update({
                    'street': address_dict.get('addr1', ''),
                    'street2': address_dict.get('addr2', ''),
                    'city': address_dict.get('city', ''),
                    'zip': address_dict.get('zip', ''),
                    'state_id': state_id.id if state_id else False,
                    'country_id': country.id,
                })
            elif custom_field.tag in ['FNAME', 'LNAME'] and not prepared_vals.get('name', False):
                prepared_vals.update({'name': "%s %s" % (merge_field_vals.get('FNAME'), merge_field_vals.get('LNAME'))})
            elif custom_field.field_id and custom_field.type in ['date', 'birthday']:
                value = merge_field_vals.get(custom_field.tag)
                if value and custom_field.field_id.ttype in ['date']:
                    if len(value.split('/')) > 1:
                        value = datetime.strptime(value, custom_field.date_format).strftime(DEFAULT_SERVER_DATE_FORMAT)
                prepared_vals.update({custom_field.field_id.name: value or False})
            elif custom_field.field_id:
                prepared_vals.update({custom_field.field_id.name: merge_field_vals.get(custom_field.tag)})
        return prepared_vals

    def process_member_from_stored_response(self, pending_record):
        member_data = safe_eval(pending_record.pending_res_data)
        mailing_contact_obj = self.env['mailing.contact']
        count = 0
        while member_data:
            for member in member_data[:100]:
                if not member.get('email_address', False):
                    continue
                update_partner_required = True
                mailchimp_id = str(member.get('web_id'))
                contact_id = mailing_contact_obj.search(['|', ('email', '=', member.get('email_address')), ('subscription_list_ids.mailchimp_id', '=', mailchimp_id)], limit=1)
                create_vals = member.get('merge_fields')
                prepared_vals_for_create_partner = self._prepare_vals_for_to_create_partner(create_vals)
                name = member.get('email_address')
                if create_vals.get('FNAME', False) or create_vals.get('LNAME', False):
                    name = "%s %s" % (create_vals.get('FNAME', False) and create_vals.pop('FNAME') or '', create_vals.get('LNAME', False) and create_vals.pop('LNAME') or '')
                tag_ids = self.env['res.partner.category']
                tag_list = member.get('tags')
                if tag_list:
                    tag_ids = self.env['res.partner.category'].create_or_update_tags(tag_list)
                prepared_vals_for_create_partner.update({'category_id': [(6, 0, tag_ids.ids)]})
                if not contact_id:
                    if not self.account_id.auto_create_member:
                        continue
                    self.update_partner_detail(name, member.get('email_address'), prepared_vals_for_create_partner)
                    update_partner_required = False
                    contact_id = mailing_contact_obj.create(
                        {'name': name, 'email': member.get('email_address'),
                         'country_id': prepared_vals_for_create_partner.get('country_id', False) or False})
                if contact_id:
                    md5_email = hashlib.md5(member.get('email_address').encode('utf-8')).hexdigest()
                    vals = {'list_id': self.odoo_list_id.id, 'contact_id': contact_id.id,
                            'mailchimp_id': member.get('web_id'), 'md5_email': md5_email}
                    status = member.get('status', '')
                    if update_partner_required:
                        self.update_partner_detail(name, member.get('email_address'), prepared_vals_for_create_partner, old_email=contact_id.email)
                    contact_vals = {'tag_ids': [(6, 0, tag_ids.ids)], 'email': member.get('email_address')}
                    if status == 'cleaned':
                        self.env['mail.blacklist'].sudo()._add(member.get('email_address'))
                        # contact_vals.update({'is_email_valid': False})
                    contact_id.write(contact_vals)
                    vals.update({'opt_out': True}) if status in ['unsubscribed', 'cleaned'] else vals.update({'opt_out': False})
                    existing_define_list = contact_id.subscription_list_ids.filtered(
                        lambda x: x.list_id.id == self.odoo_list_id.id)
                    if existing_define_list:
                        existing_define_list.write(vals)
                    else:
                        contact_id.subscription_list_ids.create(vals)
                # del member_data[i]
            del member_data[:100]
            count += 100
            pending_record.write({'pending_res_data': member_data})
            self._cr.commit()
            _logger.info("## MAILCHIMP IMPORT For %s : CURRENTLY PROCESSED RECORD COUNT : %s" % (pending_record.name, count))
        return True

    def fetch_members(self):
        mailchimp_queue_process_obj = self.env['mailchimp.queue.process']
        if not self.account_id:
            raise Warning("MailChimp Account not defined to Fetch Member list")
        if not self.merge_field_ids:
            return True
        # if member_import_log_obj.search([('operation', '=', 'contact'), ('list_id', '=', self.id)]):
        #     raise ValidationError(_("You can't trigger import since there is already pending record to process for this list! You can check it by navigating MailChimp >> Pending Import Log."))
        count = 1000
        offset = 0
        members_list = []
        members_list_to_create = []
        prepared_vals = {}
        if self.member_since_last_changed:
            member_since_last_changed = self.member_since_last_changed - timedelta(minutes=10)
            prepared_vals.update({'since_last_changed': member_since_last_changed.strftime("%Y-%m-%dT%H:%M:%S+00:00")})
        while True:
            prepared_vals.update({'count': count, 'offset': offset, 'fields': 'members.email_address,members.merge_fields,members.tags,members.web_id,members.status'})
            response = self.account_id._send_request('lists/%s/members' % self.list_id, {}, params=prepared_vals)
            if len(response.get('members')) == 0:
                break
            if isinstance(response.get('members'), dict):
                members_data = [response.get('members')]
            else:
                members_data = response.get('members')
            offset = offset + 1000
            storage_vals = {'response_data': members_data,
                            'account_id': self.account_id.id,
                            'list_id': self.id,
                            'operation': 'contact',
                            'state': 'fetched',
                            'req_data': {},
                            'req_url': 'lists/{}/members'.format(self.list_id),
                            'req_param': prepared_vals
                            }
            job_queue = mailchimp_queue_process_obj.create(storage_vals)
            _logger.info("{job} : Job Queue Created to Fetch MailChimp Audience for '{list}'".format(job=job_queue.name, list=self.name))
            self._cr.commit()
        self.write({'member_since_last_changed': fields.Datetime.now()})
        return members_list

    def update_partner_detail(self, name, email, partner_detail, old_email=False):
        query = """
                SELECT id 
                  FROM res_partner
                WHERE LOWER(substring(email, '([^ ,;<@]+@[^> ,;]+)')) = LOWER(substring('{}', '([^ ,;<@]+@[^> ,;]+)')) order by id desc limit 1""".format(email.replace("'", "''"))
        self._cr.execute(query)
        partner_id = self._cr.fetchone()
        partner_id = partner_id[0] if partner_id else False
        if not partner_id and old_email:
            query = """
                    SELECT id 
                      FROM res_partner
                    WHERE LOWER(substring(email, '([^ ,;<@]+@[^> ,;]+)')) = LOWER(substring('{}', '([^ ,;<@]+@[^> ,;]+)')) order by id desc limit 1""".format(
                old_email.replace("'", "''"))
            self._cr.execute(query)
            partner_id = self._cr.fetchone()
            partner_id = partner_id[0] if partner_id else False
        if partner_id:
            partner_id = self.env['res.partner'].browse(partner_id)
            if partner_detail:
                partner_detail.update({'name': name, 'email': email})
                partner_id.with_context(no_need=True).write(partner_detail)
        else:
            if self.account_id.auto_create_member and self.account_id.auto_create_partner:
                partner_detail.update({
                    'name': name,
                    'email': email,
                    'is_company': False,
                    'type': 'contact',
                })
                self.env['res.partner'].create(partner_detail)
        return True

    def get_mapped_merge_field(self):
        merge_fields = []
        for record in self:
            if record.merge_field_ids:
                merge_fields.extend(record.merge_field_ids.mapped('field_id').mapped('name'))
        merge_fields.extend(['name', 'email', 'street', 'street2', 'city', 'state_id', 'zip', 'country_id'])
        return merge_fields

    @api.model
    def fetch_member_cron(self):
        account_obj = self.env['mailchimp.accounts']
        for record in account_obj.search([('auto_refresh_member', '=', True)]):
            list_ids = self.search([('account_id', '=', record.id)])
            for list in list_ids:
                list.fetch_members()
        return True

    def _get_remaining_partner_to_export(self):
        self.ensure_one()
        if not self.auto_export_filter:
            return []
        prepare_domain = safe_eval(self.auto_export_filter)
        models_records = self.env['res.partner'].search_read(prepare_domain, ['id'])
        models_records = [x['id'] for x in models_records]
        if models_records:
            query = """select rp.id as par_id from res_partner as rp left join mailing_contact cl on rp.email = cl.email left join mailing_contact_list_rel clrel on clrel.contact_id = cl.id where mailchimp_list_id is distinct from {} and rp.id in %s""".format(self.id)
            self._cr.execute(query, (tuple(models_records),))
            res = self._cr.dictfetchall()
            return self.env['res.partner'].browse(res['par_id'] for res in res)
        return self.env['res.partner']

    @api.model
    def auto_export_member_to_list(self):
        for record in self:
            if record.auto_export_filter:
                remaining_to_export = record._get_remaining_partner_to_export()
                remaining_to_export.with_context(from_cron=True).action_export_partner_mailchimp(record)
        return True

    def get_auto_export_member_action(self):
        action = self.env.ref('base.ir_cron_act').read()[0]
        cron = self.env.ref('mailchimp.auto_export_member_to_list')
        if cron:
            action['views'] = [(False, 'form')]
            action['res_id'] = cron.id
        else:
            raise ValidationError(_("Scheduled action isn't found! Please upgrade app to get it back!"))
        return action


class MailChimpListsStats(models.Model):
    _name = "mailchimp.lists.stats"
    _description = "MailChimp Statistics"

    list_id = fields.Many2one("mailchimp.lists", string="MailChimp List", required=True, ondelete='cascade')
    member_count = fields.Integer("Subscribed Count")
    unsubscribe_count = fields.Integer("Unsubscribe Count")
    cleaned_count = fields.Integer("Cleaned Count")
    member_count_since_send = fields.Integer("Subscribed Count")
    unsubscribe_count_since_send = fields.Integer("Unsubscribe Count")
    cleaned_count_since_send = fields.Integer("Cleaned Count")
    campaign_count = fields.Integer("Campaign Count")
    campaign_last_sent = fields.Datetime("Campaign Last Sent")
    merge_field_count = fields.Integer("Merge Count")
    avg_sub_rate = fields.Float("Average Subscription Rate")
    avg_unsub_rate = fields.Float("Average Unsubscription Rate")
    target_sub_rate = fields.Float("Average Subscription Rate")
    open_rate = fields.Float("Open Rate")
    click_rate = fields.Float("Click Rate")
    last_sub_date = fields.Datetime("Date of Last Subscribe")
    last_unsub_date = fields.Datetime("Date of Last Unsubscribe")
