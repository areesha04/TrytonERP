# This file is part xgettext module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool

from . import i18n

_ = i18n._

__all__ = ['_', 'register']


def register():
    Pool.register(
        i18n.Translation,
        module='xgettext', type_='model')
    Pool.register(
        i18n.TranslationSet,
        i18n.TranslationClean,
        i18n.TranslationUpdate,
        module='xgettext', type_='wizard')
