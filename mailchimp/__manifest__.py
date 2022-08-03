{
    "name": "MailChimp Connector",
    "version": "15.3",
    "category": "Marketing",
    'summary': 'Integrate & Manage MailChimp Operations from Odoo',

    "depends": ["mass_mailing"],

    'data': [
        'data/ir_cron.xml',
        'data/ir_sequence_data.xml',
        # 'views/assets.xml',
        'views/mailchimp_accounts_view.xml',
        'views/mailchimp_lists_view.xml',
        'wizard/import_export_operation_view.xml',
        'views/mass_mailing_contact_view.xml',
        'views/mass_mailing_list_view.xml',
        'views/mailchimp_template_view.xml',
        'views/mailchimp_queue_process_view.xml',
        'views/mass_mailing_view.xml',
        'views/link_tracker_view.xml',
        'wizard/mass_mailing_schedule_date_view.xml',
        'views/res_partner_views.xml',
        'wizard/partner_export_update_wizard.xml',
        'security/ir.model.access.csv'
    ],

    'assets': {
        'web.assets_backend': [
            'mailchimp/static/src/scss/mailchimp.scss',
        ]
    },

    'images': ['static/description/mailchimp_odoo.png'],

    "author": "Teqstars",
    "website": "https://teqstars.com",
    'support': 'support@teqstars.com',
    'maintainer': 'Teqstars',
    "description": """
        - Manage your MailChimp operation from Odoo
        - Integration mailchimp
        - Connector mailchimp
        - mailchimp Connector
        - Odoo mailchimp Connector
        - mailchimp integration
        - mailchimp odoo connector
        - mailchimp odoo integration
        - odoo mailchimp integration
        - odoo integration with mailchimp
        - odoo teqstars apps
        - teqstars odoo apps
        - manage audience
        - manage champaign
        - email Marketing
        - mailchimp marketing
        - odoo and mailchimp
        """,

    'demo': [],
    'license': 'OPL-1',
    'live_test_url':'http://bit.ly/2n7ExKX',
    'auto_install': False,
    "installable": True,
    'application': True,
    'qweb': [],
    "price": "349.99",
    "currency": "EUR",
}
