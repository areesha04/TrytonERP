import weasyprint

from trytond.transaction import Transaction
from trytond.report import Report
from trytond.pool import Pool

class HTMLReport(Report):
    render_method = "weasyprint"
    babel_domain = 'messages'
    report_translations = None
    side_margin = 2
    extra_vertical_margin = 30

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context({
                    'html_report_ids': ids,
                    'html_report_data': data,
                    }):
            return super().execute(ids, data)

    @classmethod
    def render(cls, report, report_context):
        if not report.report_content:
            raise Exception('Error', 'Missing report file!')
        return report.report_content.decode('utf-8')

    @classmethod
    def convert(cls, report, data):
        # Convert the report to PDF if the output format is PDF
        # Do not convert when report is generated in tests, as it takes
        # time to convert to PDF due to which tests run longer.
        # Pool.test is True when running tests.
        output_format = report.extension or report.template_extension

        if Pool.test:
            return output_format, data
        elif cls.render_method == "weasyprint" and output_format == "pdf":
            return output_format, cls.weasyprint(data)

        return output_format, data

    @classmethod
    def weasyprint(cls, data, options=None):
        return weasyprint.HTML(string=data).write_pdf()
