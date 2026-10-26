# -*- coding: utf-8 -*-
{
    'name': 'TD Medicus Equipment Partner',
    'summary': 'Helpdesk: client and equipment are resolved independently, '
               'the equipment owner is kept on the serial number, '
               'equipment applicants are registered per serial number',
    'description': """
The ticket client (payer, by EDRPOU) and the equipment (by serial number) are
resolved independently. The owner of a serial number comes from sale
deliveries, the ticket shows a "not owner" notice, and every company that
asked for service on a serial number is kept as an equipment applicant.
    """,
    'version': '18.0.1.0.1',
    'category': 'Services/Helpdesk',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'depends': [
        'helpdesk_stock',
        'helpdesk_repair',
        'td_medicus_agreement',
        'td_medicus_helpdesk_website_autofill',
        'td_medicus_service_report',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/td_equipment_applicant_views.xml',
        'views/td_equipment_applicant_menus.xml',
        'views/helpdesk_ticket_views.xml',
        'views/stock_lot_views.xml',
        'views/td_service_report_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
