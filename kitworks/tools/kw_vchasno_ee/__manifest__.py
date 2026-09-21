# flake8: noqa
{
    'name': 'Vchasno EE',
    'version': '18.0.1.0.6',
    'license': 'OPL-1',
    'category': 'Document',
    'summary': 'Vchasno EE Version',


    'author': 'Kitworks Systems',
    'website': 'https://kitworks.systems/',

    # 'images': [
    #     'static/description/cover.png',
    # ],

    'depends': ['documents', 'kw_vchasno'],
    'data': [
        'views/kw_document.xml',
        'wizard/vchasno_download.xml',
    ],

    'application': True,
    'installable': True,
}
