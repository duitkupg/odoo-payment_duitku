# -*- coding: utf-8 -*-

import logging
import pprint
import werkzeug

from werkzeug import urls
from odoo import http
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.http import request
from odoo.addons.payment.controllers.portal import PaymentProcessing

_logger = logging.getLogger(__name__)


class DuitkuController(http.Controller):
    @http.route('/payment/duitku/call/', type='http', methods=['POST'], auth='public', csrf=False)
    def duitku_call(self, **post):
        """ Duitku Call. """
        _logger.info('Beginning Call form_feedback with post data %s', pprint.pformat(post))  # debug
        try:
            payment_url = post.get('payment_url')
            request.env['payment.transaction'].sudo().form_feedback(post, 'duitku')
            return werkzeug.utils.redirect(payment_url)
        except ValidationError:
            _logger.exception('Unable to request a transaction with duitku')
        return werkzeug.utils.redirect('/payment/process')

    @http.route('/payment/duitku/callback/', type='http', auth='public', methods=['POST'], csrf=False)
    def duitku_callback(self, **post):
        """ Duitku Callback """
        _logger.info('Received Callback form_feedback with post data %s', pprint.pformat(post))  # debug
        request.env['payment.transaction'].sudo().form_feedback(post, 'duitku')
        return ''

    @http.route('/payment/duitku/return/', type='http', auth="public", methods=['GET'], csrf=False)
    def duitku_return(self, **post):
        """ Duitku Return """
        _logger.info('Duitku customer has returned with post data %s', pprint.pformat(post))  # debug
        return werkzeug.utils.redirect('/payment/process')
