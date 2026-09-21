{
    'name': 'Vchasno Partner',
    'summary': 'Vchasno integration for Partner module',

    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    'category': 'Hidden/Tools',
    'license': 'OPL-1',
    'version': '18.0.0.0.2',

    'depends': [
        'kw_vchasno',
    ],

    'external_dependencies': {
        'python': [],
    },

    'data': [
        'views/res_partner_views.xml',
        'views/vchasno_document_views.xml',
        'wizard/vchasno_download.xml',
    ],
    'demo': [
    ],

    'installable': True,
    'auto_install': False,
    'application': False,

}
