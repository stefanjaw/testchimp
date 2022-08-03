# -*- coding: utf-8 -*-
import random
import json
import time
import requests
from email.utils import formataddr
from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError, Warning, UserError

def random_auth_token():
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.SystemRandom().choice(chars) for _ in range(20))

class MailChimpAccounts(models.Model):
    _name = "mailchimp.accounts"
    _description = "Mailchimp Accounts"

    name = fields.Char("Name", required=True, copy=False, help="Name of your MailChimp account")

    # Authentication
    api_key = fields.Char('API Key', required=True, copy=False)
    auto_refresh_member = fields.Boolean("Auto Sync Member?", copy=False, default=True)
    auto_create_member = fields.Boolean("Auto Create Member?", copy=False, default=True)
    auto_create_partner = fields.Boolean("Auto Create Customer?", copy=False, default=False)
    list_ids = fields.One2many('mailchimp.lists', 'account_id', string="Lists/Audience", copy=False)
    campaign_ids = fields.One2many('mailing.mailing', 'mailchimp_account_id', string="Campaigns", copy=False)
    camp_rep_interval = fields.Integer(default=5, help="To use fetch campaign report until x.")
    camp_rep_interval_type = fields.Selection([('hours', 'Hours'),
                                               ('days', 'Days'),
                                               ('weeks', 'Weeks'),
                                               ('months', 'Months')], string='Interval Unit', default='days')
    webhook_url = fields.Char('Webhook URL')
    webhook_token = fields.Char('Webhook Token',copy=False)
    auto_update_contact = fields.Boolean(string="Auto Update Contact in MailChimp?", copy=False, default=True)
    camp_since_last_changed = fields.Datetime("Fetch Campaigns Since Last Change", copy=False,help='This date automatically come from a selected MailChimp account if you want you can change it to get campaigns according to this date')

    _sql_constraints = [
        ('api_keys_uniq', 'unique(api_key)', 'API keys must be unique per MailChimp Account!'),
    ]

    @api.model
    def _send_request(self, request_url, request_data, params=False, method='GET'):
        if not self.api_key:
            raise ValidationError(_("MailChimp API key is not found!"))
        if '-' not in self.api_key:
            raise ValidationError(_("MailChimp API key is invalid!"))
        if len(self.api_key.split('-')) > 2:
            raise ValidationError(_("MailChimp API key is invalid!"))

        api_key, dc = self.api_key.split('-')
        headers = {
            'Content-Type': 'application/json'
        }
        data = json.dumps(request_data)
        api_url = "https://{dc}.api.mailchimp.com/3.0/{url}".format(dc=dc, url=request_url)
        try:
            req = requests.request(method, api_url, auth=('apikey', api_key), headers=headers, params=params, data=data)
            req.raise_for_status()
            response_text = req.text
        except requests.HTTPError as e:
            raise Warning("%s" % req.text)
        response = json.loads(response_text) if response_text else {}
        return response

    def generate_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            token = random_auth_token()
            rec.webhook_url = base_url+'/mailchimp/webhook/notification/'
            rec.webhook_token = token

    def get_refresh_member_action(self):
        action = self.env.ref('base.ir_cron_act').read()[0]
        refresh_member_cron = self.env.ref('mailchimp.fetch_member')
        if refresh_member_cron:
            action['views'] = [(False, 'form')]
            action['res_id'] = refresh_member_cron.id
        else:
            raise ValidationError(_("Scheduled action isn't found! Please upgrade app to get it back!"))
        return action

    def covert_date(self, value):
        before_date = value[:19]
        coverted_date = time.strptime(before_date, "%Y-%m-%dT%H:%M:%S")
        final_date = time.strftime("%Y-%m-%d %H:%M:%S", coverted_date)
        return final_date


    def import_lists(self):
        mailchimp_lists = self.env['mailchimp.lists']
        for account in self:
            mailchimp_lists.import_lists(account)
        return True


    def import_templates(self):
        mailchimp_templates = self.env['mailchimp.templates']
        for account in self:
            mailchimp_templates.import_templates(account)
        return True


    def import_campaigns(self):
        mass_mailing_obj = self.env['mailing.mailing']
        for account in self:
            mass_mailing_obj.import_campaigns(account)
        return True


    def test_connection(self):
        response = self._send_request('lists', {})
        if response:
            raise UserError(_("Test Connection Succeeded"))
        return True
