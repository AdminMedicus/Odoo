from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    td_warehouse_manager_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Warehouse Manager',
        help='User responsible for warehouse management tasks.'
    )
    td_medical_warehouse_manager_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Medical Warehouse Manager',
        help='User responsible for medical warehouse management tasks.'
    )
    td_responsible_manager_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Responsible Manager',
        help='User responsible for overseeing operations.'
    )
    td_president_id = fields.Many2one(
        comodel_name='hr.employee',
        string='President',
        help='User holding the position of president.'
    )
    td_head_medical_equipment_sales_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Head of Medical Equipment Sales Department',
        help='User responsible for heading the medical equipment sales department.'
    )
    td_medical_equipment_engineer_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Medical Equipment Engineer',
        help='User responsible for medical equipment engineering tasks.'
    )
    td_vice_president_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Vice President',
        help='User holding the position of vice president.'
    )
    