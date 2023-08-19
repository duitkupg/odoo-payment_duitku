# -*- coding: utf-8 -*-

from . import models
from . import controllers


# from odoo.addons.payment.models.payment_acquirer import create_missing_journal_for_acquirers
# from odoo.addons.payment import reset_payment_provider

# def uninstall_hook(cr, registry):
#     reset_payment_provider(cr, registry, 'duitku')
#

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(cr, registry):
    setup_provider(cr, registry, 'duitku')


def uninstall_hook(cr, registry):
    reset_payment_provider(cr, registry, 'duitku')
