# -*- coding: utf-8 -*-
{
    'name': "TD Medicus Service Report",
    'summary': 'Service reports on helpdesk tickets with a printable service form',
    'description': """
Service Report for the Medicus Service Department
=================================================

* A "Service Report" tab on the helpdesk ticket holding several reports per ticket.
* Service category checkboxes (delivery, installation, repair, maintenance,
  demonstration, equipment inspection) with a dedicated block of fields each.
* Agreement <-> equipment serial number relation.
* Semi-automatic Warranty / Non-warranty detection based on the serial
  number warranty records.
* A printable form built only from the blocks that were actually filled in,
  laid out like the paper service report of the department.
* The "Replacement" table of the repair block is filled from the spare parts
  of the repair order linked to the report.
""",
    'version': '18.0.1.1.0',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Services/Helpdesk',

    'depends': [
        'stock',
        'helpdesk',
        'repair',
        'helpdesk_repair',
        'td_medicus_working_with_service',
        'td_medicus_warranty',
        'td_medicus_agreement',
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/td_service_report_rules.xml',
        'report/report_paperformat.xml',
        'report/td_service_report_templates.xml',
        'report/report_actions.xml',
        'views/td_service_report_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/td_agreement_views.xml',
        'views/stock_lot_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
}
