from trytond.model import fields


class HTMLPartyInfoMixin:
    __slots__ = ()
    html_party = fields.Function(fields.Many2One('party.party', 'HTML Party'),
        'get_html_party')
    html_tax_identifier = fields.Function(fields.Many2One('party.identifier',
        'HTML Party Tax Identifier'), 'get_html_tax_identifier')
    html_address = fields.Function(fields.Many2One('party.address',
        'HTML Party Address'), 'get_html_address')
    html_second_address = fields.Function(fields.Many2One('party.address',
        'HTML Second Address'), 'get_html_second_address')
    html_second_address_label = fields.Function(fields.Char(
        'HTML Second Address Label'), 'get_html_second_address_label')

    def get_html_party(self, name):
        return self.party and self.party.id

    def get_html_tax_identifier(self, name):
        return (self.html_party and self.html_party.tax_identifier
            and self.html_party.tax_identifier.id)

    def get_html_address(self, name):
        return (self.html_party and self.html_party.addresses
            and self.html_party.addresses[0].id or None)

    def get_html_second_address(self, name):
        return

    def get_html_second_address_label(self, name):
        return
