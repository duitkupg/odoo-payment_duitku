# -*- coding: utf-8 -*-
# Code created by https://github.com/maikdi/ <mikedh2612@gmail.com>
{
    'name': "Duitku Payment Acquirer",
    'author': "Duitku",
    'sequence': 100,
    'description': "Duitku Payment Acquirer",
    'website': "https://www.duitku.com/",
    'summary': 'Payment Acquirer: Duitku Implementation',
    'category': 'Accounting/Payment Providers',
    'version': '1.0.0',
    'depends': ['payment'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_duitku_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml'
    ],
    'images': [
        'static/src/img/duitku_icon.png',
        'static/src/thumbnail.png',
        'static/description/duitku_icon.png',
        'static/description/icon.png'
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
