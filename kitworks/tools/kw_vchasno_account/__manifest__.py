{
    'name': 'Vchasno Account',
    'summary': 'Vchasno integration for Account module',

    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    'category': 'Hidden/Tools',
    'license': 'OPL-1',
    'version': '18.0.0.0.3',

    'depends': [
        'account',
        'kw_vchasno_partner',
    ],

    'external_dependencies': {
        'python': [],
    },

    'data': [
        'wizard/account_invoice_send_views.xml',
    ],
    'demo': [
    ],

    'installable': True,
    'auto_install': False,
    'application': False,

}
