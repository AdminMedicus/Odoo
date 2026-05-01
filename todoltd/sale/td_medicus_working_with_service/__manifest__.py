# -*- coding: utf-8 -*-
{
    'name': "TD Medicus Working with Service",
    'summary': 'Medicus Working with Service, Custom Help desk',
    'version': '18.0.1.0.2',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',

    'depends': [
        'helpdesk',
        'crm_helpdesk',
        'helpdesk_fsm',
    ],

    'data': [
        'views/helpdesk_ticket_views.xml',
        'views/res_partner_views.xml',
        'views/project_task_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
}
