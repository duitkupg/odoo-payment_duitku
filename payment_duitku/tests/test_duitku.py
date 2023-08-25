import hashlib
import coverage
from odoo.addons.payment.tests.common import PaymentAcquirerCommon
from odoo.tests import tagged
from lxml import objectify
from werkzeug import urls
from unittest.mock import Mock, patch
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.exceptions import ValidationError as ValEr
from odoo.exceptions import AccessError
from odoo.tools import mute_logger
from requests.exceptions import HTTPError


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def raise_for_status(self):
        return True


class DuitkuCommon(PaymentAcquirerCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.currency_idr = cls.env.ref('base.IDR')

        # Create the mock api for requesting transaction
        mock_api = Mock()

        # Configure to always return a successful mock response every time a transaction in requested
        # This is what matters in a successful create_transaction requests
        mock_response = {
            'paymentUrl': 'mockurl.com',
            'reference': 'mock_reference'
        }
        mock_api.duitku_create_transaction.return_value = mock_response
        cls.duitku = cls.env.ref('payment_duitku.payment_provider_duitku')
        cls.duitku._set_duitku_api(mock_api)
        cls.duitku.write({
            'duitku_merchant_code': 'dummy_code',
            'duitku_api_key': 'dummy_key',
            'duitku_environment': 'sandbox',
            'duitku_expiry': 1440,
            'state': 'test',
        })


@tagged('post_install', '-at_install')
class DuitkuForm(DuitkuCommon):

    def test_10_duitku_form_render(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')

        self.assertEqual(self.duitku.state, 'test', 'test without test environment')

        # ----------------------------------------
        # Test: button direct rendering
        # ----------------------------------------

        res = self.duitku.render(
            'test_ref_1', 100000, self.currency_idr.id,
            values=self.buyer_values)

        form_values = {
            'payment_url': 'mockurl.com',
            'merchantOrderId': 'test_ref_1',
            'expiryPeriod': '1440',  # Int turns to str when creating transaction
            'callMode': 'True',  # Even boolean turns to str during form passing
            'reference': 'mock_reference'
        }

        # check form result
        tree = objectify.fromstring(res)

        data_set = tree.xpath("//input[@name='data_set']")
        expected_action_url = urls.url_join(base_url, '/payment/duitku/call/')
        self.assertEqual(len(data_set), 1, 'Duitku: Found %d "data_set" input instead of 1' % len(data_set))
        self.assertEqual(data_set[0].get('data-action-url'), expected_action_url,
                         'Duitku: wrong form POST url')
        for form_input in tree.input:
            if form_input.get('name') in ['submit', 'data_set']:
                continue
            self.assertEqual(
                form_input.get('value'),
                form_values[form_input.get('name')],
                'Duitku: wrong value for input %s: received %s instead of %s' % (
                    form_input.get('name'), form_input.get('value'), form_values[form_input.get('name')])
            )

    @mute_logger('from odoo.addons.payment.models.payment_acquirer', 'ValidationError')
    @mute_logger('odoo.exceptions', 'AccessError')
    def test_20_duitku_form_management(self):

        self.assertEqual(self.duitku.state, 'test', 'test without test environment')

        # Calculate the signature that will be used as the signature in dummy data
        # Params = merchant Code + Amount + Order Id + API Key
        params = 'dummy_code' + '50000' + 'test_ref_2' + 'dummy_key'
        signature = hashlib.md5(params.encode('utf-8')).hexdigest()
        # Dummy Callback Data
        duitku_callback_data = {
            'merchantCode': 'dummy_code',
            'amount': '50000',
            'merchantOrderId': 'test_ref_2',
            'productDetail': 'dummy_detail',
            'additionalParam': '',
            'paymentCode': 'VA',
            'resultCode': '02',
            'merchantUserId': 'dummy@mail.com',
            'reference': 'mock_reference',
            'signature': signature
        }

        # should raise error about unknown tx
        with self.assertRaises(ValidationError):
            self.env['payment.transaction'].form_feedback(duitku_callback_data, 'duitku')

        # create tx
        tx = self.env['payment.transaction'].create({
            'amount': 50000,
            'acquirer_id': self.duitku.id,
            'currency_id': self.currency_idr.id,
            'reference': 'test_ref_2',
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france.id})

        # validate it
        tx.form_feedback(duitku_callback_data, 'duitku')
        # check
        self.assertEqual(tx.state, 'pending',
                         'duitku: the state should be changed to pending until confirmed payment')
        self.assertEqual(tx.state_message, '02', 'duitku: wrong state message after receiving a pending notification')
        self.assertEqual(tx.acquirer_reference, 'test_ref_2',
                         'duitku: wrong order id after receiving a valid pending notification')

        # update tx
        tx.write({
            'acquirer_reference': 'test_ref_2',
            'reference': 'test_ref_2'})

        # update notification from duitku
        duitku_callback_data['resultCode'] = '00'
        tx.sudo().form_feedback(duitku_callback_data, 'duitku')  # Sudo to bypass access errors.
        # check
        self.assertEqual(tx.state, 'done', 'duitku: wrong state after receiving a valid pending notification')
        self.assertEqual(tx.state_message, '', 'duitku: wrong state message after receiving a valid notification')
        self.assertEqual(tx.acquirer_reference, 'test_ref_2',
                         'duitku: wrong txn_id after receiving a valid pending notification')

    def test_21_return_all_invalid_parameters(self):
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')
        # Dummy Callback Data
        duitku_callback_data = {
            'amount': '10000',  # The important thing is to NOT have the same amount as the transaction.
            'merchantOrderId': 'wrong_order_id',
            'productDetail': 'dummy_detail',
            'additionalParam': '',
            'paymentCode': 'VA',
            'resultCode': '02',
            'merchantUserId': 'dummy@mail.com',
            'reference': 'mock_reference',
        }
        # create tx
        tx = self.env['payment.transaction'].create({
            'amount': 50000,
            'acquirer_id': self.duitku.id,
            'currency_id': self.currency_idr.id,
            'reference': 'test_ref_2.1',
            'partner_name': 'Norbert Buyer',
            'partner_country_id': self.country_france.id})

        # validate it
        invalid_param_method_name = '_duitku_form_get_invalid_parameters'
        invalid_parameters = getattr(tx, invalid_param_method_name)(duitku_callback_data)
        self.assertEqual(len(invalid_parameters), 4,
                         "Should count and return all the invalid parameters")
    def test_30_return_duitku_production_call_url(self):
        # Arrange
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')
        self.duitku._set_duitku_api()  # Reset the API to default API since we want to test the API this time

        # Act
        prod_url = self.duitku.duitku_api['api'].duitku_get_call_url('production')
        sandbox_url_1 = self.duitku.duitku_api['api'].duitku_get_call_url('sandbox')
        # The code I built would return the sandbox url if the environment is not 'production'
        sandbox_url_2 = self.duitku.duitku_api['api'].duitku_get_call_url('not_production')
        expected_prod_url = 'https://api-prod.duitku.com/api/merchant/createInvoice'
        expected_sandbox_url = 'https://api-sandbox.duitku.com/api/merchant/createInvoice'

        # Assert
        self.assertEqual(prod_url, expected_prod_url, 'duitku: wrong production url')
        self.assertEqual(sandbox_url_1, expected_sandbox_url, 'duitku: wrong sandbox url')
        self.assertEqual(sandbox_url_2, expected_sandbox_url, 'duitku: wrong sandbox url')

    def test_31_return_correct_duitku_check_transaction_url(self):
        # Arrange
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')
        self.duitku._set_duitku_api()  # Reset the API to default API since we want to test the API this time

        # Act
        prod_url = self.duitku.duitku_api['api'].duitku_get_check_transaction_url('production')
        sandbox_url_1 = self.duitku.duitku_api['api'].duitku_get_check_transaction_url('sandbox')
        # The code I built would return the sandbox url if the environment is not 'production'
        sandbox_url_2 = self.duitku.duitku_api['api'].duitku_get_check_transaction_url('not_production')
        expected_prod_url = 'https://api-prod.duitku.com/api/merchant/transactionStatus'
        expected_sandbox_url = 'https://api-sandbox.duitku.com/api/merchant/transactionStatus'

        # Assert
        self.assertEqual(prod_url, expected_prod_url, 'duitku: wrong production url')
        self.assertEqual(sandbox_url_1, expected_sandbox_url, 'duitku: wrong sandbox url')
        self.assertEqual(sandbox_url_2, expected_sandbox_url, 'duitku: wrong sandbox url')

    @mute_logger('odoo.addons.payment_paypal.models.payment', 'ValEr')
    def test_40_return_error_for_failed_request(self):
        # Arrange
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')
        duitku_api = self.duitku.duitku_api['api']
        mock_tx = Mock()  # Mock transaction object that will be used for logger warning
        mock_tx._set_transaction_error.return_value = True  # Doesn't matter what it does/return.

        # It really doesn't matter what the actual response are in here
        # What we care for now is the status code
        mock_response = {
            'paymentUrl': 'mockurl.com',
            'reference': 'mock_reference'
        }
        succesful_resp = MockResponse(mock_response, 200)
        failed_resp_1 = MockResponse(mock_response, 400)
        failed_resp_2 = MockResponse(mock_response, 404)

        # Act
        succesful_req = duitku_api.process_request(succesful_resp, mock_tx)

        # Assert
        self.assertEqual(mock_response, succesful_req)
        with self.assertRaises(ValEr):  # Different ValEr because this one actually sends an output to the user
            duitku_api.process_request(failed_resp_1, mock_tx)

        with self.assertRaises(ValEr):
            duitku_api.process_request(failed_resp_2, mock_tx)

    @mute_logger('odoo.addons.payment_paypal.models.payment', 'ValEr')
    def test_41_return_error_for_failed_check_transaction(self):
        # Arrange
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')
        # It really doesn't matter what the actual response are in here
        # What we care for now is the status code
        fail_mock_response = {
            'statusCode': '01'
        }
        success_mock_response = {
            'statusCode': '00'
        }
        mock_values = {
            'merchantCode': '',
            'merchantOrderId': ''
        }
        succesful_resp = MockResponse(success_mock_response, 200)
        failed_resp = MockResponse(fail_mock_response, 200)

        duitku_api = self.duitku.duitku_api['api']

        # Act
        succesful_request = duitku_api.send_check_transaction_request(succesful_resp)

        # Assert
        self.assertEqual(success_mock_response,
                         succesful_request)  # If it's successful, should just return the initial response
        with self.assertRaises(HTTPError):  # Just give whatever value that should cause an error.
            duitku_api.duitku_check_transaction(mock_values, '', '')

        with self.assertRaises(ValEr):  # Should raise ValEr if the request is found, but not paid yet
            duitku_api.send_check_transaction_request(failed_resp)


# A new form to create a transaction with a different currency.
@tagged('post_install', '-at_install')
class DuitkuForm2(DuitkuCommon):

    def test_10_duitku_form_return_error_not_idr(self):
        self.assertEqual(self.duitku.state, 'test', 'test without test environment')

        with self.assertRaises(ValEr):
            self.duitku.render(
                'test_ref_3', 100000, self.currency_euro.id,
                values=self.buyer_values)
