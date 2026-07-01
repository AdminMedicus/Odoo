{
    'name': 'Medicus Exchange Warning',
    'version': '18.0.1.0.0',
    'summary': 'Warnings and retry actions for failed exchange records',
    'category': 'Integration/Extension',
    'author': 'Todo',
    'website': 'https://todo.ltd',
    'license': 'LGPL-3',
    'depends': [
        'td_medicus_exchange_sale',
    ],
    'data': [
        'views/ata_exchange_warning_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
