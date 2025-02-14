# -*- coding: utf-8 -*-

from . import models
from . import controllers


# from odoo.addons.payment.models.payment_acquirer import create_missing_journal_for_acquirers
# from odoo.addons.payment import reset_payment_provider

import odoo.addons.payment as payment  # prevent circular import error with payment


def post_init_hook(env):
    payment.setup_provider(env, 'duitku')


def uninstall_hook(env):
    payment.reset_payment_provider(env, 'duitku')