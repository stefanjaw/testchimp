from odoo import fields, api, models, _
from odoo.tools.safe_eval import safe_eval


class MailchimpQueueProcess(models.Model):
    _name = "mailchimp.queue.process"
    _description = 'Mailchimp Queue Process'
    _order = 'id desc'

    _get_queue_state = [('in_queue', 'In Queue'), ('fetched', 'Fetched'), ('exception', 'Exception'), ('done', 'Done')]

    name = fields.Char('Name', required=1, default=lambda self: _('New'))
    create_date = fields.Datetime("Create Date")
    account_id = fields.Many2one("mailchimp.accounts", string="Account", required=True, ondelete='cascade')
    operation = fields.Selection([('contact', 'Mailing Contact'),
                                  ('Campaign', 'Campaign'),
                                  ('campaign_sent_to_report', 'Campaign Sent To Report'),
                                  ('campaign_activity_report', 'Campaign Activity Report'),
                                  ('click_activity','Click Activity')], string="Operation")
    list_id = fields.Many2one("mailchimp.lists", string="List", ondelete='cascade', copy=False)
    campaign_id = fields.Many2one("mailing.mailing", string="Campaign", ondelete='cascade', copy=False)

    req_url = fields.Char('URL', copy=False)
    req_data = fields.Char('Request Data', default='{}', copy=False)
    req_param = fields.Char('Request Params', default='{}', copy=False)
    total_items = fields.Integer('Total Items', copy=False, help='Count of total items on the current campaign')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user, copy=False)
    state = fields.Selection(_get_queue_state, default='in_queue', string='State', readonly=True)
    exception_message = fields.Text("Exception Message", copy=False, readonly=True)
    response_data = fields.Text('Response Data', copy=False, readonly=True)
    pending_res_data = fields.Text('Pending Response Data', copy=False, readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            if 'company_id' in vals:
                vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                    'mailchimp.queue.process') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('mailchimp.queue.process') or _('New')
        if vals.get('response_data'):
            vals.update({'pending_res_data': vals.get('response_data')})
        return super(MailchimpQueueProcess, self).create(vals)

    def process_fetched_response(self, response):
        self.ensure_one()
        data_list = []
        if self.operation == 'campaign_activity_report':
            if isinstance(response.get('emails'), dict):
                data_list += [response.get('emails')]
            data_list += response.get('emails')
        if self.operation == 'click_activity':
            if isinstance(response.get('urls_clicked'), dict):
                data_list += [response.get('urls_clicked')]
            data_list += response.get('urls_clicked')
        self.write({'response_data': data_list, 'pending_res_data' : data_list})
        return True

    def do_fetch(self):
        self.ensure_one()
        if self.state != 'in_queue':
            return False
        response = self.account_id._send_request(self.req_url, safe_eval(self.req_data), params=safe_eval(self.req_param))
        self.process_fetched_response(response)
        self.write({'state': 'fetched'})
        self._cr.commit()
        return True

    def process_queue_response_data(self):
        mailing_obj = self.env['mailing.mailing']
        campaign_ids = set([])
        queue_ids = self.env['mailchimp.queue.process']
        for pending_record in self.search([('state', 'in', ['in_queue', 'fetched']), ('account_id', '!=', False),('operation','!=','campaign_activity_report')],order='id'):
            if pending_record.state == 'in_queue':
                pending_record.do_fetch()
            if pending_record.pending_res_data:
                if pending_record.operation == 'contact' and pending_record.list_id:
                    pending_record.list_id.process_member_from_stored_response(pending_record)
                if pending_record.operation == 'click_activity' and pending_record.campaign_id:
                    pending_record.campaign_id.process_clicked_link(pending_record)
            pending_record.write({'state': 'done'})
        for ac_report in self.search([('state', 'in', ['in_queue', 'fetched']), ('account_id', '!=', False),('operation', '=', 'campaign_activity_report')], order='id'):
            if ac_report.state == 'in_queue':
                ac_report.do_fetch()
            campaign_ids.add(ac_report.campaign_id.id)
            queue_ids += ac_report
        campaign_ids = campaign_ids and mailing_obj.browse(list(campaign_ids)) or mailing_obj
        campaign_ids.process_report_from_stored_response(queue_ids)
        queue_ids.write({'state': 'done'})
        return True
