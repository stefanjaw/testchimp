import logging
from datetime import datetime, timedelta
from odoo.tools.safe_eval import safe_eval
from odoo import api, fields, models, tools, _
from odoo.exceptions import Warning, ValidationError
from dateutil.relativedelta import relativedelta
import ast

from email.utils import formataddr, parseaddr
_logger = logging.getLogger(__name__)

REPLACEMENT_OF_KEY = [('id', 'mailchimp_id'), ('create_time', 'create_date'), ('send_time', 'sent_date'),
                      ('type', 'mailchimp_champ_type')]
DATE_CONVERSION = ['create_date', 'sent_date']
UNWANTED_DATA = ['_links', 'created_by', 'edited_by', 'thumbnail']


class MassMailing(models.Model):
    _inherit = "mailing.mailing"

    def _compute_pending_queue_count(self):
        queue_obj = self.env['mailchimp.queue.process']
        for record in self:
            record.pending_queue_count = queue_obj.search_count([('campaign_id', '=', record.id), ('state', 'in', ['in_queue', 'fetched'])])

    create_date = fields.Datetime("Created on", readonly=True, index=True)
    mailchimp_template_id = fields.Many2one('mailchimp.templates', "MailChimp Template", copy=False)
    mailchimp_account_id = fields.Many2one('mailchimp.accounts', string="MailChimp Account",
                                           related="mailchimp_template_id.account_id", store=True)
    mailchimp_list_id = fields.Many2one("mailchimp.lists", string="MailChimp List")
    mailchimp_id = fields.Char("MailChimp ID", copy=False)
    mailchimp_segment_id = fields.Many2one('mailchimp.segments', string="MailChimp Segments", copy=False)
    mailchimp_champ_type = fields.Selection(
        [('regular', 'Regular'), ('plaintext', 'Plain Text'), ('absplit', 'AB Split'), ('rss', 'RSS'),
         ('variate', 'Variate'),('automation-email','Automated'),('tx','TX')],
        default='regular', string="Type")
    last_report_import_date = fields.Datetime("Report Imported On", copy=False)
    pending_queue_count = fields.Integer(compute="_compute_pending_queue_count")
    mailchimp_body_html = fields.Html(string='Mailchimp Body', sanitize_attributes=False, related='mailchimp_template_id.body_html', store=True)
    body_arch = fields.Html(string='Body', translate=False, related='mailchimp_template_id.body_arch',store=True)

    def action_view_clicked(self):
        model_name = self.env['ir.model']._get('link.tracker').display_name
        return {
            'name': model_name,
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'view_id': self.env.ref('mailchimp.mailchimp_link_tracker_view_tree').id,
            'res_model': 'link.tracker',
            'domain': [('mass_mailing_id.id', '=', self.id)],
            'context': dict(self._context, create=False)
        }

    def process_clicked_link(self, pending_record):
        link_tracker_obj = self.env['link.tracker']
        link_data = safe_eval(pending_record.pending_res_data)
        account = self.mailchimp_template_id.account_id
        for link in link_data:
            exist = link_tracker_obj.search([('mailchimp_id','=',link.get('id'))])
            if not exist:
                exist = link_tracker_obj.search([('campaign_id', '=', self.campaign_id.id),('medium_id','=',self.medium_id.id),('source_id','=',self.source_id.id),('url','=',link.get('url', ''))])
            campaign_id = self.env['mailing.mailing'].search([('mailchimp_id', '=', link.get('campaign_id',''))])
            if exist:
                exist.write({
                    'url' : link.get('url',''),
                    'mass_mailing_id' : self.id,
                    'medium_id' : self.medium_id and self.medium_id.id,
                    'source_id' : self.source_id and self.source_id.id or False,
                    'campaign_id' : self.campaign_id and self.campaign_id.id or False,
                    'mailchimp_link_clicks' : link.get('total_clicks',0)
                })
            else:
                link_tracker_obj.create({
                    'mailchimp_id': link.get('id'),
                    'url': link.get('url', ''),
                    'mass_mailing_id': self.id,
                    'medium_id': self.medium_id and self.medium_id.id,
                    'source_id': self.source_id and self.source_id.id or False,
                    'campaign_id': self.campaign_id and self.campaign_id.id or False,
                    'mailchimp_link_clicks': link.get('total_clicks', 0)
                })
        return True


    def process_click_activity_report(self, account):
        self.ensure_one()
        mailchimp_queue_process_obj = self.env['mailchimp.queue.process']
        count = 1000
        offset = 0
        prepared_vals = {'fields': 'total_items'}
        response = account._send_request('reports/%s/click-details' % self.mailchimp_id, {}, params=prepared_vals)
        total_items = response.get('total_items')
        while offset <= total_items:
            prepared_vals = {'count': count, 'offset': offset}
            mailchimp_queue_process_obj.create({
                'account_id': account.id,
                'campaign_id': self.id,
                'operation': 'click_activity',
                'state': 'in_queue',
                'req_data': {},
                'req_url': 'reports/%s/click-details' % self.mailchimp_id,
                'req_param': prepared_vals
            })
            offset = offset + 1000
        return True

    def process_email_activity_report(self):
        self.ensure_one()
        mailchimp_queue_process_obj = self.env['mailchimp.queue.process']
        account = self.mailchimp_template_id.account_id
        count = 1000
        offset = 0
        prepared_vals = {'fields': 'total_items'}
        #-----------------------------------------------
        #TODO #Need to improve while passing date.  Becuase issues while creating statistics whith half data.
        # -----------------------------------------------
        # if self.last_report_import_date:
        #     # Todo #Need to check datetime come with conveted in from string or not
        #     since_last_changed = fields.Datetime.from_string(self.last_report_import_date) - timedelta(minutes=10)
        #     prepared_vals.update({'since': since_last_changed.strftime("%Y-%m-%dT%H:%M:%S+00:00")})
        response = account._send_request('reports/%s/email-activity' % self.mailchimp_id, {}, params=prepared_vals)
        total_items = response.get('total_items')
        while offset <= total_items:
            prepared_vals.update({'count': count, 'offset': offset, 'fields': 'emails.email_address,emails.activity'})
            mailchimp_queue_process_obj.create({
                'account_id': account.id,
                'campaign_id': self.id,
                'operation': 'campaign_activity_report',
                'state': 'in_queue',
                'req_data': {},
                'req_url': 'reports/%s/email-activity' % self.mailchimp_id,
                'req_param': prepared_vals
            })
            offset = offset + 1000
        self.process_click_activity_report(account)
        self.write({'last_report_import_date': fields.Datetime.now()})
        self._cr.commit()
        return True

    def _select_clause(self):
        select_str = """
            SELECT tmp.email_address AS email,
                   'mail.mass_mailing.contact' AS model,
                   'mail' as trace_type,
                   mc.id AS res_id,
                   mm.sent_date AS sent,
                   tmp.opened AS opened,
                   tmp.clicked AS clicked,
                   tmp.status AS state,
                   mm.id AS mass_mailing_id
        """
        return select_str

    def _from_clause(self):
        from_str = """
            FROM tmp_activity_report tmp
                JOIN mailing_contact mc ON mc.email = tmp.email_address
                JOIN mailing_contact_list_rel mcrel ON mcrel.contact_id = mc.id
                    JOIN mail_mass_mailing_list_rel mmlr ON mmlr.mailing_mailing_id = tmp.mass_mailing_id
                JOIN mailing_mailing mm ON mm.id = tmp.mass_mailing_id
        """
        return from_str

    def _create_or_update_campaign_statsticts(self):
        #bounced = mc_report.bounced,
        self._cr.execute("""
                    UPDATE mailing_trace SET email = mc_report.email,
                        model = mc_report.model,
                        trace_type = mc_report.trace_type,
                        res_id = mc_report.res_id,
                        sent_datetime = mc_report.sent,
                        open_datetime = mc_report.opened,
                        links_click_datetime = mc_report.clicked,
                        trace_status = mc_report.state,
                        mass_mailing_id = mc_report.mass_mailing_id
                    FROM ( 
                        %s 
                        %s 
                        full outer JOIN mailing_trace mt on mt.res_id = mc.id and mt.mass_mailing_id=%d
                        WHERE mcrel.list_id = mmlr.mailing_list_id and mt.res_id is not null
                    ) AS mc_report                
                    WHERE mailing_trace.email = mc_report.email
                    AND mailing_trace.mass_mailing_id = %d""" % (self._select_clause(), self._from_clause(), self.id, self.id))
        self._cr.execute("""
            INSERT INTO mailing_trace (email, model, trace_type, res_id, sent_datetime, open_datetime, links_click_datetime, trace_status, mass_mailing_id)
                %s
                %s
                full outer JOIN mailing_trace mt on mt.res_id = mc.id and mt.mass_mailing_id=%d
                WHERE mcrel.list_id = mmlr.mailing_list_id and mt.res_id is null
            """ % (self._select_clause(), self._from_clause(), self.id))
        return True

    def process_report_from_stored_response(self, pending_records):
        for record in self:
            email_lists = []
            queues = pending_records.filtered(lambda x : x.campaign_id.id==record.id)
            for queue in queues:
                record = queue.campaign_id
                email_list = safe_eval(queue.pending_res_data)
                account = record.mailchimp_template_id.account_id
                for email in email_list:
                    activities = email.pop('activity')
                    open = None
                    click = None
                    bounce = None
                    for activity in activities:
                        action = activity.get('action')
                        if action == 'open':
                            open = account.covert_date(activity.get('timestamp'))
                        elif action == 'click':
                            click = account.covert_date(activity.get('timestamp'))
                        elif action == 'bounce':
                            bounce = account.covert_date(activity.get('timestamp'))
                    state = 'sent'
                    if open or click:
                        state = 'open'
                    elif bounce or state in ['hard', 'soft']:
                        state = 'bounce'
                    email.update({'status': state, 'opened': open, 'clicked': click, 'bounced': bounce})
                email_lists += email_list
            if email_lists:
                self._cr.execute("DROP TABLE IF EXISTS tmp_activity_report")
                self._cr.execute(
                    'CREATE TEMP TABLE tmp_activity_report (email_address character varying, status character varying, mass_mailing_id integer, opened timestamp without time zone, clicked timestamp without time zone, bounced timestamp without time zone)')
                cols = list(email_lists[0])
                insert_query = "INSERT INTO {table} ({cols}) VALUES {rows}".format(table='tmp_activity_report',
                                                                                   cols=",".join(cols), rows=",".join(
                        "%s" for row in email_lists))
                params = [tuple(row[col] for col in cols) for row in email_lists]
                self._cr.execute(insert_query, params)
                update_query = "UPDATE {table} SET mass_mailing_id = {value}".format(table='tmp_activity_report',
                                                                                     value=record.id)
                self._cr.execute(update_query)
                self._cr.commit()
            record._create_or_update_campaign_statsticts()
            _logger.info("## MAILCHIMP CAMPAIGN ACTIVITY REPORT Processed For %s " % (record.name))
        return True

    @api.model
    def fetch_email_activity(self):
        for record in self.search([('state', 'not in', ['draft', 'in_queue']), ('mailchimp_id', '!=', False)]):
            account_id = record.mailchimp_template_id and record.mailchimp_template_id.account_id or False
            interval_no = account_id and account_id.camp_rep_interval or 5
            interval_dur = account_id and account_id.camp_rep_interval_type or 'days'
            interval_date = relativedelta(**{interval_dur: interval_no})
            pre_date = datetime.now() - interval_date
            if record.sent_date >= pre_date:
                record.fetch_campaign()
                record.process_email_activity_report()
        return True

    def create_or_update_campaigns(self, values_dict, account=False):
        fetch_needed = False
        list_obj = self.env['mailchimp.lists']
        template_obj = self.env['mailchimp.templates']
        mailchimp_id = values_dict.get('id')
        settings_dict = values_dict.get('settings')
        recipients_dict = values_dict.get('recipients')
        list_id = recipients_dict.get('list_id')
        template_id = settings_dict.get('template_id')
        if list_id:
            list_obj = list_obj.search([('list_id', '=', list_id)]).odoo_list_id
        if template_id:
            template_obj = template_obj.search([('template_id', '=', template_id), ('account_id', '=', account.id)])
        status = values_dict.get('status')
        subject_line = settings_dict.get('subject_line') or settings_dict.get('title') or ' '
        try:
            email_from = formataddr((settings_dict.get('from_name'), settings_dict.get('reply_to')))
        except Exception as e:
            author_id, email_from = self.env['mail.thread']._message_compute_author(None,settings_dict.get('from_name'),raise_exception=False)
            email_from = email_from
        prepared_vals = {
            'create_date': values_dict.get('create_time'),
            'sent_date': values_dict.get('send_time'),
            'subject': subject_line,
            'mailchimp_id': mailchimp_id,
            'mailing_model_id': self.env.ref('mass_mailing.model_mailing_list').id,
            'contact_list_ids': [(6, 0, list_obj.ids)],
            'mailchimp_template_id': template_obj.id,
            'mailchimp_champ_type': values_dict.get('type'),
            'email_from': email_from,
            'reply_to': email_from,
        }
        if status in ['save', 'paused']:
            prepared_vals.update({'state': 'draft'})
        elif status == 'schedule':
            prepared_vals.update({'state': 'in_queue'})
        elif status == 'sending':
            prepared_vals.update({'state': 'sending'})
        elif status == 'sent':
            fetch_needed = True
            prepared_vals.update({'state': 'done'})
        for item in DATE_CONVERSION:
            if prepared_vals.get(item, False) == '':
                prepared_vals[item] = False
            if prepared_vals.get(item, False):
                prepared_vals[item] = account.covert_date(prepared_vals.get(item))
        existing_list = self.search([('mailchimp_id', '=', mailchimp_id)])
        if not existing_list:
            existing_list = self.create(prepared_vals)
            self.env.cr.execute("""
                           UPDATE
                           mailing_mailing
                           SET create_date = '%s'
                           WHERE id = %s
                           """ % (prepared_vals.get('create_date'), existing_list.id))
        else:
            existing_list.write(prepared_vals)
        existing_list._onchange_model_and_list()
        existing_list.body_html = False
        # if fetch_needed:
        #     existing_list.process_email_activity_report()
        return True

    def fetch_campaign(self):
        self.ensure_one()
        if not self.mailchimp_id:
            return True
        account = self.mailchimp_template_id.account_id
        params_vals = {
            'fields': 'id,type,status,create_time,send_time,settings.template_id,settings.subject_line,settings.title,settings.from_name,settings.reply_to,recipients.list_id'}
        response = account._send_request('campaigns/%s' % self.mailchimp_id, {}, params=params_vals)
        self.create_or_update_campaigns(response, account=account)
        return True

    def import_campaigns(self, account=False):
        if not account:
            raise Warning("MailChimp Account not defined to import Campaigns")
        count = 1000
        offset = 0
        campaigns_list = []
        while True:
            prepared_vals = {'count': count, 'offset': offset}
            since_date = self._context.get('camp_since_last_changed') or account.camp_since_last_changed
            if since_date:
                member_since_last_changed = since_date - timedelta(minutes=10)
                prepared_vals.update({'since_create_time': member_since_last_changed.strftime("%Y-%m-%dT%H:%M:%S+00:00")})
            response = account._send_request('campaigns', {}, params=prepared_vals)
            if len(response.get('campaigns')) == 0:
                break
            if isinstance(response.get('campaigns'), dict):
                campaigns_list += [response.get('campaigns')]
            campaigns_list += response.get('campaigns')
            offset = offset + 1000
        for campaigns_dict in campaigns_list:
            self.create_or_update_campaigns(campaigns_dict, account=account)
        account.camp_since_last_changed = fields.Datetime.now()
        return True

    @api.model
    def _prepare_vals_for_export(self):
        self.ensure_one()
        self.mailchimp_template_id.export_update_templates_mailchimp()
        from_name, from_email = parseaddr(self.email_from)
        reply_to_name, reply_to_email = parseaddr(self.reply_to)
        settings_dict = {'subject_line': self.subject, 'title': self.subject, 'from_name': from_name,
                         'reply_to': reply_to_email, 'template_id': int(self.mailchimp_template_id.template_id)}
        prepared_vals = {'type': 'regular',
                         'recipients': {'list_id': self.contact_list_ids.mailchimp_list_id.list_id, },
                         'settings': settings_dict}
        if self.mailchimp_segment_id.mailchimp_id:
            prepared_vals['recipients'].update({'segment_opts': {'saved_segment_id': int(self.mailchimp_segment_id.mailchimp_id)}})
        return prepared_vals

    def export_to_mailchimp(self, account=False):
        if self.mailchimp_id:
            return True
        if not account:
            raise Warning("MailChimp Account not defined in selected Template.")
        prepared_vals = self._prepare_vals_for_export()
        response = account._send_request('campaigns', prepared_vals, method='POST')
        if response.get('id', False):
            self.write({'mailchimp_id': response['id']})
        else:
            ValidationError(_("MailChimp Identification wasn't received. Please try again!"))
        self._cr.commit()
        return True

    def send_now_mailchimp(self, account=False):
        if not account:
            raise Warning("MailChimp Account not defined in selected Template.")
        response = account._send_request('campaigns/%s/actions/send' % self.mailchimp_id, {}, method='POST')
        return True

    def send_test_mail_mailchimp(self, test_emails):
        self.ensure_one()
        self.export_to_mailchimp(self.mailchimp_template_id.account_id)
        prepared_vals = {'test_emails': test_emails, 'send_type': 'html'}
        response = self.mailchimp_template_id.account_id._send_request('campaigns/%s/actions/test' % self.mailchimp_id,
                                                                       prepared_vals, method='POST')
        return True

    def schedule_mailchimp_champaign(self, schedule_date):
        self.ensure_one()
        self.export_to_mailchimp(self.mailchimp_template_id.account_id)
        prepared_vals = {'schedule_time': schedule_date.isoformat()}
        response = self.mailchimp_template_id.account_id._send_request(
            'campaigns/%s/actions/schedule' % self.mailchimp_id,
            prepared_vals, method='POST')
        return True

    def cancel_mass_mailing(self):
        res = super(MassMailing, self).cancel_mass_mailing()
        if self.mailchimp_id and self.mailchimp_template_id:
            self.mailchimp_template_id.account_id._send_request('campaigns/%s/actions/cancel-send' % self.mailchimp_id,
                                                                {}, method='POST')
            if self.schedule_date:
                self.mailchimp_template_id.account_id._send_request(
                    'campaigns/%s/actions/unschedule' % self.mailchimp_id,
                    {}, method='POST')
        return res

    def action_put_in_queue(self):
        res = super(MassMailing, self).action_put_in_queue()
        for record in self.filtered(lambda x: x.mailchimp_template_id):
            if len(record.contact_list_ids) > 1:
                raise ValidationError(_("Multiple list is not allowed while going with MailChimp!"))
            if record.contact_list_ids.filtered(lambda x: not x.mailchimp_list_id):
                raise ValidationError(_("Please provide MailChimp list as you selected MailChimp Template!"))
            record.export_to_mailchimp(record.mailchimp_template_id.account_id)
            if record.mailchimp_id:
                record.send_now_mailchimp(record.mailchimp_template_id.account_id)
                record.fetch_campaign()
                record.process_email_activity_report()
        return res

    @api.model
    def _process_mass_mailing_queue(self):
        mass_mailings = self.search(
            [('state', 'in', ('in_queue', 'sending')), '|', ('schedule_date', '<', fields.Datetime.now()),
             ('schedule_date', '=', False)])
        for mass_mailing in mass_mailings:
            user = mass_mailing.write_uid or self.env.user
            mass_mailing = mass_mailing.with_context(**user.with_user(user).context_get())
            if mass_mailing.mailchimp_id:
                mass_mailing.fetch_campaign()
                continue
            if len(mass_mailing.get_remaining_recipients()) > 0:
                mass_mailing.state = 'sending'
                mass_mailing.send_mail()
            else:
                mass_mailing.write({'state': 'done', 'sent_date': fields.Datetime.now()})


    @api.onchange('contact_list_ids')
    def _onchange_model_and_list(self):
        # res = self._onchange_contact_list_ids()
        mailing_domain = []
        list_obj = self.env['mailchimp.lists']
        list_ids = list_obj.search([('odoo_list_id', 'in', self.contact_list_ids.ids)])

        self.mailchimp_list_id = list_ids and list_ids[0] or False
        if self.mailchimp_list_id:
            self.email_from = formataddr((self.mailchimp_list_id.from_name, self.mailchimp_list_id.from_email))
            self.reply_to = formataddr((self.mailchimp_list_id.from_name, self.mailchimp_list_id.from_email))
        self.mailchimp_segment_id = False
        # return res
