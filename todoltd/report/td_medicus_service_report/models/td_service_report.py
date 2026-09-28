# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

WARRANTY_SELECTION = [
    ('warranty', 'Warranty'),
    ('non_warranty', 'Non-warranty'),
]

# Checkbox fields of the "Service category" block, in the order of the paper form.
SERVICE_CATEGORIES = [
    'td_is_delivery',
    'td_is_installation',
    'td_is_repair',
    'td_is_maintenance',
    'td_is_demonstration',
    'td_is_inspection',
]

# Per-block "Warranty / Non-warranty" fields and the checkbox that governs them.
WARRANTY_BLOCKS = [
    ('td_repair_warranty_type', 'td_is_repair'),
    ('td_maintenance_warranty_type', 'td_is_maintenance'),
    ('td_demonstration_warranty_type', 'td_is_demonstration'),
    ('td_inspection_warranty_type', 'td_is_inspection'),
]


class TdServiceReport(models.Model):
    """One service visit documented on a helpdesk ticket.

    NOTE: the model deliberately does NOT inherit ``mail.thread``: the
    specification asks for the changes to land in the chatter of the *ticket*,
    which ``_post_ticket_message`` does. The ``tracking=True`` attributes are
    kept as the declarative list of the fields worth logging there.
    """

    _name = 'td.service.report'
    _description = 'Service Report'
    _order = 'ticket_id, sequence_number, id'
    _rec_name = 'name'

    _sql_constraints = [
        ('td_service_report_sequence_uniq',
         'unique(ticket_id, sequence_number)',
         'Service report numbers must be unique per ticket.'),
    ]

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
    )
    sequence_number = fields.Integer(
        string='Number',
        default=1,
        readonly=True,
        copy=False,
    )
    ticket_id = fields.Many2one(
        comodel_name='helpdesk.ticket',
        string='Ticket',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='ticket_id.company_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        related='ticket_id.partner_id',
        store=True,
        readonly=True,
    )
    td_date_report = fields.Date(
        string='Preparation Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help='Date the service report is drawn up. Defaults to today and can be changed.',
    )
    td_service_hours = fields.Char(
        string='Service Hours',
        tracking=True,
        help='Number of service hours, free text as on the paper form.',
    )
    td_engineer_id = fields.Many2one(
        comodel_name='res.users',
        string='Engineer',
        tracking=True,
        default=lambda self: self.env.user,
    )

    # ------------------------------------------------------------------
    # Equipment / agreement
    # ------------------------------------------------------------------
    td_lot_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Equipment Serial Number',
        tracking=True,
    )
    td_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Equipment',
        related='td_lot_id.product_id',
        store=True,
        readonly=True,
    )
    td_equipment_address = fields.Char(
        string='Equipment Location Address',
        tracking=True,
        help='Address the equipment is installed at, as printed on the form. '
             'Prefilled from the customer of the ticket and can be corrected.',
    )
    td_agreement_ids = fields.Many2many(
        comodel_name='td.agreement',
        relation='td_service_report_agreement_rel',
        column1='report_id',
        column2='agreement_id',
        string='Agreements',
        tracking=True,
    )
    td_agreement_domain = fields.Binary(
        string='Agreement Domain',
        compute='_compute_td_agreement_domain',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Warranty suggestion (section 5 of the specification)
    # ------------------------------------------------------------------
    td_warranty_suggestion = fields.Selection(
        selection=WARRANTY_SELECTION,
        string='Suggested Warranty State',
        compute='_compute_td_warranty_suggestion',
        help='Value proposed by the system from the warranty records of the '
             'serial number. The engineer confirms or overrides it in every block.',
    )
    td_warranty_date_end_manufacturer = fields.Date(
        string='Manufacturer Warranty Until',
        compute='_compute_td_warranty_suggestion',
    )
    td_warranty_date_end_company = fields.Date(
        string='Company Warranty Until',
        compute='_compute_td_warranty_suggestion',
    )

    # ------------------------------------------------------------------
    # Service categories
    # ------------------------------------------------------------------
    td_is_delivery = fields.Boolean(string='Delivery', tracking=True)
    td_is_installation = fields.Boolean(string='Installation', tracking=True)
    td_is_repair = fields.Boolean(string='Repair / Technical Maintenance', tracking=True)
    td_is_maintenance = fields.Boolean(string='Maintenance / Setup', tracking=True)
    td_is_demonstration = fields.Boolean(string='Demonstration / Consulting', tracking=True)
    td_is_inspection = fields.Boolean(
        string='Equipment Inspection on Call / Removal for Repair',
        tracking=True,
    )
    td_category_summary = fields.Char(
        string='Categories',
        compute='_compute_td_category_summary',
    )
    td_has_category = fields.Boolean(
        string='Has Category',
        compute='_compute_td_has_category',
        store=True,
    )

    # --- Delivery block ---
    td_delivery_info = fields.Text(string='Delivery Information', tracking=True)

    # --- Installation block ---
    td_installation_info = fields.Text(string='Installation Information', tracking=True)

    # --- Repair / technical maintenance block ---
    td_repair_order_id = fields.Many2one(
        comodel_name='repair.order',
        string='Repair Order',
        tracking=True,
        help='Repair order the spare parts of the "Replacement" table are '
             'taken from. Defaults to the last repair opened on the ticket.',
    )
    td_repair_warranty_type = fields.Selection(
        selection=WARRANTY_SELECTION,
        string='Repair: Warranty Type',
        tracking=True,
    )
    td_repair_works = fields.Text(string='Repair: Works Performed', tracking=True)
    td_repair_comments = fields.Text(string='Repair: Comments / Results', tracking=True)

    # --- Maintenance / setup block ---
    td_maintenance_warranty_type = fields.Selection(
        selection=WARRANTY_SELECTION,
        string='Maintenance: Warranty Type',
        tracking=True,
    )
    td_maintenance_description = fields.Text(string='Maintenance: Description', tracking=True)
    td_maintenance_works = fields.Text(string='Maintenance: Works Performed', tracking=True)
    td_maintenance_comments = fields.Text(string='Maintenance: Comments / Results', tracking=True)

    # --- Demonstration / consulting block ---
    td_demonstration_warranty_type = fields.Selection(
        selection=WARRANTY_SELECTION,
        string='Demonstration: Warranty Type',
        tracking=True,
    )
    td_demonstration_description = fields.Text(string='Demonstration: Description', tracking=True)
    td_demonstration_works = fields.Text(string='Demonstration: Works Performed', tracking=True)
    td_demonstration_comments = fields.Text(string='Demonstration: Comments / Results', tracking=True)

    # --- Equipment inspection / removal for repair block ---
    td_inspection_warranty_type = fields.Selection(
        selection=WARRANTY_SELECTION,
        string='Inspection: Warranty Type',
        tracking=True,
    )
    td_inspection_defect = fields.Text(string='Inspection: Defect Description', tracking=True)
    td_inspection_works = fields.Text(string='Inspection: Works Performed', tracking=True)
    td_inspection_comments = fields.Text(string='Inspection: Comments / Results', tracking=True)
    td_inspection_damage = fields.Selection(
        selection=[('none', 'None'), ('present', 'Present')],
        string='Visible Damage on Acceptance',
        default='none',
        tracking=True,
    )
    td_inspection_damage_description = fields.Text(
        string='Visible Damage Description',
        tracking=True,
    )
    td_inspection_warranty_card_marked = fields.Boolean(
        string='Removal Noted in the Warranty Card',
        tracking=True,
    )
    td_inspection_equipment_set = fields.Text(
        string='Accepted for Repair Together With (Set)',
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('sequence_number')
    def _compute_name(self):
        for record in self:
            record.name = _('Service Report %s', record.sequence_number or 1)

    @api.depends(*SERVICE_CATEGORIES)
    def _compute_td_category_summary(self):
        for record in self:
            record.td_category_summary = ', '.join(
                record._fields[fname]._description_string(self.env)
                for fname in SERVICE_CATEGORIES if record[fname]
            )

    @api.depends(*SERVICE_CATEGORIES)
    def _compute_td_has_category(self):
        for record in self:
            record.td_has_category = any(record[fname] for fname in SERVICE_CATEGORIES)

    @api.depends('td_lot_id')
    def _compute_td_agreement_domain(self):
        """Narrow the selectable agreements down to the ones linked to the
        chosen piece of equipment (section 4 of the specification)."""
        for record in self:
            if record.td_lot_id:
                record.td_agreement_domain = [('td_lot_ids', 'in', record.td_lot_id.ids)]
            else:
                record.td_agreement_domain = []

    @api.depends(
        'td_date_report',
        'td_lot_id',
        'td_lot_id.td_warranty_ids.status',
        'td_lot_id.td_warranty_ids.warranty_type',
        'td_lot_id.td_warranty_ids.date_start',
        'td_lot_id.td_warranty_ids.date_end',
    )
    def _compute_td_warranty_suggestion(self):
        """Propose Warranty / Non-warranty from the warranty table of the serial
        number and expose the reference end dates for the printed form."""
        for record in self:
            record.td_warranty_suggestion = False
            record.td_warranty_date_end_manufacturer = False
            record.td_warranty_date_end_company = False
            if not record.td_lot_id:
                continue

            date_report = record.td_date_report or fields.Date.context_today(record)
            warranties = record.td_lot_id.td_warranty_ids.filtered(
                lambda w: w.status != 'draft'
            )
            if not warranties:
                continue

            manufacturer_dates = [
                w.date_end for w in warranties
                if w.warranty_type == 'manufacturer' and w.date_end
            ]
            company_dates = [
                w.date_end for w in warranties
                if w.warranty_type == 'extended' and w.date_end
            ]
            record.td_warranty_date_end_manufacturer = max(manufacturer_dates, default=False)
            record.td_warranty_date_end_company = max(company_dates, default=False)

            covered = warranties.filtered(
                lambda w: w.date_start and w.date_end
                and w.date_start <= date_report <= w.date_end
            )
            record.td_warranty_suggestion = 'warranty' if covered else 'non_warranty'

    # ------------------------------------------------------------------
    # Onchange — the system only PROPOSES the warranty state (section 5)
    # ------------------------------------------------------------------
    @api.onchange('td_lot_id')
    def _onchange_td_lot_id(self):
        """Another device means another set of agreements and a fresh warranty
        proposal: drop the agreements that do not belong to it and re-propose
        the warranty state of every active block from scratch.

        Both onchange methods react to ``td_lot_id``; Odoo calls them in
        alphabetical order, so this one runs last and has the final say.
        """
        for record in self:
            record.td_agreement_ids = record.td_agreement_ids.filtered(
                lambda a: record.td_lot_id and record.td_lot_id in a.td_lot_ids
            )
            for field_name, checkbox_name in WARRANTY_BLOCKS:
                record[field_name] = (
                    record.td_warranty_suggestion if record[checkbox_name] else False
                )

    @api.onchange('td_date_report', 'td_is_repair', 'td_is_maintenance',
                  'td_is_demonstration', 'td_is_inspection')
    def _onchange_propose_warranty_type(self):
        """Fill an empty block with the value suggested by the warranty table.

        A value the engineer already chose is never overwritten: responsibility
        for the final answer stays with the engineer.
        """
        for record in self:
            for field_name, checkbox_name in WARRANTY_BLOCKS:
                if not record[checkbox_name]:
                    record[field_name] = False
                elif not record[field_name]:
                    record[field_name] = record.td_warranty_suggestion

    def action_apply_warranty_suggestion(self):
        """Re-apply the value proposed by the system to every active block."""
        for record in self:
            values = {
                field_name: record.td_warranty_suggestion
                for field_name, checkbox_name in WARRANTY_BLOCKS
                if record[checkbox_name]
            }
            if values:
                record.write(values)
        return True

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model
    def _next_sequence_number(self, ticket):
        last = self.search(
            [('ticket_id', '=', ticket.id)], order='sequence_number desc', limit=1)
        return (last.sequence_number or 0) + 1

    @api.model
    def _default_repair_order(self, ticket):
        """The repair the engineer is most likely reporting on: the last one
        opened on the ticket. Several repairs per ticket are normal, so the
        engineer can always pick another one."""
        return self.env['repair.order'].search(
            [('ticket_id', '=', ticket.id)], order='id desc', limit=1)

    @api.model
    def _format_partner_address(self, partner):
        """The postal address of the partner on a single line."""
        if not partner:
            return ''
        return ', '.join(
            line.strip()
            for line in partner._display_address(without_company=True).splitlines()
            if line.strip()
        )

    @api.model
    def default_get(self, fields_list):
        """Prefill the wizard from the ticket before anything is saved."""
        values = super().default_get(fields_list)
        ticket_id = values.get('ticket_id') or self.env.context.get('default_ticket_id')
        ticket = self.env['helpdesk.ticket'].browse(ticket_id) if ticket_id else False
        if not ticket or not ticket.exists():
            return values
        values.setdefault('ticket_id', ticket.id)
        if 'sequence_number' in fields_list:
            values['sequence_number'] = self._next_sequence_number(ticket)
        if 'td_lot_id' in fields_list and ticket.td_serial_number_id:
            values.setdefault('td_lot_id', ticket.td_serial_number_id.lot_id.id)
        if 'td_agreement_ids' in fields_list and ticket.td_agreement_ids:
            values.setdefault('td_agreement_ids', [(6, 0, ticket.td_agreement_ids.ids)])
        if 'td_engineer_id' in fields_list and ticket.user_id:
            values.setdefault('td_engineer_id', ticket.user_id.id)
        if 'td_equipment_address' in fields_list and ticket.partner_id:
            values.setdefault(
                'td_equipment_address', self._format_partner_address(ticket.partner_id))
        if 'td_repair_order_id' in fields_list:
            repair = self._default_repair_order(ticket)
            if repair:
                values.setdefault('td_repair_order_id', repair.id)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        counters = {}
        for vals in vals_list:
            ticket_id = vals.get('ticket_id') or self.env.context.get('default_ticket_id')
            ticket = self.env['helpdesk.ticket'].browse(ticket_id) if ticket_id else False
            if not ticket or not ticket.exists():
                continue
            vals.setdefault('ticket_id', ticket.id)
            # Always allocated at insert time: a value carried over from
            # default_get may be stale if another report was created meanwhile.
            if ticket.id not in counters:
                counters[ticket.id] = self._next_sequence_number(ticket) - 1
            counters[ticket.id] += 1
            vals['sequence_number'] = counters[ticket.id]
            if 'td_lot_id' not in vals and ticket.td_serial_number_id:
                vals['td_lot_id'] = ticket.td_serial_number_id.lot_id.id
            if 'td_agreement_ids' not in vals and ticket.td_agreement_ids:
                vals['td_agreement_ids'] = [(6, 0, ticket.td_agreement_ids.ids)]
            if 'td_engineer_id' not in vals and ticket.user_id:
                vals['td_engineer_id'] = ticket.user_id.id
            if 'td_equipment_address' not in vals and ticket.partner_id:
                vals['td_equipment_address'] = self._format_partner_address(
                    ticket.partner_id)
            if 'td_repair_order_id' not in vals:
                repair = self._default_repair_order(ticket)
                if repair:
                    vals['td_repair_order_id'] = repair.id
        records = super().create(vals_list)
        records._post_ticket_message(created=True)
        return records

    def write(self, vals):
        if self.env.context.get('td_skip_ticket_log') or not (
                set(vals) & set(self._tracked_fields())):
            return super().write(vals)
        previous = self._tracked_field_snapshot()
        result = super().write(vals)
        self._post_ticket_message(previous=previous)
        return result

    # ------------------------------------------------------------------
    # Chatter of the ticket (section 2 of the specification)
    # ------------------------------------------------------------------
    @api.model
    def _tracked_fields(self):
        return [
            fname for fname, field in self._fields.items()
            if getattr(field, 'tracking', False)
        ]

    def _tracked_field_snapshot(self):
        return {
            record.id: {
                fname: record._format_tracked_value(fname)
                for fname in self._tracked_fields()
            }
            for record in self
        }

    def _format_tracked_value(self, fname):
        field = self._fields[fname]
        value = self[fname]
        if field.type == 'many2one':
            return value.display_name or ''
        if field.type in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name'))
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, '')
        if field.type == 'boolean':
            return _('Yes') if value else _('No')
        if value is False or value is None:
            return ''
        return str(value)

    def _post_ticket_message(self, previous=None, created=False):
        """Mirror the changes made in the tab / wizard into the ticket chatter."""
        for record in self:
            ticket = record.ticket_id
            if not ticket:
                continue
            if created:
                ticket.message_post(body=_('Service report created: %s', record.name))
                continue
            before = (previous or {}).get(record.id, {})
            changes = []
            for fname in record._tracked_fields():
                old = before.get(fname)
                new = record._format_tracked_value(fname)
                if old is None or old == new:
                    continue
                label = record._fields[fname]._description_string(self.env)
                changes.append(Markup('<li><b>%s</b>: %s &#8594; %s</li>') % (
                    label, old or _('(empty)'), new or _('(empty)')))
            if changes:
                ticket.message_post(body=Markup('%s<ul>%s</ul>') % (
                    _('%s updated:', record.name),
                    Markup('').join(changes),
                ))

    # ------------------------------------------------------------------
    # Printed form
    # ------------------------------------------------------------------
    def td_format_date(self, value):
        """Date with the month spelled out, the way the paper form reads it."""
        return format_date(self.env, value, date_format='d MMMM y') if value else ''

    def td_get_agreement_lines(self):
        """Number and date of every agreement, for the "to agreement No." line."""
        self.ensure_one()
        return [{
            'number': agreement.agreement_number or agreement.number or '',
            'date': self.td_format_date(agreement.signing_date or agreement.start_date),
        } for agreement in self.td_agreement_ids]

    def td_get_replacement_lines(self):
        """Spare parts of the linked repair order for the "Replacement" table.

        The parts are the "add" moves of the repair order, and the amounts
        come from the quotation line each of those moves generated: the
        repair is what puts a price on a spare part, the service report only
        reports it.
        """
        self.ensure_one()
        moves = self.td_repair_order_id.move_ids.filtered(
            lambda m: m.repair_line_type == 'add' and m.state != 'cancel')
        return [{
            'name': move.product_id.display_name,
            'quantity': (move.sale_line_id.product_uom_qty if move.sale_line_id
                         else move.quantity or move.product_uom_qty),
            'serial': ', '.join(move.move_line_ids.lot_id.mapped('name')),
            'price_subtotal': move.sale_line_id.price_subtotal or 0.0,
            'price_tax': move.sale_line_id.price_tax or 0.0,
            'price_total': move.sale_line_id.price_total or 0.0,
        } for move in moves]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_open_wizard(self):
        """Open this report in the wizard-like dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'td.service.report',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'td_medicus_service_report.view_td_service_report_form').id,
            'res_id': self.id,
            'target': 'new',
        }

    def action_print_report(self):
        """Generate (print) the document from the wizard."""
        self.ensure_one()
        if not self.td_has_category:
            raise UserError(_(
                'Select at least one service category before generating the report.'))
        return self.env.ref(
            'td_medicus_service_report.action_report_td_service_report'
        ).report_action(self)
