# -*- coding: utf-8 -*-

import logging
import hashlib
import requests
import datetime
from odoo import api, fields, models, _
from werkzeug import urls
from odoo.exceptions import ValidationError
import pprint

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('duitku', 'Duitku Payment')], ondelete={'duitku': 'set default'})
    duitku_merchant_code = fields.Char(
        string='Merchant Code', required_if_provider='duitku', groups='base.group_system', help='Duitku Merchant Code')
    duitku_api_key = fields.Char(
        string='Duitku API Key', required_if_provider='duitku', groups='base.group_system', help='Duitku API Key')
    duitku_expiry = fields.Integer(default=1440)  # Default value in minutes


    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'duitku').update({
            'is_published': True,
        })

    # === CONSTRAINT METHODS ===#


    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'duitku':
            return default_codes
        return 'duitku'

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist Mollie providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name != 'IDR':
            providers = providers.filtered(lambda p: p.code != 'duitku')

        return providers

    def _duitku_get_api_url(self):
        """ Return the API URL according to the state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()
        if self.state == 'enabled':
            return 'https://api-prod.duitku.com/api/merchant/'
        else:
            return 'https://api-sandbox.duitku.com/api/merchant/'

    def _duitku_generate_signature(self, values):
        """ Generate the signature for the provided data according to the Duitku documentation.

        :param dict values: The values used to generate the signature

        :return: The signature
        :rtype: str
        """
        present_date = datetime.datetime.now()
        timestamp = str(round(datetime.datetime.timestamp(present_date) * 1000))
        merchant_code = values['merchantCode']
        api_key = values['apiKey']
        encrytion_text = (merchant_code + str(timestamp) + api_key)
        return hashlib.sha256(encrytion_text.encode('utf-8')).hexdigest() , timestamp

    def _duitku_make_request(self, endpoint, data=None,headers=None, method='POST'):
        """ Make a request at duitku endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request
        :param dict data: The payload of the request
        :param dict headers: The headers of the request
        :param str method: The HTTP method of the request
        :return The JSON-formatted content of the response
        :rtype: dict
        :raise: ValidationError if an HTTP error occurs
        """

        endpoint = endpoint.strip("/")
        url = urls.url_join(self._duitku_get_api_url(), endpoint)
        try:
            
            if endpoint == 'transactionStatus':
                req = requests.post(url=url, json=data, headers=headers, allow_redirects=False)
                response = req.json()
                _logger.info('Duitku create response for transactionStatus %s', pprint.pformat(response))
                if response['statusCode'] != '00':
                    raise ValidationError(_("Payment has not been successfully paid but a callback is triggered."
                                            "Could be because someone is trying to cheat the system."))
            if endpoint == 'createInvoice':
                req = requests.post(url=url, data=data, headers=headers, allow_redirects=False)
                response = req.json()
                _logger.info('Duitku create response for CreateInvoice %s', pprint.pformat(response))
                if req.status_code != 200:
                    _logger.info('There was an error when creating a transasction. The data sent was %s',
                                 pprint.pformat(req))
                    _logger.info('Duitku create transaction response %s', pprint.pformat(response))
                    raise ValidationError(_("%s") % response)
        except requests.exceptions.RequestException:
            _logger.exception("unable to communicate with Duitku: %s", url)
            raise ValidationError("Dutiku: " + _("Could not establish the connection to the API."))
        except requests.exceptions.ConnectionError:
            _logger.exception("unable to reach endpoint at %s", url)
            raise ValidationError("Dutiku: " + _("Could not establish the connection to the API."))
        except requests.exceptions.HTTPError as error:
            _logger.exception(
                "invalid API request at %s with data %s: %s", url, data, error.response.text
            )
            raise ValidationError("Dutiku: " + _("The communication with the API failed."))
        return response
