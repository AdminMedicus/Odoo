{
    'name': 'Vchasno integration Bundle',
    'summary': 'Complete Vchasno integration package for Odoo',

    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    'category': 'Extra Tools',
    'license': 'OPL-1',
    'version': '18.0.1.0.0',

    'depends': [
        'kw_vchasno',
        'kw_vchasno_partner',
        'kw_vchasno_account',
        'kw_vchasno_sale',
    ],

    'external_dependencies': {
        'python': [],
    },

    'data': [
    ],
    'demo': [
    ],

    'installable': True,
    'auto_install': False,
    'application': False,

    'images': [
        'static/description/cover.png',
        'static/description/icon.png',
    ],
}
