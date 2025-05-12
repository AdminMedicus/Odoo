# -*- coding: utf-8 -*-
{
    'name': "Modification Contact Sale",
    'summary': 'Additional for contacts and sale',
    'version': '18.0.0.0.5',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',

    'depends': [
        'contacts',
        'sale_management',
        'stock'
    ],

    'data': [
        # security
        'security/ir.model.access.csv',
        # views
        'views/td_res_region_views.xml',
        'views/res_partner_views.xml',
        'views/sale_report_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        # menu
        'views/region_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'td_contact_sale/static/src/style.scss'
        ],
    },
    'installable': 'True',
    'application': False,
}
