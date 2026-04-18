from odoo import api, models


class TdAccountTax(models.Model):
	_name = 'account.tax'
	_inherit = ['account.tax','ata.exchange.class']

	ata_tax_group_type = {}

	@api.model
	def ata_exchange_init_vat_type(self):
		types_vat = ('vat20', 'vat14', 'vat7', 'vat0', 'vat_free', 'not_vat')

		try:
			module_name = 'l10n_ua'
			module = self.env['ir.module.module'].search([('name', '=', module_name)], limit=1)
			if module.state == 'installed':
				for type_vat in types_vat:
					self.ata_tax_group_type[self.env.ref(f'account.1_tax_group_{type_vat}')] = type_vat
		except ValueError:
			pass

	def ata_exchange_get_vat_type(self) -> str:
		if len(self.ata_tax_group_type) == 0:
			self.ata_exchange_init_vat_type()

		for record in self:
			type_vat = self.ata_tax_group_type.get(record.tax_group_id, '')
			if type_vat:
				return type_vat

		return ''

	# override
	def ata_exchange_get_data_record(self, method = None, as_node = False) -> list[dict]|dict|str:
		return {
			"vat_type": self.ata_exchange_get_vat_type(),
		} if self else ""
