# -*- coding: utf-8 -*-
# Code created by https://github.com/maikdi/ <mikedh2612@gmail.com>
{
    'name': "Duitku Payment Acquirer",
    'author': "Duitku",
    'sequence': 100,
    'description': """Duitku Payment Acquirer""",
    'website': "https://www.duitku.com/",
    'summary': 'Payment Acquirer: Duitku Implementation',
    'category': 'Accounting/Payment Acquirers',
    'version': '1.0.0',
    'depends': ['payment'],
    'data': [
        'views/views.xml',
        'views/templates.xml',
        'data/duitku_acquirer_data.xml'
    ],
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
