{
    'name': 'Vchasno',
    'summary': 'Integration with Vchasno electronic document '
               'management system',

    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    'category': 'Hidden/Tools',
    'license': 'OPL-1',
    'version': '18.0.0.6.1',

    'depends': [
        'base',
        'web',
    ],

    'external_dependencies': {
        'python': ['html2text'],
    },

    'data': [
        'data/kw.vchasno.status.xml',
        'data/kw.vchasno.category.xml',
        'data/ir_cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/meny_views.xml',
        'views/vchasno_key_views.xml',
        'views/vchasno_log_view.xml',
        'views/vchasno_catalog_view.xml',
        'views/vchasno_document_views.xml',
        'views/res_parnter_views.xml',
        'wizard/vchasno_download.xml',
    ],
    'demo': [
    ],

    'assets': {
        'web.assets_backend': [
            'kw_vchasno/static/src/js/open_vchasno_document_wizard.js',
            'kw_vchasno/static/src/xml/open_vchasno_document_wizard.xml',
        ],
    },

    'installable': True,
    'auto_install': False,
    'application': True,

    'images': [
        'static/description/cover.png',
        'static/description/icon.png',
    ],

    'price': 100,
    'currency': 'EUR',

}
