# pylint:disable = W8120
import json
import base64
import logging
import requests
from html2text import html2text
from odoo import exceptions, _

from odoo.http import request

_logger = logging.getLogger(__name__)


VCHASNO_OPTIONAL_PARAMS = (
    'amount',
    'category',
    'date_document',
    'doc_number',
    'expected_owner_signatures',
    'expected_recipient_signatures',
    'first_sign_by',
    'signer_emails',
    'signer_roles',
    'is_internal',
    'is_multilateral',
    'is_parallel',
    'is_required_review',
    'is_versioned',
    'parallel_review',
    'parallel_signing',
    'parent_id',
    'recipient_edrpou',
    'recipient_emails',
    'reviewers_ids',
    'share_to',
    'show_recipients'
    'tags',
    'title',
    'template_id',
)


class VchasnoApi:
    base_url = 'https://vchasno.ua'
    api_version = '/api/v2'
    api_key = ''
    is_log_enabled = False

    def __init__(self, api_key='', is_log_enabled=False):
        self.api_key = api_key
        self.is_log_enabled = is_log_enabled

    def get_url(self, url=''):
        def urljoin(*args):
            return '/'.join(map(lambda x: str(x).strip('/'), args))
        return urljoin(self.base_url, self.api_version, url)

    @staticmethod
    def headers():
        return {'Content-Type': 'application/json', }

    def request(self, method, url, headers, data=None, params=None, file=None):
        if self.is_log_enabled:
            try:
                log = request.env['kw.vchasno.log'].sudo().create({
                    'name': self.get_url(url), 'token': self.api_key,
                    'method': method, 'headers': headers,
                    'json': json.dumps(data, indent=2, ensure_ascii=False),
                    'params': params,
                })
            except Exception as e:
                _logger.debug(e)
                # Don`t work in cron
                self.is_log_enabled = False
            else:
                # pylint: disable=E8102
                request._cr.commit()
        response = requests.request(
            method=method,
            url=self.get_url(url),
            json=data,
            params=params,
            headers=headers,
            files=file,
            timeout=100,
        )
        if 200 <= response.status_code < 300:
            if response.headers['Content-Type'] != \
                    'application/json; charset=utf-8':
                res = response.content
                if self.is_log_enabled:
                    log.write({
                        'code': response.status_code,
                        'is_download': True,
                    })
                return res
            res = response.json()
            if self.is_log_enabled:
                log.write({
                    'code': response.status_code,
                    'response': json.dumps(res, indent=2, ensure_ascii=False),
                })
            return res
        if self.is_log_enabled:
            log.write({
                'code': response.status_code,
                'error': html2text(response.text).split('\n')[0],
                'response':
                json.dumps(response.json(), indent=2, ensure_ascii=False)
            })
            # pylint: disable=E8102
            request._cr.commit()
        raise exceptions.ValidationError(
            _('Vchasno error:\n{}').format(
                json.dumps(response.json(), indent=4, ensure_ascii=False)
            )
        )

    def get(self, url, params=None, headers=None):
        if not params:
            params = {}
        if not headers:
            headers = self.headers()
        headers.update({'Authorization': self.api_key if self.api_key else ''})
        return self.request('get', url=url, params=params, headers=headers)

    def post(self, url, data=None, headers=None, file=None, params=None):
        if not data:
            data = {}
        if not headers:
            headers = self.headers()
        if file:
            headers = {}
        headers.update({'Authorization': self.api_key if self.api_key else ''})
        return self.request('post', url=url, data=data, headers=headers,
                            file=file, params=params,)

    def get_incoming_documents(self, params=None):
        url = '/incoming-documents'
        return self.get(url=url, params=params)

    def get_documents(self, has_changed=0, params=None):
        url = '/documents?has_changed={}'.format(has_changed)
        return self.get(url=url, params=params)

    def download_incoming_documents(self, document_id=0):
        url = '/documents/{}/original'.format(document_id)
        return self.get(url)

    def download_incoming_archive(self, document_id=0):
        url = '/documents/{}/archive'.format(document_id)
        return self.get(url)

    def post_document(self, file, filename, title, **kwargs):
        url = '/documents'
        params = {'title': title}
        for key in kwargs:
            if key in VCHASNO_OPTIONAL_PARAMS:
                params.update({key: kwargs[key]})
            else:
                _logger.warning(
                    f'\nVchasnoApi.\npost_document:Unknown param {key}',
                )
        if file and filename:
            vals = {'files': (filename, base64.b64decode(file))}
            return self.post(url=url, file=vals, params=params)
        return False

    def send_document_to_recipient(self, vchasno_doc_id, vchasno_ref):
        send_res = requests.request(
            method='post',
            url=self.get_url(f'/documents/{vchasno_ref}/send'),
            headers={'Authorization': self.api_key if self.api_key else ''},
            timeout=100,
        )
        if send_res.status_code != 200:
            _logger.error(
                f'VchasnoApi.\nsend_document_to_recipient: '
                f'Error {send_res.text} sending document'
            )
        upd_res = requests.request(
            method='get',
            url=self.get_url(f'/documents?ids={vchasno_ref}'),
            headers={'Authorization': self.api_key if self.api_key else ''},
            timeout=100,
        )
        if 200 <= upd_res.status_code < 300 and upd_res.json()['documents']:
            vchasno_doc_id.update({
                'state': str(upd_res.json()['documents'][0]['status']),
            })
