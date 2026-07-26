from cryptography.fernet import Fernet, InvalidToken
import trytond.config as config
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import fields

FERNET_KEY = config.get('cryptography', 'fernet_key')


class FernetEncryptionMixin:
    __slots__ = ()

    @classmethod
    def get_fernet(cls):
        if not FERNET_KEY:
            raise UserError(gettext('widgets.msg_missing_fernet_key'))
        return Fernet(FERNET_KEY)

    def get_fernet_value(self, name):
        if not name.endswith('_decrypted'):
            return 'x' * 10

        clear_name = name[:-10]
        if clear_name not in self._fields:
            raise UserError(gettext(
                'widgets.msg_unknown_decrypted_field',
                field=clear_name))

        encrypted_name = '%s_encrypted' % clear_name
        encrypted_value = getattr(self, encrypted_name, None)
        if not encrypted_value:
            return None
        try:
            decrypted = self.get_fernet().decrypt(bytes(encrypted_value))
        except InvalidToken as exc:
            raise UserError(gettext(
                    'widgets.msg_invalid_fernet_token',
                    field=clear_name)) from exc
        if isinstance(self._fields[clear_name], fields.Binary):
            return decrypted
        return decrypted.decode('utf-8')

    @classmethod
    def set_fernet_value(cls, records, name, value):
        if value == 'x' * 10:
            return
        if value:
            if not isinstance(value, bytes):
                value = value.encode('utf-8')
            encrypted_value = cls.get_fernet().encrypt(value)
        else:
            encrypted_value = None
        encrypted_name = '%s_encrypted' % name
        cls.write(records, {encrypted_name: encrypted_value})
