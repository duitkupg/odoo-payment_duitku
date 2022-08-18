# -*- coding: utf-8 -*-

import json
import logging
import hashlib
import pprint
import requests
import datetime
from dateutil import relativedelta
from odoo import api, fields, models, _
from werkzeug import urls
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.exceptions import ValidationError as ValEr
from odoo.http import request
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class DuitkuAPI:
    def duitku_get_call_url(self, environment):
        if environment == 'production':
            return 'https://api-prod.duitku.com/api/merchant/createInvoice'
        else:
            return 'https://api-sandbox.duitku.com/api/merchant/createInvoice'

    def duitku_get_check_transaction_url(self, environment):
        if environment == 'production':
            return 'https://api-prod.duitku.com/api/merchant/transactionStatus'
        else:
            return 'https://api-sandbox.duitku.com/api/merchant/transactionStatus'

    def duitku_create_transaction(self, values):
        reference = values['merchantOrderId']
        tx = None
        if reference:
            tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        if not tx:
            # we have seemingly received a notification for a payment that did not come from
            # odoo. Send warning and stop.
            _logger.warning('received notification for unknown payment reference')
            return False
        params = {
            'paymentAmount': round(float(values['amount'])),
            'merchantOrderId': values['merchantOrderId'],
            'productDetails': values['productDetails'],
            'additionalParam': '',  # Empty for now
            'merchantUserInfo': values['merchantUserInfo'],
            'customerVaName': values['customerVaName'],
            'email': values['email'],
            'phoneNumber': values['phoneNumber'],
            'itemDetails': [values['itemDetails']],
            'customerDetail': values['customerDetail'],
            'callbackUrl': values['callbackUrl'],
            'returnUrl': values['returnUrl'],
            'expiryPeriod': int(values['expiryPeriod']),
        }
        params_string = json.dumps(params)

        present_date = datetime.datetime.now()
        timestamp = str(round(datetime.datetime.timestamp(present_date) * 1000))
        merchant_code = values['merchantCode']
        api_key = values['apiKey']
        encrytion_text = (merchant_code + str(timestamp) + api_key)
        header = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Content-Length': str(len(str(params))),
            'x-duitku-signature': hashlib.sha256(encrytion_text.encode('utf-8')).hexdigest(),
            'x-duitku-timestamp': timestamp,
            'x-duitku-merchantcode': merchant_code
        }
        environment = values['environment']
        callurl = self.duitku_get_call_url(environment)
        req = requests.post(url=callurl, data=params_string, headers=header, allow_redirects=False)
        return self.process_request(req, tx)

    def process_request(self, req, tx):
        response = req.json()
        if req.status_code != 200:
            _logger.info('There was an error when creating a transasction. The data sent was %s', pprint.pformat(req))
            _logger.info('Duitku create transaction response %s', pprint.pformat(response))
            tx._set_transaction_error(
                'There was an error when requesting a transaction. Please contact your administrator.')
            raise ValEr(_("%s") % response)
        else:
            return response

    def duitku_check_transaction(self, values, api_key, environment):
        merchant_code = values.get('merchantCode')
        merchant_order_id = values.get('merchantOrderId')
        hashtext = merchant_code + merchant_order_id + api_key
        signature = hashlib.md5(hashtext.encode('utf-8')).hexdigest()
        params = {
            'merchantCode': merchant_code,
            'merchantOrderId': merchant_order_id,
            'signature': signature,
        }
        params_string = json.dumps(params)
        header = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Content-Length': str(len(str(params))),
        }
        check_url = self.duitku_get_check_transaction_url(environment)
        req = requests.post(url=check_url, data=params_string, headers=header, allow_redirects=False)
        return self.send_check_transaction_request(req)

    def send_check_transaction_request(self, req):
        req.raise_for_status()  # Stops all non successful request
        response = req.json()
        _logger.info('Duitku check transaction response %s', pprint.pformat(response))
        if response['statusCode'] != '00':
            raise ValEr(_("Payment has not been successfully paid but a callback is triggered."
                          "Could be because someone is trying to cheat the system."))
        return response


class DuitkuAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    # For testing purposes, this seems to bypass the 'read-only' property
    # Not elegant, but it does the job and helps with testing as well.
    duitku_api = {
        'api': DuitkuAPI()
    }
    provider = fields.Selection(selection_add=[
        ('duitku', 'Duitku Payment')
    ], ondelete={'duitku': 'set default'})

    duitku_merchant_code = fields.Char('Merchant Code', required_if_provider='duitku', groups='base.group_user',
                                       default='Insert Merchant Code here')
    duitku_api_key = fields.Char('Duitku API Key', required_if_provider='duitku', groups='base.group_user',
                                 default='Insert API Key')
    duitku_environment = fields.Selection(selection=[
        ('sandbox', 'Sandbox Environment'),
        ('production', 'Production Environment')
    ], ondelete={'sandbox': 'set default'})
    duitku_expiry = fields.Integer(default=1440)  # Default value in minutes

    # Only used for testing purposes
    def _set_duitku_api(self, new_api=DuitkuAPI()):
        self.duitku_api['api'] = new_api

    def _get_callback_url(self):
        return '/payment/duitku/callback/'

    def _get_return_url(self):
        return '/payment/duitku/return/'

    def duitku_get_form_action_url(self):
        self.ensure_one()
        return self._get_duitku_urls()

    def duitku_prepare_payment_values(self, values):
        address = {
            'firstName': values['billing_partner_first_name'],
            'lastName': values['billing_partner_last_name'],
            'address': values['billing_partner_address'],
            'city': values['billing_partner_city'],
            'postalCode': values['billing_partner_zip'],
            'phone': values['billing_partner_phone'],
            'countryCode': values['billing_partner_country'].code,
        }

        customer_detail = {
            'firstName': values['billing_partner_first_name'],
            'lastName': values['billing_partner_last_name'],
            'email': values['billing_partner_email'],
            'phoneNumber': values['billing_partner_phone'],
            'billingAddress': address,
            'shippingAddress': address,
        }

        item_details = {
            'name': '%s: %s' % (self.company_id.name, values['reference']),
            'price': int(values['amount']),
            'quantity': 1,
        }
        return item_details, customer_detail

    def duitku_form_generate_values(self, values):
        base_url = self.get_base_url()
        duitku_tx_values = dict(values)
        if values['currency'].name != 'IDR':
            raise ValEr(_("Duitku can only be used with IDR"))

        item_details, customer_detail = self.duitku_prepare_payment_values(values)
        values['itemDetails'] = item_details
        values['customerDetail'] = customer_detail
        values['amount'] = values['amount']
        values['merchantOrderId'] = values['reference']
        values['productDetails'] = '%s: %s' % (self.company_id.name, values['reference'])
        values['customerVaName'] = values['billing_partner_first_name']
        values['merchantUserInfo'] = values['billing_partner_first_name']
        values['email'] = values['billing_partner_email']
        values['itemDetails'] = item_details
        values['customerDetail'] = customer_detail
        values['callbackUrl'] = urls.url_join(base_url, self._get_callback_url())
        values['returnUrl'] = urls.url_join(base_url, self._get_return_url())
        values['expiryPeriod'] = self.duitku_expiry
        values['phoneNumber'] = values['billing_partner_phone']
        values['merchantCode'] = self.duitku_merchant_code
        values['apiKey'] = self.duitku_api_key
        values['environment'] = self.duitku_environment

        response = self.duitku_api['api'].duitku_create_transaction(values)
        duitku_tx_values.update({
            'payment_url': response['paymentUrl'],
            'merchantOrderId': values['merchantOrderId'],
            'expiryPeriod': self.duitku_expiry,
            'reference': response['reference']
        })
        return duitku_tx_values

    @api.model
    def _get_duitku_urls(self):
        """ Duitku URLS """
        base_url = self.get_base_url()
        return urls.url_join(base_url, '/payment/duitku/call/')


class TxDuitku(models.Model):
    _inherit = 'payment.transaction'
    duitku_reference = fields.Char('Duitku reference')
    duitku_order_id = fields.Char('Duitku Merchant Order ID')

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def _duitku_form_get_tx_from_data(self, data):
        merchant_order_id = data.get('merchantOrderId')
        if not merchant_order_id:
            error_msg = _('Duitku: received data with missing Merchant Order Id (%s)') % (merchant_order_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        txs = self.env['payment.transaction'].search([('reference', '=', merchant_order_id)])
        if not txs or len(txs) > 1:
            error_msg = 'Duitku: received data for reference %s' % (merchant_order_id)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    def _duitku_form_get_invalid_parameters(self, data):
        invalid_parameters = []

        # If it is just requesting transaction, no need to check
        # for signature validity.
        if data.get('callMode'):
            return invalid_parameters

        if not data.get('merchantCode'):
            invalid_parameters.append(('merchantCode', 'merchantCode not present', 'merchantCode Parameters received'))

        if not data.get('signature'):
            invalid_parameters.append(('signature', 'signature not present', 'signature Parameters received'))

        # Since during callback we will not be receiving apiKey, then we should just pass it as a additionalParam
        params = self.acquirer_id.duitku_merchant_code + str(data.get('amount')) + data.get(
            'merchantOrderId') + self.acquirer_id.duitku_api_key
        calculated_signature = hashlib.md5(params.encode('utf-8')).hexdigest()
        if data.get('signature') != calculated_signature:
            invalid_parameters.append(('signature', calculated_signature, data.get('signature')))

        if int(data.get('amount')) != int(self.amount):
            invalid_parameters.append(('amount', data.get('amount'), int(self.amount)))

        return invalid_parameters

    def _duitku_form_validate(self, data):
        if not data.get('callMode'):
            status = data.get('resultCode')
        else:
            status = '01'

        res = {
            'acquirer_reference': data.get('merchantOrderId'),
            'duitku_reference': data.get('reference'),
            'duitku_order_id': data.get('merchantOrderId')
        }

        if status == '00':
            date = fields.Datetime.now()
            res.update(date=date)
            self.acquirer_id.duitku_api['api'].duitku_check_transaction(data, self.acquirer_id.duitku_api_key,
                                                                        self.acquirer_id.duitku_environment)
            self._set_transaction_done()
            self._post_process_after_done()  # This might cause an error in a test. But this is the only way for now.
            _logger.info('Validated Duitku payment for tx %s: set as done' % self.reference)
            self.write(res)
            return True
        else:
            date = fields.Datetime.now()
            res.update(date=date)
            res.update(state_message=data.get('resultCode', ''))
            self._set_transaction_pending()
            _logger.info('Received notification for Duitku payment %s: is now awaiting payment' % self.reference)
            return self.write(res)
