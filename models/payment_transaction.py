# -*- coding: utf-8 -*-

import json
import logging
import hashlib
import pprint
from odoo import api, fields, models, _
from werkzeug import urls
from odoo.exceptions import ValidationError

from odoo.addons.payment_duitku.controllers.main import DuitkuController

_logger = logging.getLogger(__name__)

def _partner_format_address(address1=False, address2=False):
    return ' '.join((address1 or '', address2 or '')).strip()

def _partner_split_name(partner_name):
    return [' '.join(partner_name.split()[:-1]), ' '.join(partner_name.split()[-1:])]


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    duitku_reference = fields.Char('Duitku reference')
    duitku_order_id = fields.Char('Duitku Merchant Order ID')

    #=== BUSINESS METHODS ===#
    def _duitku_prepare_payment_request_payload(self, values):
        create_payment_values = {
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
        duitku_signature, timestamp = self.provider_id._duitku_generate_signature(values)

        headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Content-Length': str(len(str(create_payment_values))),
                'x-duitku-signature': duitku_signature,
                'x-duitku-timestamp': timestamp,
                'x-duitku-merchantcode': values['merchantCode']
            }

        return create_payment_values,headers
    def duitku_prepare_payment_values(self, values):
        partner_id = values.get('partner_id', [])
        item_details, customer_detail = {}, {}
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            billing_partner = self.env['res.partner'].browse(partner_id)
            values.update({
                'partner': partner,
                'partner_id': partner_id,
                'partner_name': partner.name,
                'partner_lang': partner.lang,
                'partner_email': partner.email,
                'partner_zip': partner.zip,
                'partner_city': partner.city,
                'partner_address': _partner_format_address(partner.street, partner.street2),
                'partner_country_id': partner.country_id.id or self.env.company.country_id.id,
                'partner_country': partner.country_id,
                'partner_phone': partner.phone,
                'partner_state': partner.state_id,
                'billing_partner': billing_partner,
                'billing_partner_id': partner_id,
                'billing_partner_name': billing_partner.name,
                'billing_partner_commercial_company_name': billing_partner.commercial_company_name,
                'billing_partner_lang': billing_partner.lang,
                'billing_partner_email': billing_partner.email,
                'billing_partner_zip': billing_partner.zip,
                'billing_partner_city': billing_partner.city,
                'billing_partner_address': _partner_format_address(billing_partner.street, billing_partner.street2),
                'billing_partner_country_id': billing_partner.country_id.id,
                'billing_partner_country': billing_partner.country_id,
                'billing_partner_phone': billing_partner.phone,
                'billing_partner_state': billing_partner.state_id,
            })
            if values.get('partner_name'):
                values.update({
                    'partner_first_name': _partner_split_name(values.get('partner_name'))[0],
                    'partner_last_name': _partner_split_name(values.get('partner_name'))[1],
                })
            if values.get('billing_partner_name'):
                values.update({
                    'billing_partner_first_name': _partner_split_name(values.get('billing_partner_name'))[0],
                    'billing_partner_last_name': _partner_split_name(values.get('billing_partner_name'))[1],
                })

            # Fix address, country fields
            if not values.get('partner_address'):
                values['address'] = _partner_format_address(values.get('partner_street', ''),
                                                            values.get('partner_street2', ''))

            if not values.get('partner_country') and values.get('partner_country_id'):
                values['country'] = self.env['res.country'].browse(values.get('partner_country_id'))

            if not values.get('billing_partner_address'):
                values['billing_address'] = _partner_format_address(values.get('billing_partner_street', ''),
                                                                    values.get('billing_partner_street2', ''))

            if not values.get('billing_partner_country') and values.get('billing_partner_country_id'):
                values['billing_country'] = self.env['res.country'].browse(values.get('billing_partner_country_id'))

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
        return item_details, customer_detail, values


    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Duitku-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        # print("Processing Values--", processing_values)
        if self.provider_code != 'duitku':
            return res

        base_url = self.provider_id.get_base_url()
        duitku_tx_values = dict()

        item_details, customer_detail, processing_values = self.duitku_prepare_payment_values(processing_values)
        processing_values['itemDetails'] = item_details
        processing_values['customerDetail'] = customer_detail
        processing_values['amount'] = processing_values['amount']
        processing_values['merchantOrderId'] = processing_values['reference']
        processing_values['productDetails'] = '%s: %s' % (self.company_id.name, processing_values['reference'])
        processing_values['customerVaName'] = processing_values['billing_partner_first_name']
        processing_values['merchantUserInfo'] = processing_values['billing_partner_first_name']
        processing_values['email'] = processing_values['billing_partner_email']
        processing_values['callbackUrl'] = urls.url_join(base_url, DuitkuController._callback_url)
        processing_values['returnUrl'] = urls.url_join(base_url, DuitkuController._return_url)
        processing_values['expiryPeriod'] = self.provider_id.duitku_expiry
        processing_values['phoneNumber'] = processing_values['billing_partner_phone']
        processing_values['merchantCode'] = self.provider_id.duitku_merchant_code
        processing_values['apiKey'] = self.provider_id.duitku_api_key

        payload, headers = self._duitku_prepare_payment_request_payload(processing_values)
        _logger.info("sending '/createInvoice' request for link creation:\n%s", pprint.pformat(payload))
        payment_data = self.provider_id._duitku_make_request('/createInvoice',data=json.dumps(payload),headers=headers)
        _logger.info("Received invoice request response:\n%s", pprint.pformat(payment_data))
        # if the merchantOrderId already exists in Duitku and you try to pay again, the createInvoice return
        # ("MerchantOrderId":"Bill already paid. (Parameter \u0027MerchantOrderId\u0027)")
        # So her we check, if he response is string thne
        if isinstance(payment_data, str):
            self._set_error(payment_data)
            raise ValidationError(
                "Duitku: " + _("Create Invoice response %(ref)s.", ref=payment_data)
            )

        self.provider_reference = payment_data.get('reference')

        duitku_tx_values.update({
            'api_url': payment_data.get('paymentUrl'),
            # 'payment_url': payment_data['paymentUrl'],
            'merchantOrderId': processing_values['merchantOrderId'],
            'expiryPeriod': self.provider_id.duitku_expiry,
            'reference': payment_data['reference']
        })
        return duitku_tx_values


#     # --------------------------------------------------
#     # FORM RELATED METHODS
#     # --------------------------------------------------

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on APS data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If inconsistent data are received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'duitku' or len(tx) == 1:
            return tx

        reference = notification_data.get('merchantOrderId')
        if not reference:
            raise ValidationError(
                "Duitku: " + _("Received data with missing reference %(ref)s.", ref=reference)
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'duitku')])
        if not tx or len(tx) > 1:
            error_msg = 'Duitku: received data for reference %s' % (reference)
            if not tx:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            raise ValidationError("Duitku: " + error_msg)

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Duitku data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        """

        self.ensure_one()

        super()._process_notification_data(notification_data)
        if self.provider_code != 'duitku':
            return

        self.duitku_reference = self.provider_reference = notification_data.get('reference')
        self.duitku_order_id = notification_data.get('merchantOrderId')
        _logger.info(
            "received data with pending payment status (%s) for transaction with reference %s",
            self.duitku_reference, self.duitku_order_id
        )
        merchant_code = self.provider_id.duitku_merchant_code
        merchant_order_id = notification_data.get('merchantOrderId')
        hashtext = f"{merchant_code}{merchant_order_id}{self.provider_id.duitku_api_key}"
        signature = hashlib.md5(hashtext.encode('utf-8')).hexdigest()
        playload = {
            'merchantCode': merchant_code,
            'merchantOrderId': merchant_order_id,
            'signature': signature,
        }
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        payment_status = notification_data.get('resultCode')

        if payment_status == '00':
            _logger.info(
                "send payload data (%s)",
                playload
            )
            self.provider_id._duitku_make_request('/transactionStatus', data=playload, headers=headers)
            self._set_done()
            _logger.info(
                "received data with sucess payment status (%s) for transaction with reference %s",
                payment_status, self.reference
            )
        elif payment_status in ('01', '02'):
            self._set_pending()
            _logger.info(
                "received data with pending payment status (%s) for transaction with reference %s",
                payment_status, self.reference
            )
        else:
            _logger.info(
                "received data with invalid payment status (%s) for transaction with reference %s",
                payment_status, self.reference
            )
            self._set_error(
                "Duitku: " + _("Received data with invalid payment status: %s", payment_status)
            )