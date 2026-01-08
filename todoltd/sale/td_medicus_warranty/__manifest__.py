# -*- coding: utf-8 -*-
{
    'name': "Product Warranty Management",
    'summary': 'Manage product warranties and claims',
    'version': '18.0.0.0.9',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Sales',

    'depends': [
        'product',
        'sale',
        'stock',
        'account',
        'td_medicus_1c_integration',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/td_warranty_period_views.xml',
        'views/td_warranty_record_views.xml',
        'views/product_template_views.xml',
        'wizards/td_warranty_bulk_link_wizard_views.xml',
        'views/account_move_views.xml',
        'views/stock_picking_views.xml',
        'views/res_partner_views.xml',
        'views/stock_lot_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {

    },
    'installable': True,
    'application': False,
}
