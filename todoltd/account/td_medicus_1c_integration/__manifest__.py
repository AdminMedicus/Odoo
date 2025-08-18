{
    'name': 'TD Medicus 1C Integration',
    "version": '18.0.0.0.20',
    'author': 'ToDo',
    'website': 'https://todo.ltd',
    'license': 'OPL-1',
    'category': 'Other',
    'depends': [
        'stock',
        'sale',
        'account',
        'purchase_stock',
        'td_medicus_uktzed',
        'td_medicus_agreement'
    ],
    'data': [
        # data
        'data/ir_cron_data.xml',
        # security
        'security/ir.model.access.csv',
        'security/tax_invoices_groups.xml',
        # views
        'views/td_manufacturer_directory_views.xml',
        'views/td_one_c_category_views.xml',
        'views/product_template_views.xml',
        'views/stock_warehouse_views.xml',
        'views/td_tax_invoice_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_type_views.xml',
        # wizard
        'wizard/sale_make_invoice_advance.xml',
        'wizard/td_sale_order_low_margin_warning.xml'
    ],
    "installable": True,
    "application": True,
}
