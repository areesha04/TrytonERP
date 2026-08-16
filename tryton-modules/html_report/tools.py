import tempfile
from openpyxl.writer.excel import save_workbook
from datetime import date, datetime, time as dt_time
from decimal import Decimal

from trytond.pool import Pool
from trytond.transaction import Transaction

def save_virtual_workbook(workbook):
    with tempfile.NamedTemporaryFile() as tmp:
        save_workbook(workbook, tmp.name)
        with open(tmp.name, 'rb') as f:
            return f.read()

def _convert_to_title(value):
    # Replace symbols that are not allowed in the sheet name
    title = value.replace('/', '_').replace(':', '_')
    # Excel has a limit of 31 characters for the sheet name
    title = title[:31]
    return title

def _convert_to_string(value):
    if isinstance(value, (Decimal, str, int, float, date, datetime,
            dt_time, bool)):
        return value
    return str(value) if value is not None else None

def _convert_str_to_float(value):
    if isinstance(value, str):
        try:
            return float(value.replace(',', '.'))
        except ValueError:
            return value
    return value

def label(model, field=None, lang=None):
    pool = Pool()
    Translation = pool.get('ir.translation')
    Model = pool.get('ir.model')

    if not lang:
        lang = Transaction().language

    if not model:
        return ''

    if field is None:
        model, = Model.search([('name', '=', model)])
        return model.string

    args = ("%s,%s" % (model, field), 'field', lang, None)
    translation = Translation.get_sources([args])
    if translation[args]:
        return translation[args]

    args = ("%s,%s" % (model, field), 'field', 'en', None)
    translation = Translation.get_sources([args])
    if translation[args]:
        return translation[args]

    ModelObject = pool.get(model)
    return getattr(ModelObject, field).string
