# This file is part xgettext module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from unittest.mock import patch

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction

from trytond.modules.xgettext.i18n import KEY, TYPE, _


class XGettextTestCase(ModuleTestCase):
    'Test XGettext module'
    module = 'xgettext'

    @with_transaction()
    def test_gettext_uses_shared_translation_type(self):
        with Transaction().set_context(language='ca'):
            with patch('trytond.modules.xgettext.i18n.Pool') as pool:
                pool.return_value.get.return_value.get_source.return_value = (
                    'Traduccio')
                self.assertEqual(_('Message'), 'Traduccio')
                pool.return_value.get.return_value.get_source.assert_called_once_with(
                    KEY, TYPE, 'ca', 'Message')

    @with_transaction()
    def test_gettext_falls_back_to_source_message(self):
        with Transaction().set_context(language='es'):
            with patch('trytond.modules.xgettext.i18n.Pool') as pool:
                pool.return_value.get.return_value.get_source.return_value = None
                self.assertEqual(_('Original'), 'Original')


del ModuleTestCase
