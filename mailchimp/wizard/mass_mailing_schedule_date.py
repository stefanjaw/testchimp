# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MassMailingScheduleDate(models.TransientModel):
    _inherit = 'mailing.mailing.schedule.date'

    def set_schedule_date(self):
        self.ensure_one()
        mailing = self.mass_mailing_id
        if mailing.mailchimp_template_id:
            mailing.schedule_mailchimp_champaign(self.schedule_date)
        self.mass_mailing_id.write({'schedule_date': self.schedule_date, 'state': 'in_queue'})
