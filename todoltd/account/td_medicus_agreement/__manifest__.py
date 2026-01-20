# -*- coding: utf-8 -*-
{
    'name': "Modification ToDo Agreement",
    'summary': 'Additional for ToDo Agreement',
    'version': '18.0.0.0.19',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',

    'depends': [
        # 'td_yaroslav_agreement',
        'td_agreement',
        'sale',
        'purchase',
        'delivery',
        'stock',
        'td_contact_sale',
        'td_medicus_uktzed',
    ],

    'data': [
        # security
        'security/ir.model.access.csv',
        # views
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_type_views.xml',
        'views/td_agreement_types_views.xml',
        # yaroslav agreement
        'views/td_agreements_reporting.xml',
        'views/td_agreement_closing_reasons_views.xml',
        # views
        'views/td_agreement_views.xml',
        # wizard
        'wizard/td_agreement_stock_move_views.xml',
        'wizard/td_agreement_closing_wizard_views.xml',
        # report
        'report/td_stock_report.xml'
    ],
    'installable': 'True',
    'application': False,
}
