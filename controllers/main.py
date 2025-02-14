# -*- coding: utf-8 -*-

import logging
import pprint
from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

class DuitkuController(http.Controller):

    _return_url = '/payment/duitku/return'
    _callback_url = '/payment/duitku/callback'

    @http.route(_return_url, type='http', auth="public", methods=['GET'], csrf=False)
    def duitku_return(self, **data):
        """ Process the notification data sent by Duitku after redirection from checkout.

        :param dict data: The notification data.
        """
        _logger.info('Duitku customer has returned with post data %s', pprint.pformat(data))
        request.env['payment.transaction'].sudo()._handle_notification_data('duitku', data)# debug
        # Redirect the user to the status page.
        return request.redirect('/payment/status')


    @http.route(_callback_url, type='http', auth='public', methods=['POST'], csrf=False)
    def duitku_callback(self, **data):
        _logger.info("Handling redirection from Duitku with data:\n%s", pprint.pformat(data))
        request.env['payment.transaction'].sudo()._handle_notification_data('duitku', data)# debug
        return request.redirect('/payment/status')