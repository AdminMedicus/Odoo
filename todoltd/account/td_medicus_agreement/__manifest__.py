# -*- coding: utf-8 -*-
{
    'name': "Modification ToDo Agreement",
    'summary': 'Additional for ToDo Agreement',
    'version': '18.0.0.0.1',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',

    'depends': [
        'td_yaroslav_agreement',
    ],

    'data': [
        # views
        'views/td_agreement_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': 'True',
    'application': False,
}
