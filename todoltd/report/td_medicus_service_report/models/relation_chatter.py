# -*- coding: utf-8 -*-
"""Log actual changes to the many-to-many fields supplied by this module."""
from markupsafe import Markup

from odoo import _


def _relation_state(record, field_name):
    related = record[field_name]
    return frozenset(related.ids), ', '.join(sorted(related.mapped('display_name')))


def relation_snapshots(records, field_name):
    return {
        record.id: (*_relation_state(record, field_name), record[field_name])
        for record in records
    }


def post_relation_changes(records, field_name, previous=None, inverse_field_name=None):
    """Post on the edited card and on each affected inverse card."""
    previous = previous or {}
    for record in records:
        old_ids, old_names, old_related = previous.get(
            record.id, (frozenset(), '', ()))
        new_ids, new_names = _relation_state(record, field_name)
        if old_ids == new_ids:
            continue
        label = record._fields[field_name]._description_string(record.env)
        record.message_post(body=Markup('<b>%s</b>: %s &#8594; %s') % (
            label, old_names or _('(empty)'), new_names or _('(empty)'),
        ), subtype_xmlid='mail.mt_note')
        if inverse_field_name:
            for related in old_related:
                if related.id in new_ids:
                    continue
                inverse_label = related._fields[inverse_field_name]._description_string(
                    related.env)
                related.message_post(body=Markup('<b>%s</b>: %s %s') % (
                    inverse_label, _('Removed'), record.display_name,
                ), subtype_xmlid='mail.mt_note')
            for related in record[field_name]:
                if related.id in old_ids:
                    continue
                inverse_label = related._fields[inverse_field_name]._description_string(
                    related.env)
                related.message_post(body=Markup('<b>%s</b>: %s %s') % (
                    inverse_label, _('Added'), record.display_name,
                ), subtype_xmlid='mail.mt_note')
