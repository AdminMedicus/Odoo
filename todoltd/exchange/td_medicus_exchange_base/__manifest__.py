{
    'name': 'Medicus Exchange (Base)',
    'version': '18.0.1.4.0',
    'summary': 'Base module for exchange integration',
    'description': """
        Base module for exchange integration with Medicus system.
    """,
    'category': 'Integration/Extension',
    'author': 'Todo',
    'website': 'https://todo.ltd',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'ata_exchange_v4',
        'product',
        'td_medicus_1c_integration',
    ],  
    'data': [
        'data/ata_exchange_method_data.xml',        
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
