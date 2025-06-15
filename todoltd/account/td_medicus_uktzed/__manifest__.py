{
    'name': 'TD Medicus UKTZED',
    "version": '18.0.0.0.1',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',
    'depends': [
        'accountant',
        'stock',
    ],
    'data': [
        # data
        'data/uktzed_data.xml',
        # security
        'security/ir.model.access.csv',
        # views
        'views/td_uktzed_views.xml',
        'views/product_template_views.xml',
        'views/stock_lot_views.xml',
    ],
    "installable": True,
    "application": True,
}
