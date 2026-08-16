# custom_reports/utils.py

REPORT_CSS = """
@page { size: A4 portrait; margin: 12mm; }
@page cash_book { size: A4 landscape; margin: 10mm; }

body { 
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; 
    font-size: 10px; 
    color: #1e293b; 
    line-height: 1.4; 
}
.report-header { 
    text-align: center; 
    margin-bottom: 20px; 
    padding-bottom: 15px; 
    border-bottom: 2px solid #64748b; 
}
h1 { 
    margin: 0; 
    font-size: 20px; 
    font-weight: 700; 
    color: #0f172a; 
    text-transform: uppercase; 
    letter-spacing: 1px; 
}
h3 { 
    margin: 4px 0 0 0; 
    font-size: 13px; 
    font-weight: 500; 
    color: #475569; 
}
.meta-info { 
    display: flex; 
    justify-content: space-between; 
    margin-bottom: 15px; 
    font-size: 11px; 
    color: #334155; 
}
table { 
    width: 100%; 
    border-collapse: collapse; 
    margin-bottom: 25px; 
    border: 1px solid #64748b; 
}
th { 
    background-color: #1e293b; /* Dark Slate Header */
    color: #ffffff;            /* Crisp White Text */
    font-weight: 600; 
    text-align: left; 
    padding: 8px 6px; 
    border: 1px solid #475569; 
    font-size: 9px; 
    text-transform: uppercase; 
    letter-spacing: 0.5px; 
}
td { 
    padding: 6px; 
    border: 1px solid #cbd5e1; /* Clear Column Borders */
    vertical-align: top; 
}
tr:nth-child(even) td { 
    background-color: #f8fafc; /* Soft alternating row shade */
}
.text-right { text-align: right; }
.text-center { text-align: center; }
.font-bold { font-weight: 700; color: #0f172a; }
.total-row td { 
    background-color: #e2e8f0; 
    font-weight: 700; 
    border-top: 1px solid #64748b; 
    border-bottom: 2px solid #0f172a; 
    color: #0f172a; 
}

/* Cash Book Specific Styles */
.cb-container { 
    display: table; 
    width: 100%; 
    border: 1px solid #64748b; 
    border-radius: 4px; 
    table-layout: fixed;
    page-break-inside: auto;
    break-inside: auto;
}
.cb-side { 
    display: table-cell; 
    width: 50%; 
    vertical-align: top;
    page-break-inside: auto;
    break-inside: auto;
}
.cb-side:first-child { 
    border-right: 1px solid #64748b; 
}
.cb-title { 
    background-color: #1e293b; 
    color: #ffffff;
    text-align: center; 
    font-weight: 700; 
    padding: 6px; 
    border-bottom: 1px solid #475569; 
    letter-spacing: 1px; 
}
"""