from odoo import api, fields, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams


class TdResRegion(models.Model):
    _name = "td.res.country.region"
    _inherit = ["td.res.country.region",'ata.exchange.model.handler.mixin']

    full_name = fields.Char(
        string="Full name",
        compute='_compute_full_name',
        store=True,
        recursive=True
    )
    
    @api.depends('name', 'parent_region_id', 'parent_region_id.full_name')
    def _compute_full_name(self):
        for record in self:
            if record.parent_region_id:
                record.full_name = f"{record.parent_region_id.full_name}/{record.name}"
            else:
                record.full_name = record.name or "" 
    
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:

        full_name: str = record_params.data['full_name']
        name_list = full_name.split('/')

        parent_id = None
        if len(name_list) > 1:
            full_name_parent = "/".join(name_list[:-1])
            parent_params = record_params.build(self.env, 'td.res.country.region')
            parent_params.data = {'full_name': full_name_parent}
            parent_params.create_record = True
            parent_params.search_params.search_domain = [
                ('full_name', '=', full_name_parent)
            ]
            parent_id = self.ata_exchange_get_model_record(parent_params)
        
        vals = {
            "name": name_list[-1],
            **({"parent_region_id": parent_id.id} if parent_id else {})
        }
        
        return vals
