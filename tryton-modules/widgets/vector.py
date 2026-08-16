import json

from trytond.model import fields


class Vector(fields.Field):
    _type = 'vector'
    _py_type = list

    def __init__(self, string='', size=None, help='', required=False,
            readonly=False, domain=None, states=None, on_change=None,
            on_change_with=None, depends=None, context=None,
            loading='eager'):
        super().__init__(string=string, help=help, required=required,
            readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.size = size

    @property
    def _sql_type(self):
        if isinstance(self.size, int):
            return 'vector(%s)' % self.size
        else:
            return 'vector'

    def get(self, ids, model, name, values=None):
        vectors = dict((id, None) for id in ids)
        for value in values or []:
            data = value.get(name)
            if data is None:
                vectors[value['id']] = None
                continue

            # pgvector + psycopg may return numpy arrays; normalize to list.
            if hasattr(data, 'tolist'):
                data = data.tolist()
            elif isinstance(data, str):
                if data.startswith('[') and data.endswith(']'):
                    data = json.loads(data)
            elif isinstance(data, tuple):
                data = list(data)
            elif not isinstance(data, list):
                try:
                    data = list(data)
                except TypeError:
                    pass

            if isinstance(data, list):
                # Ensure plain Python floats (avoid numpy scalar types).
                data = [float(x) for x in data]

            vectors[value['id']] = data
        return vectors
