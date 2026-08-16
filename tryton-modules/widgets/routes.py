# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import mimetypes

from trytond.protocols.wrappers import (
    HTTPStatus, Response, abort, with_pool, with_transaction)
from trytond.wsgi import app

@app.route('/<database_name>/widgets/attachment/<int:record>')
@app.auth_required
@with_pool
@with_transaction(user='request', context=dict(_check_access=True))
def attachment(request, pool, record):

    Attachment = pool.get('ir.attachment')
    attachments = Attachment.search([
            ('id', '=', record),
            ], limit=1)

    if not attachments:
        abort(HTTPStatus.NOT_FOUND)

    attachment, = attachments

    file_mime = mimetypes.guess_type(attachment.name, strict=False)[0]
    return Response(attachment.data, mimetype=file_mime)
