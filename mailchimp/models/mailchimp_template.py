from odoo import api, fields, models, _
from datetime import datetime

REPLACEMENT_OF_KEY = [('id', 'template_id')]
DATE_CONVERSION = ['date_created', 'date_edited']
UNWANTED_DATA = ['_links', 'created_by', 'edited_by', 'thumbnail']


class MailChimpTemplates(models.Model):
    _name = "mailchimp.templates"
    _description = "Templates"

    name = fields.Char("Name", required=True, help="The name of the template.")
    template_id = fields.Char("Template ID", copy=False)
    type = fields.Selection([('user', 'User'), ('gallery', 'Gallery'), ('base', 'Base')], default='user', copy=False,
                            help="The type of template (user, base, or gallery).")
    drag_and_drop = fields.Boolean("Drag and Drop", help="Whether the template uses the drag and drop editor.")
    responsive = fields.Boolean("Responsive", help="Whether the template contains media queries to make it responsive.")
    category = fields.Char("Template Category", help="If available, the category the template is listed in.")
    date_created = fields.Datetime("Created On")
    date_edited = fields.Datetime("Edited On")
    active = fields.Boolean("Active", default=True)
    folder_id = fields.Char("Folder ID", help="The id of the folder the template is currently in.")
    share_url = fields.Char("Share URL", help="The URL used for template sharing")
    account_id = fields.Many2one("mailchimp.accounts", string="Account", required=True, ondelete='cascade')
    # body_html = fields.Html(string='Body', sanitize_attributes=False)
    is_exported = fields.Boolean('Is Exported', help='This flag using identified template exported odoo to mailchimp')
    body_arch = fields.Html(string='Body', translate=False)
    body_html = fields.Html(string='Body converted to be send by mail', sanitize_attributes=False)


    def create_or_update_template(self, values_dict, account=False):
        template_id = values_dict.get('id')
        existing_list = self.search([('template_id', '=', template_id)])
        for item in UNWANTED_DATA:
            values_dict.pop(item)
        for old_key, new_key in REPLACEMENT_OF_KEY:
            values_dict[new_key] = values_dict.pop(old_key)
        for item in DATE_CONVERSION:
            if values_dict.get(item, False) == '':
                values_dict[item] = False
            if values_dict.get(item, False):
                values_dict[item] = account.covert_date(values_dict.get(item))
        values_dict.update({'account_id': account.id})
        values_dict.pop('content_type')
        if not existing_list:
            existing_list = self.create(values_dict)
        else:
            existing_list.write(values_dict)
        return True


    def import_templates(self, account=False):
        if not account:
            raise Warning("MailChimp Account not defined to import templates")
        count = 1000
        offset = 0
        template_list = []
        while True:
            prepared_vals = {'count': count, 'offset': offset}
            response = account._send_request('templates', {}, params=prepared_vals)
            if len(response.get('templates')) == 0:
                break
            if isinstance(response.get('templates'), dict):
                template_list += [response.get('templates')]
            template_list += response.get('templates')
            offset = offset + 1000
        for template_dict in template_list:
            self.create_or_update_template(template_dict, account=account)
        return True

    def export_update_templates_mailchimp(self, account=False):
        for record in self:
            body_html = self.env['mail.render.mixin']._replace_local_links(record.body_html)
            prepared_vals = {'name': record.name, 'html': body_html,'type':record.type,'drag_and_drop':record.drag_and_drop,'responsive':record.responsive}
            if record.template_id:
                # return True
                response = record.account_id._send_request('templates/%s' % (record.template_id), prepared_vals,method='PATCH')
            else:
                response = record.account_id._send_request('templates', prepared_vals, method='POST')
            # account.covert_date(values_dict.get(item))
            date_created = response.get('date_created') and datetime.strptime(response.get('date_created'), "%Y-%m-%dT%H:%M:%S+00:00") or False
            date_edited = response.get('date_edited') and datetime.strptime(response.get('date_edited'),"%Y-%m-%dT%H:%M:%S+00:00") or False
            record.write({
                'template_id': response.get('id'),
                'type': response.get('type'),
                'drag_and_drop': response.get('drag_and_drop'),
                'responsive': response.get('responsive'),
                'category': response.get('category'),
                'date_created': date_created,
                'date_edited': date_edited,
                'active': response.get('active'),
                'share_url': response.get('share_url'),
                'is_exported': True
            })
        return True
