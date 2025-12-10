from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    td_warehouse_manager_id = fields.Many2one(
        'hr.employee',
        string='Warehouse Manager',
        help='User responsible for warehouse management tasks.'
    )
    td_medical_warehouse_manager_id = fields.Many2one(
        'hr.employee',
        string='Medical Warehouse Manager',
        help='User responsible for medical warehouse management tasks.'
    )
    td_responsible_manager_id = fields.Many2one(
        'hr.employee',
        string='Responsible Manager',
        help='User responsible for overseeing operations.'
    )
    td_president_id = fields.Many2one(
        'hr.employee',
        string='President',
        help='User holding the position of president.'
    )
    