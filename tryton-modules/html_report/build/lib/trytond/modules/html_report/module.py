from dominate.tags import h1, p, table, tbody, td, th, thead, tr

from .dominate_report import DominateReport
from trytond.modules.xgettext import _


class ModuleReport(DominateReport):
    __name__ = 'html_report.module_report'
    _single = False

    @classmethod
    def css(cls, action, data, records):
        css = super().css(action, data, records) or ''
        return css + '\n@page { size: A4 landscape; }\n'

    @classmethod
    def title(cls, action, data, records):
        return _('Module List')

    @classmethod
    def body(cls, action, data, records):
        dependencies_label = cls.label('ir.module', 'dependencies')
        modules_table = table(style='width:100%;')
        with modules_table:
            with thead():
                with tr():
                    th(cls.label('ir.module', 'name'))
                    th(cls.label('ir.module', 'version'))
                    th(cls.label('ir.module', 'state'))
                    th(dependencies_label)
            with tbody():
                for record in records:
                    dependencies = ', '.join(
                        dependency.render.name for dependency in record.dependencies)
                    with tr():
                        td(record.render.name)
                        td(record.render.version or '')
                        td(record.render.state or '')
                        td(dependencies)

        return [
            h1(_('Module List'), cls='title'),
            p(_('This report lists the selected modules and their dependencies.')),
            modules_table,
        ]
