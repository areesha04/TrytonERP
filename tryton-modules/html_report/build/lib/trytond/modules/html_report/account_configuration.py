# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields, ModelSQL
from trytond.pool import Pool, PoolMeta
from trytond.modules.company.model import CompanyValueMixin


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    use_invoice_report_cache = fields.MultiValue(
        fields.Boolean("Use Invoice Report Cache"))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'use_invoice_report_cache':
            return pool.get('account.configuration.html_report')
        return super().multivalue_model(field)

    @classmethod
    def default_use_invoice_report_cache(cls, **pattern):
        return True


class ConfigurationHTMLReport(ModelSQL, CompanyValueMixin):
    "Account Configuration HTML Report"
    __name__ = 'account.configuration.html_report'

    use_invoice_report_cache = fields.Boolean("Use Invoice Report Cache")
