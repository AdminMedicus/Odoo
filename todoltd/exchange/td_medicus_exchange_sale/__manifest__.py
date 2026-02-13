{
    'name': 'Medicus Exchange (Sale)',
    'version': '18.0.1.4.16',
    'summary': 'Sale/stock module for exchange integration',
    'description': """
        Sale/stock module for exchange integration with Medicus system.
    """,
    'category': 'Integration/Extension',
    'author': 'Todo',
    'website': 'https://todo.ltd',
    'license': 'LGPL-3',
    'depends': [
        'ata_exchange_v4',
        'td_medicus_exchange_base',
        'td_medicus_1c_integration',
        'td_medicus_agreement',
        'stock',
        'account',
        'td_contact_sale',
    ],  
    'data': [
        'data/ata_exchange_method_data.xml',        
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
