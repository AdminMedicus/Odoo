{
    'name': 'Medicus Completion act (Sale)',
    'version': '18.0.1.0.7',
    'summary': 'Sale',
    'description': 'Medicus Sale: Act of Completion',
    'category': 'Sale',
    'author': 'Todo',
    'website': 'https://todo.ltd',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'mrp',
        'td_medicus_report',
        'td_medicus_agreement',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_bom_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_template_views.xml',
        'wizard/td_confirmation_bom_wizard_views.xml'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
