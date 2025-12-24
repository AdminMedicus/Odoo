# -*- coding: utf-8 -*-
{
    'name': "ToDo Medicus Reports",
    'summary': 'Друковані форми для Medicus',
    'version': '18.0.0.0.11',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Reporting',

    'depends': [
        'account',
        'sale',
        'stock',
        'td_contact_sale',
        'td_medicus_agreement',
        'td_medicus_1c_integration',
    ],

    'data': [
        'security/ir.model.access.csv',
        'report/report_actions.xml',
        'report/report_template.xml',
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/stock_location_views.xml',
        'views/td_stock_condition_views.xml',
        'views/stock_picking_views.xml',
        'views/hr_employee_views.xml',
    ],
    
    'assets': {
        'web.report_assets_common': [
            'td_medicus_report/static/src/css/wholesale_invoice.css',
        ],
    },
    
    'installable': True,
    'application': False,
}
