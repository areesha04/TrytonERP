# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.company.tests import CompanyTestMixin, create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.modules.account_invoice.tests import set_invoice_sequences
from trytond.modules.html_report.engine import HTMLReportMixin, DualRecord


class _FalseyRecord:
    _fields = {}
    __name__ = 'test.falsey'
    id = None

    def __bool__(self):
        return False


class HtmlReportTestCase(CompanyTestMixin, ModuleTestCase):
    'Test HtmlReport module'
    module = 'html_report'
    extras = ['account_invoice', 'account_payment_type',
        'account_invoice_discount', 'account_bank', 'carrier', 'sale',
        'sale_product_customer', 'purchase', 'stock', 'stock_lot',
        'stock_valued', 'production']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_dual_record_bool(self):
        self.assertFalse(DualRecord(None))
        self.assertFalse(DualRecord(_FalseyRecord()))

    @with_transaction()
    def test_get_template_filters(self):
        expected_keys = {
            'base64',
            'currencyformat',
            'decimalformat',
            'dateformat',
            'datetimeformat',
            'integer_to_words',
            'format_currency',
            'format_date',
            'format_datetime',
            'format_number',
            'format_timedelta',
            'grouped_slice',
            'js_plus_js',
            'js_to_html',
            'js_to_text',
            'modulepath',
            'nullslast',
            'numberformat',
            'number_to_words',
            'render',
            'percentformat',
            'scientificformat',
            'short_url',
            'timedeltaformat',
            'timeformat',
            }

        with Transaction().set_context(language='en', report_lang='en'):
            filters = HTMLReportMixin.get_template_filters()

            self.assertEqual(set(filters.keys()), expected_keys)
            for key in expected_keys:
                self.assertIn(key, filters)
                self.assertTrue(callable(filters[key]))

            self.assertEqual(filters['format_number'](12.45, lang=None), '12.45')
            self.assertEqual(filters['integer_to_words'](1234),
                'Thousand Two Hundred Thirty-Four')
            base64_css = filters['base64']('html_report/base.css')
            self.assertTrue(base64_css.startswith('data:text/css;base64,'))
            self.assertTrue(len(base64_css) > len('data:text/css;base64,'))
            self.assertEqual(filters['currencyformat'](12.45, 'EUR'), '€12.45')
            self.assertEqual(filters['decimalformat'](12.45), '12.45')
            self.assertEqual(filters['dateformat'](date(2024, 1, 2)), 'Jan 2, 2024')
            self.assertEqual(filters['datetimeformat'](
                    datetime(2024, 1, 2, 3, 4, 5)),
                'Jan 2, 2024, 3:04:05\u202fAM')
            self.assertEqual(filters['format_date'](date(2024, 1, 2), lang=None),
                '01/02/2024')
            self.assertEqual(filters['format_datetime'](
                    datetime(2024, 1, 2, 3, 4, 5), lang=None),
                '01/02/2024\xa003:04:05')
            self.assertEqual(filters['format_timedelta'](timedelta(hours=1)),
                '01:00')
            self.assertEqual([list(g) for g in filters['grouped_slice']([1, 2, 3], 2)],
                [[1, 2], [3]])
            # self.assertEqual(filters['js_plus_js'](['a', 'b']), 'a+b')
            # self.assertEqual(filters['js_to_html']('hello'), '<p>hello</p>')
            # self.assertEqual(filters['js_to_text']('<p>hello</p>'), 'hello')
            self.assertEqual(filters['modulepath']('html_report/base.css')[:7],
                'file://')
            self.assertEqual(filters['nullslast']([(1, 'a'), (None, 'b')]),
                [(1, 'a'), (None, 'b')])
            self.assertEqual(filters['numberformat'](12.45), '12.45')
            self.assertEqual(filters['number_to_words'](12), 'Twelve Euros')
            self.assertEqual(filters['render']('a\nb'), 'a<br/>b')
            self.assertEqual(filters['percentformat'](0.12), '12%')
            self.assertEqual(filters['scientificformat'](1000), '1E3')
            self.assertEqual(filters['short_url']('Visit https://example.com'),
                'Visit <a href="https://example.com">example.com</a>')
            self.assertEqual(filters['timedeltaformat'](timedelta(hours=1)),
                '1 hour')
            self.assertEqual(filters['timeformat'](time(3, 4, 5)), '3:04:05\u202fAM')

    @with_transaction()
    def test_html_report_mixin_helpers(self):
        pool = Pool()
        Model = pool.get('ir.model')
        record, = Model.search([], limit=1)

        with Transaction().set_context(language='en', report_lang='en'):
            self.assertEqual(
                HTMLReportMixin.label('ir.model', 'global_search_p'),
                'Global Search')
            self.assertEqual(
                HTMLReportMixin.message('ir.msg_created_at'),
                'Created at')
            self.assertEqual(
                HTMLReportMixin.markdown('# Test\nHello World'),
                '<h1>Test</h1>\n<p>Hello World</p>')
            self.assertEqual(
                HTMLReportMixin.markdown('| A | B |\n| --- | --- |\n| 1 | 2 |'),
                '<table>\n<thead>\n<tr>\n<th>A</th>\n<th>B</th>\n</tr>\n</thead>\n<tbody>\n<tr>\n<td>1</td>\n<td>2</td>\n</tr>\n</tbody>\n</table>')
            self.assertEqual(
                HTMLReportMixin.markdown('1. One\n2. Two'),
                '<ol>\n<li>One</li>\n<li>Two</li>\n</ol>')
            self.assertEqual(
                HTMLReportMixin.render_jinja(
                    '{{ value }}-{{ number }}', value='test', number=7),
                'test-7')
            self.assertTrue(
                HTMLReportMixin.qrcode('test').startswith(
                    'data:image/svg+xml;base64,'))
            self.assertTrue(
                HTMLReportMixin.barcode('code128', 'test').startswith(
                    'data:image/svg+xml;base64,'))
            self.assertTrue(
                HTMLReportMixin.datamatrix('test').startswith(
                    'data:image/svg+xml;base64,'))
            self.assertTrue(
                HTMLReportMixin.to_base64(b'<svg></svg>').startswith(
                    'data:image/svg+xml;base64,'))

            dual = HTMLReportMixin.dualrecord(record)
            self.assertIsInstance(dual, DualRecord)
            self.assertEqual(dual.raw.id, record.id)

            dual_from_string = HTMLReportMixin.dualrecord(
                f'{record.__name__},{record.id}')
            self.assertIsInstance(dual_from_string, DualRecord)
            self.assertEqual(dual_from_string.raw.id, record.id)

    @with_transaction()
    def test_check_reports(self):
        pool = Pool()
        Report = pool.get('ir.action.report')
        FiscalYear = pool.get('account.fiscalyear')
        Account = pool.get('account.account')
        Party = pool.get('party.party')
        PaymentTerm = pool.get('account.invoice.payment_term')
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Category = pool.get('product.category')
        Uom = pool.get('product.uom')
        Sale = pool.get('sale.sale')
        Purchase = pool.get('purchase.purchase')
        Location = pool.get('stock.location')
        ShipmentInternal = pool.get('stock.shipment.internal')

        company = create_company()
        with set_company(company):
            create_chart(company)

            fiscalyear = get_fiscalyear(company)
            set_invoice_sequences(fiscalyear)
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])

            account_revenue, = Account.search([
                        ('type.revenue', '=', True),
                        ('closed', '=', False),
                        ('company', '=', company.id),
                        ], limit=1)
            account_expense, = Account.search([
                        ('type.expense', '=', True),
                        ('closed', '=', False),
                        ('company', '=', company.id),
                        ], limit=1)

            payment_term, = PaymentTerm.create([{
                        'name': 'Test',
                        'lines': [
                            ('create', [{
                                        'type': 'remainder',
                                        }])
                            ],
                        }])

            unit, = Uom.search([('name', '=', 'Unit')])

            party, = Party.create([{
                        'name': 'Party',
                        'addresses': [
                            ('create', [{}]),
                            ],
                        }])

            # category
            account_category = Category()
            account_category.name = 'Account Category'
            account_category.accounting = True
            account_category.account_expense = account_expense
            account_category.account_revenue = account_revenue
            account_category.save()

            # product
            unit, = Uom.search([('name', '=', 'Unit')])
            template1 = Template()
            for key, value in Template.default_get(Template._fields.keys(),
                    with_rec_name=False).items():
                if value is not None:
                    setattr(template1, key, value)
            template1.name = 'Product 1'
            template1.list_price = Decimal(12)
            template1.cost_price = Decimal(10)
            template1.default_uom = unit
            template1.salable = True
            template1.purchasable = True
            template1.on_change_default_uom()
            template1.account_category = account_category
            template1.save()
            product1, = template1.products

            sales = Sale.create([{
                        'party': party.id,
                        'company': company.id,
                        'payment_term': payment_term.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'shipment_address': party.addresses[0].id,
                        'invoice_method': 'order',
                        'shipment_method': 'order',
                        'lines': [
                            ('create', [{
                                        'product': product1,
                                        'quantity': 2,
                                        'unit_price': Decimal('25'),
                                        'unit': unit,
                                        }]),
                            ],
                        }, {
                        'party': party.id,
                        'company': company.id,
                        'payment_term': payment_term.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'shipment_address': party.addresses[0].id,
                        'invoice_method': 'order',
                        'shipment_method': 'order',
                        'lines': [
                            ('create', [{
                                        'product': product1,
                                        'quantity': 2,
                                        'unit_price': Decimal('25'),
                                        'unit': unit,
                                        }]),
                            ],
                        }])
            Sale.quote(sales)
            Sale.confirm(sales)
            Sale.process(sales)

            purchases = Purchase.create([{
                        'party': party.id,
                        'company': company.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'invoice_method': 'order',
                        'lines': [
                            ('create', [{
                                        'product': product1,
                                        'quantity': 2,
                                        'unit_price': Decimal('25'),
                                        'unit': unit,
                                        }]),
                            ],
                        }, {
                        'party': party.id,
                        'company': company.id,
                        'currency': company.currency.id,
                        'invoice_address': party.addresses[0].id,
                        'invoice_method': 'order',
                        'lines': [
                            ('create', [{
                                        'product': product1,
                                        'quantity': 2,
                                        'unit_price': Decimal('25'),
                                        'unit': unit,
                                        }]),
                            ],
                        }])
            Purchase.quote(purchases)
            Purchase.confirm(purchases)
            Purchase.process(purchases)

            storage_loc, = Location.search([('name', '=', 'Storage Zone')])
            lost_found_loc, = Location.search([('name', '=', 'Lost and Found')])

            # TODO stock.shipment.in
            shipment_internals = ShipmentInternal.create([{
                        'from_location': storage_loc.id,
                        'to_location': lost_found_loc.id,
                        'moves': [
                            ('create', [{
                                        'product': product1,
                                        'quantity': 2,
                                        'unit': unit,
                                        'from_location': storage_loc.id,
                                        'to_location': lost_found_loc.id,
                                        }]),
                            ],
                        }])
            ShipmentInternal.wait(shipment_internals)

            # TODO production

            reports = Report.search([
                    ('model', '!=', None),
                    ('template_extension', '=', 'html'),
                    ])

            for report in reports:
                if not report.keywords or not report.model:
                    continue

                Model = pool.get(report.model)
                records = Model.search([], limit=5, order=[('id', 'DESC')])
                # records += Model.search([], limit=5, order=[('id', 'ASC')])
                for record in records:
                    Report = pool.get(report.report_name, type='report')
                    Report.execute([record.id], data={})


del ModuleTestCase
