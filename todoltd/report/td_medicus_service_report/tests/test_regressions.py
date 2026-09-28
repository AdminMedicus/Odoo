"""Focused model regressions runnable without an Odoo database.

The doubles provide only the ORM boundary. The exercised methods are loaded
from the module itself and their user-visible messages and saved values are
checked below.
"""

import importlib.util
import itertools
import sqlite3
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
IDS = itertools.count(1)


class Field:
    def __init__(self, kind="char", **kwargs):
        self.type = kind
        self.tracking = kwargs.get("tracking", False)
        self.label = kwargs.get("string", "")

    def _description_string(self, env):
        return self.label


class Relation:
    def __init__(self, *records):
        self.records = list(records)

    @property
    def ids(self):
        return [record.id for record in self.records]

    def mapped(self, field):
        return [getattr(record, field) for record in self.records]

    def __bool__(self):
        return bool(self.records)

    def __iter__(self):
        return iter(self.records)


class Model:
    def __init__(self, **values):
        self.id = next(IDS)
        self.display_name = f"{type(self).__name__} {self.id}"
        self.env = types.SimpleNamespace(cr=types.SimpleNamespace(execute=lambda sql: None),
                                         context={})
        self.messages = []
        self.message_subtypes = []
        self.td_lot_ids = Relation()
        self.td_agreement_ids = Relation()
        self.number = False
        self.agreement_number = False
        self._fields = {
            "td_lot_ids": Field("many2many", string="Equipment Serial Number"),
            "td_agreement_ids": Field("many2many", string="Agreements"),
        }
        self.__dict__.update(values)

    def __iter__(self):
        yield self

    def __getitem__(self, name):
        return getattr(self, name)

    def create(self, values_list):
        return [type(self)(**values) for values in values_list]

    def init(self):
        pass

    def write(self, values):
        self.__dict__.update(values)
        return True

    def message_post(self, body, subtype_xmlid=None):
        self.messages.append(str(body))
        self.message_subtypes.append(subtype_xmlid)


def load_models():
    class Markup(str):
        def __mod__(self, values):
            return Markup(super().__mod__(values))

        def join(self, values):
            return Markup(super().join(values))

    api = types.SimpleNamespace(
        model=lambda fn: fn,
        model_create_multi=lambda fn: fn,
        depends=lambda *args: lambda fn: fn,
        onchange=lambda *args: lambda fn: fn,
    )
    fields = types.SimpleNamespace(**{
        name: (lambda kind: lambda **kw: Field(kind, **kw))(kind)
        for name, kind in {
            "Char": "char", "Integer": "integer", "Many2one": "many2one",
            "Many2many": "many2many", "One2many": "one2many", "Binary": "binary",
            "Boolean": "boolean", "Date": "date", "Selection": "selection",
            "Text": "text",
        }.items()
    })
    fields.Date.context_today = lambda *args: None
    odoo = types.ModuleType("odoo")
    odoo.api, odoo.fields, odoo.models = api, fields, types.SimpleNamespace(Model=Model)
    odoo._ = lambda message, *args: message % args if args else message
    exceptions = types.ModuleType("odoo.exceptions")
    exceptions.UserError = type("UserError", (Exception,), {})
    tools = types.ModuleType("odoo.tools")
    tools.format_date = lambda env, value, **kwargs: str(value)
    markupsafe = types.ModuleType("markupsafe")
    markupsafe.Markup = Markup
    package = types.ModuleType("td_medicus_service_report")
    package.__path__ = [str(ROOT)]
    models_package = types.ModuleType("td_medicus_service_report.models")
    models_package.__path__ = [str(ROOT / "models")]
    with patch.dict(sys.modules, {"odoo": odoo, "odoo.exceptions": exceptions,
                                  "odoo.tools": tools, "markupsafe": markupsafe,
                                  "td_medicus_service_report": package,
                                  "td_medicus_service_report.models": models_package}):
        loaded = {}
        for name in ("relation_chatter", "td_agreement", "helpdesk_ticket",
                     "stock_lot", "td_service_report"):
            qualified = f"td_medicus_service_report.models.{name}"
            spec = importlib.util.spec_from_file_location(
                qualified, ROOT / "models" / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[qualified] = module
            spec.loader.exec_module(module)
            loaded[name] = module
        return loaded


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_models()

    def test_agreement_numbers_stay_equal_from_either_input(self):
        agreement = self.modules["td_agreement"].TdAgreement()
        from_visible, from_legacy = agreement.create([
            {"agreement_number": "1735"}, {"number": "2001"},
        ])
        self.assertEqual((from_visible.agreement_number, from_visible.number), ("1735", "1735"))
        self.assertEqual((from_legacy.agreement_number, from_legacy.number), ("2001", "2001"))
        from_visible.write({"number": "2002"})
        self.assertEqual((from_visible.agreement_number, from_visible.number), ("2002", "2002"))
        from_visible.write({"agreement_number": "2003"})
        self.assertEqual((from_visible.agreement_number, from_visible.number), ("2003", "2003"))

    def test_agreement_keeps_number_assigned_by_parent_create(self):
        original = Model.create

        def parent_creates_number(model, values_list):
            records = original(model, values_list)
            for record in records:
                if not record.number:
                    record.number = "AUTO-21"
            return records

        with patch.object(Model, "create", parent_creates_number):
            (record,) = self.modules["td_agreement"].TdAgreement().create([{}])
        self.assertEqual((record.agreement_number, record.number), ("AUTO-21", "AUTO-21"))

    def test_existing_agreements_are_aligned_on_update(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE td_agreement (id INTEGER, number TEXT, agreement_number TEXT)")
            connection.executemany("INSERT INTO td_agreement VALUES (?, ?, ?)", [
                (1, None, "1735"), (2, "2001", None), (3, "old", "visible"),
            ])
            agreement = self.modules["td_agreement"].TdAgreement()
            agreement.env.cr = connection
            agreement.init()
            rows = connection.execute(
                "SELECT number, agreement_number FROM td_agreement ORDER BY id").fetchall()
            self.assertEqual(rows, [("1735", "1735"), ("2001", "2001"),
                                    ("visible", "visible")])
        finally:
            connection.close()

    def test_report_creation_lists_initial_values_on_ticket(self):
        report_class = self.modules["td_service_report"].TdServiceReport
        ticket = Model()
        report = report_class(ticket_id=ticket, name="Service Report 4", td_service_hours="7")
        report._fields = {"td_service_hours": Field("char", string="Service Hours", tracking=True)}
        report._post_ticket_message(created=True)
        self.assertIn("Service Hours", ticket.messages[0])
        self.assertIn("7", ticket.messages[0])
        self.assertEqual(ticket.message_subtypes, ["mail.mt_note"])

    def test_report_creation_does_not_log_defaults_of_inactive_blocks(self):
        report_class = self.modules["td_service_report"].TdServiceReport
        ticket = Model()
        report = report_class(ticket_id=ticket, name="Service Report 1",
                              td_is_delivery=True, td_inspection_damage="none",
                              td_is_inspection=False)
        report._fields = {
            "td_is_delivery": Field("boolean", string="Delivery", tracking=True),
            "td_inspection_damage": Field("selection", string="Visible Damage", tracking=True),
        }
        report._fields["td_inspection_damage"]._description_selection = (
            lambda env: [("none", "None")])
        report._post_ticket_message(created=True)
        self.assertIn("Delivery", ticket.messages[0])
        self.assertNotIn("Visible Damage", ticket.messages[0])

    def test_switching_same_named_agreements_still_logs_ticket_change(self):
        report_class = self.modules["td_service_report"].TdServiceReport
        ticket = Model()
        first = Model(display_name="test 24.09")
        second = Model(display_name="test 24.09")
        report = report_class(ticket_id=ticket, name="Service Report 4",
                              td_agreement_ids=Relation(first))
        report._fields = {"td_agreement_ids": Field(
            "many2many", string="Agreements", tracking=True)}
        report.write({"td_agreement_ids": Relation(second)})
        self.assertEqual(len(ticket.messages), 1)
        self.assertIn("Agreements", ticket.messages[0])
        self.assertIn(f"#{first.id}", ticket.messages[0])
        self.assertIn(f"#{second.id}", ticket.messages[0])

    def test_switching_same_named_serials_still_logs_ticket_change(self):
        report_class = self.modules["td_service_report"].TdServiceReport
        ticket = Model()
        first = Model(display_name="120001")
        second = Model(display_name="120001")
        report = report_class(ticket_id=ticket, name="Service Report 4", td_lot_id=first)
        report._fields = {"td_lot_id": Field(
            "many2one", string="Equipment Serial Number", tracking=True)}
        report.write({"td_lot_id": second})
        self.assertIn(f"#{first.id}", ticket.messages[0])
        self.assertIn(f"#{second.id}", ticket.messages[0])

    def test_ticket_agreement_change_appears_in_ticket_chatter(self):
        ticket = self.modules["helpdesk_ticket"].HelpdeskTicket()
        ticket._fields = {"td_agreement_ids": Field("many2many", string="Agreement")}
        agreement = Model(display_name="test 24.09")
        ticket.write({"td_agreement_ids": Relation(agreement)})
        self.assertIn("test 24.09", " ".join(ticket.messages))
        self.assertEqual(ticket.message_subtypes, ["mail.mt_note"])
        ticket.write({"td_agreement_ids": Relation()})
        self.assertEqual(len(ticket.messages), 2)

    def test_equipment_agreement_links_are_logged_on_edited_card(self):
        agreement = self.modules["td_agreement"].TdAgreement()
        agreement._fields = {"td_lot_ids": Field("many2many", string="Equipment Serial Number")}
        serial = Model(display_name="120001")
        agreement.write({"td_lot_ids": Relation(serial)})
        self.assertIn("120001", " ".join(agreement.messages))

        lot = self.modules["stock_lot"].StockLot()
        lot._fields = {"td_agreement_ids": Field("many2many", string="Agreements")}
        related_agreement = Model(display_name="test 24.09")
        lot.write({"td_agreement_ids": Relation(related_agreement)})
        self.assertIn("test 24.09", " ".join(lot.messages))

    def test_inverse_cards_also_log_agreement_equipment_links(self):
        agreement = self.modules["td_agreement"].TdAgreement(display_name="test 24.09")
        agreement._fields = {"td_lot_ids": Field("many2many", string="Equipment Serial Number")}
        serial = self.modules["stock_lot"].StockLot(display_name="120001")
        serial._fields = {"td_agreement_ids": Field("many2many", string="Agreements")}
        agreement.write({"td_lot_ids": Relation(serial)})
        self.assertIn("test 24.09", " ".join(serial.messages))
        agreement.write({"td_lot_ids": Relation()})
        self.assertIn("Removed", serial.messages[-1])

        another = self.modules["td_agreement"].TdAgreement(display_name="contract 2")
        another._fields = {"td_lot_ids": Field("many2many", string="Equipment Serial Number")}
        serial.write({"td_agreement_ids": Relation(another)})
        self.assertIn("120001", " ".join(another.messages))


if __name__ == "__main__":
    unittest.main()
