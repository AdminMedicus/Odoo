# -*- coding: utf-8 -*-
{
    'name': "Modification ToDo Agreement",
    'summary': 'Additional for ToDo Agreement',
    'version': '18.0.0.0.13',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',

    'depends': [
        'td_yaroslav_agreement',
        'delivery',
        'stock',
        'td_contact_sale',
        'td_medicus_uktzed',
    ],

    'data': [
        # security
        'security/ir.model.access.csv',
        # views
        'views/td_agreement_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_type_views.xml',
        # wizard
        'wizard/td_agreement_stock_move_views.xml',
        # report
        'report/td_stock_report.xml'
    ],
    'installable': 'True',
    'application': False,
}
