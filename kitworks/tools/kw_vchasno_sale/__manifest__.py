{
    'name': 'Vchasno Sale Pro-Forma',
    'summary': 'Vchasno integration for Sale module',

    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    'category': 'Hidden/Tools',
    'license': 'OPL-1',
    'version': '18.0.0.3.1',

    'depends': [
        'kw_vchasno_partner',
        'sale',
    ],

    'external_dependencies': {
        'python': [],
    },

    'data': [
        'wizard/mail_compose_message_views.xml',
    ],
    'demo': [
    ],

    'installable': True,
    'auto_install': False,
    'application': False,

}
