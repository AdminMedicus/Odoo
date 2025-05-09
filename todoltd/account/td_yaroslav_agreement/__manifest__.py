{
    'name': 'TD Yaroslav Agreement',
    'description': '',
    "version": '18.0.1.0.6',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',
    'depends': [
        'td_agreement',
        'sale',
        'purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/td_agreement_closing_reasons_views.xml',
        'views/td_agreement_closing_wizard_views.xml',
        'views/td_agreements_reporting.xml',
        'views/td_agreement_views.xml',
    ],
    "installable": True,
    "application": True,
}
