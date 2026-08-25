from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import (
    IncomingParam,
)
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import (
    RecordHandlerParams,
)
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestProductImportIdentity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.handler = cls.env['ata.exchange.model.handler']
        cls.product_model = cls.env['product.product']
        cls.method = cls.env.ref(
            'td_medicus_exchange_base.product_1c_odoo'
        )
        cls.ext_system = cls.env.ref(
            'td_medicus_exchange_base.medicus_1c'
        )

    def _record_params(self, external_id, name, catalog_code='AU00T0'):
        incoming_params = IncomingParam(
            method_id=self.method,
            ext_system_id=self.ext_system,
        )
        params = RecordHandlerParams.build_from_class(
            self.env,
            'product.product',
            incoming_params,
        )
        params.data = {
            'id': external_id,
            'name': name,
            'name_full': name,
            'catalog_code': catalog_code,
        }
        params.search_params.use_matching_data = True
        params.search_params.key_matching_data = 'id'
        return params

    def test_same_catalog_code_different_name_does_not_rebind(self):
        self.product_model.create({
            'name': 'ІОЛ AU00T0 24.0',
            'default_code': 'AU00T0',
        })

        params = self._record_params(
            'BAS-AU00T0-26.5',
            'ІОЛ AU00T0 26.5',
        )

        product = self.handler._find_product_rebind(params)

        self.assertFalse(product)

    def test_same_catalog_code_and_name_can_rebind(self):
        expected_product = self.product_model.create({
            'name': 'ІОЛ AU00T0 24.0',
            'default_code': 'AU00T0',
        })

        params = self._record_params(
            'BAS-AU00T0-24.0',
            ' ІОЛ   AU00T0 24.0 ',
        )

        product = self.handler._find_product_rebind(params)

        self.assertEqual(product, expected_product)

    def test_many_external_ids_for_one_product_are_not_trusted(self):
        product = self.product_model.create({
            'name': 'ІОЛ AU00T0 24.0',
            'default_code': 'AU00T0',
        })
        self.env['ata.exchange.matching.data'].create([
            {
                'method_id': self.method.id,
                'ext_system_id': self.ext_system.id,
                'key_object': 'BAS-AU00T0-24.0',
                'stage': '',
                'matching_data': {'product.product': product.id},
            },
            {
                'method_id': self.method.id,
                'ext_system_id': self.ext_system.id,
                'key_object': 'BAS-AU00T0-26.5',
                'stage': '',
                'matching_data': {
                    'product.product': product.id,
                    'extra.test.key': True,
                },
            },
        ])
        params = self._record_params(
            'BAS-AU00T0-26.5',
            'ІОЛ AU00T0 26.5',
        )

        with self.assertRaises(ValidationError):
            self.handler.search_records(params)

    def test_new_external_id_does_not_reuse_another_ids_product(self):
        product = self.product_model.create({
            'name': 'ІОЛ AU00T0 24.0',
            'default_code': 'AU00T0',
        })
        self.env['ata.exchange.matching.data'].create({
            'method_id': self.method.id,
            'ext_system_id': self.ext_system.id,
            'key_object': 'BAS-ORIGINAL-ID',
            'stage': '',
            'matching_data': {
                'product.product': product.id,
                'extra.test.key': True,
            },
        })
        params = self._record_params(
            'BAS-ANOTHER-ID',
            'ІОЛ AU00T0 24.0',
        )

        found_product = self.handler.search_records(params)

        self.assertFalse(found_product)
