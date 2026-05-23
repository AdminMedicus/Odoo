{
    'name': 'TD Helpdesk Website Form: Client & S/N Auto-fill',
    'version': '18.0.1.0.2',
    'category': 'Services/Helpdesk',
    'summary': 'Auto-fill partner_id, td_equipment_id and td_serial_number_id '
               'on helpdesk tickets created via the website form, based on '
               'EDRPOU code (company_registry) and serial number.',
    'author': 'ToDo',
    'website': 'https://www.todo.ltd',
    'depends': [
        'website',
        'helpdesk',
        'website_helpdesk',
        'stock',
        'td_medicus_working_with_service',
    ],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
