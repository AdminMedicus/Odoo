{
    'name': 'TD Medicus 1C Integration',
    'description': '',
    "version": '18.0.0.0.3',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',
    'depends': [
        'stock',
        'td_medicus_uktzed',
    ],
    'data': [
        # security
        'security/ir.model.access.csv',
        # # views
        'views/td_manufacturer_directory_views.xml',
        'views/td_one_c_category_views.xml',
        'views/product_template_views.xml',
        'views/stock_warehouse_views.xml',
        'views/td_tax_invoice_views.xml',
    ],
    "installable": True,
    "application": True,
}
