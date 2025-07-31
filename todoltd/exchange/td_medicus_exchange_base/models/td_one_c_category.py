from odoo import api, fields, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams


class TdOneCCategory(models.Model):
    _name = "td.one_c.category"
    _inherit = ["td.one_c.category",'ata.exchange.model.handler.mixin']

    full_name = fields.Char(
        string="Full name",
        compute='_compute_full_name',
        store=True,
        recursive=True
    )
    
    @api.depends('name', 'parent_id', 'parent_id.full_name')
    def _compute_full_name(self):
        for record in self:
            if record.parent_id:
                record.full_name = f"{record.parent_id.full_name}/{record.name}"
            else:
                record.full_name = record.name or "" 
    
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:

        full_name: str = record_params['data']['full_name']
        name_list = full_name.split('/')

        if len(name_list) > 1:
            parent_category_1c_id = self.ata_exchange_get_model_record({
                **(default_params:=self.ata_exchange_get_default_record_handler_params('td.one_c.category')),
                'data': {
                    'full_name': (full_name_parent := "/".join(name_list[:-1]))
                },
                'create_record': True,
                'search_params': {
                    **default_params['search_params'],
                    'search_domain': [
                        ('full_name', '=', full_name_parent)
                    ]
                }
            })
        else:
            parent_category_1c_id = None
        
        vals = {
            "name": name_list[-1],
            **({"parent_id": parent_category_1c_id.id} if parent_category_1c_id else {})
        }
        
        return vals
