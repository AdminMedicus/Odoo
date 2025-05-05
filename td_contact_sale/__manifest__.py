# -*- coding: utf-8 -*-
{
    'name': "ToDo Contact Sale",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
        Long description of module's purpose
    """,

    'author': "ToDo",
    'website': "https://www.yourcompany.com",

    'category': 'CRM Sale',
    'version': '17.0.0.0.1',

    'depends': ['contacts', 'sale'],

    'data': [
        # security
        'security/ir.model.access.csv',
        # views
        'views/td_res_region_views.xml',
        'views/res_partner_views.xml',
        'views/sale_report_views.xml',
        # menu
        'views/region_menu_views.xml',
    ],
}
