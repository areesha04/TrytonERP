import base64
import hashlib
import json
import re
from html2text import html2text
from sql.functions import Function
from trytond import backend
from trytond.pool import Pool
from trytond.transaction import Transaction
from bs4 import BeautifulSoup


class Similarity(Function):
    __slots__ = ()
    _function = 'SIMILARITY'


def create_similarity():
    conn = Transaction().connection
    if backend.name == 'sqlite':
        def trigram_similarity(a, b):
            if a is None or b is None:
                return None
            a = str(a).lower()
            b = str(b).lower()
            if len(a) < 3 or len(b) < 3:
                return 1.0 if a == b else 0.0

            def trigrams(s):
                return {s[i:i + 3] for i in range(len(s) - 2)}

            ta = trigrams(a)
            tb = trigrams(b)
            union = ta | tb
            if not union:
                return 0.0
            return len(ta & tb) / len(union)
        conn.create_function('similarity', 2, trigram_similarity)


def js_plus_js(js1, js2):
    if not js1:
        return js2
    if not js2:
        return js1
    js1 = json.loads(js1)
    js2 = json.loads(js2)
    js1['blocks'] += js2['blocks']
    return json.dumps(js1)

def js_to_html(content_block, url_prefix='', width=None):
    '''
    Converts editorJS data blocks into an html document
    '''
    if not content_block:
        return ''

    try:
        js_object = json.loads(content_block)
    except (json.JSONDecodeError, TypeError):
        return

    html = '<html><body>'
    for block in js_object['blocks']:
        was_p = False
        match block['type']:
            case 'list':
                if block['data']['style'] == 'unordered':
                    html += '<ul>'
                    for entry in block['data']['items']:
                        html += '<li>' + entry + '</li>'
                    html += '</ul>'
                else:
                    html += '<ol>'
                    for entry in block['data']['items']:
                        html += '<li>' + entry + '</li>'
                    html += '</ol>'
            case 'header':
                html += '<h' + str(block['data']['level']) + '>' + block['data']['text'] + '</h' + str(block['data']['level']) + '>'
            case 'paragraph':
                html += '<p>' + block['data']['text'] + '</p>'
                was_p = True
            case 'checklist':
                html += '<form>'
                counter = 0
                for entry in block['data']['items']:
                    is_checked = "false"
                    if entry['checked']:
                        is_checked = "true"
                    html += '<input type="checkbox" id="checkbox' + str(counter) + '" value="checkbox' + str(counter) + '" checked="' + is_checked + '" />'
                    html += '<label for="checkbox' + str(counter) + '">'+ entry['text'] + '</label>'
                    counter += 1
                html += '</form>'
            case 'table':
                html += '<table>'
                counter = 0
                for entry in block['data']['content']:
                    html += '<tr>'
                    for text in entry:
                        if block['data']['withHeadings'] == True and counter == 0:
                            html += '<th>' + text + '</th>'
                        else:
                            html += '<td>' + text + '</td>'
                    html += '</tr>'
                html += '</table>'
            case 'delimeter':
                html += '<hr />'
            case 'warning':
                html += '<table><tr><th>' + block['data']['title'] + '</th></tr>'
                html += '<tr><td>' + block['data']['message'] + '</td></tr>'
            case 'code':
                html += '<code>'
                try:
                    html += re.sub('[^\\]\\n', '<br />', block['data']['code'])
                except re.error:
                    pass
                html += '</code>'
            case 'quote':
                html += '<blockquote cite=' + block['data']['caption'] + '>' + block['data']['text'] + '</blockquote>'
            case 'image':
                src = None
                url = block['data']['file']['url']
                if url_prefix == 'cid:':
                    attachment = attachment_from_url(url)
                    if attachment:
                        src = 'cid:' + cid_from_attachment(attachment)
                elif url_prefix == 'base64':
                    attachment = attachment_from_url(url)
                    if attachment:
                        src = 'data:;base64,' + base64.b64encode(attachment.data).decode('utf-8')
                else:
                    src = url_from_tryton_to_flask(url, url_prefix)
                if width:
                    img_width = f'width="{width}"'
                else:
                    img_width = ''
                if src:
                    html += f'<img src="{src}" {img_width}/>'
            case 'link':
                html += '<a href=' + block['data']['url'] + '></a>'
        if not was_p:
            html += '<br />'

    html += '</body></html>'
    return html

def js_to_text(js):
    text = ''
    try:
        js_object = json.loads(js)
    except TypeError:
        return text
    except json.decoder.JSONDecodeError:
        return text

    def _replace_br(value):
        return re.sub(r'<br\s*/?>', r'\n\n', value, flags=re.IGNORECASE)

    try:
        blocks = js_object['blocks']
    except TypeError:
        return text

    for block in blocks:
        type_ = block.get('type', 'paragraph')
        if type_ == 'header':
            text += '# %s\n\n' % _replace_br(block['data']['text'])
        elif type_ == 'list':
            for item in  block['data']['items']:
                text += '- %s\n' % _replace_br(item)
            text += '\n'
        elif type_ == 'quote':
            text += '> %s\n\n' % _replace_br(block['data']['text'])
        elif type_ == 'code':
            text += '```\n%s\n```\n\n' % block['data']['code']
        elif type_ == 'image':
            if block['data'].get('url'):
                text += '![](%s)\n\n' % block['data']['url']
            elif block['data'].get('file'):
                text += '![](%s)\n\n' % block['data']['file']['url']
        elif type_ == 'checklist':
            for item in  block['data']['items']:
                text += '[%s] %s\n' % ('X' if item['checked'] else '', _replace_br(item['text']))
            text += '\n'
        elif block['data'].get('text'):
            text += '%s\n\n' % _replace_br(block['data']['text'])
    return text

def text_to_js(text):
    '''
    Converts text to a dictionary of datablocks to be used with editorJS using
    Markdown-like structure
    '''
    datablocks = []
    text_blocks = text.split('\n')
    for block in text_blocks:
        if not block:
            continue
        current_block = {'data' : {}}
        block = block.strip('\n')
        block = block.replace('\\', '')
        block = block.strip()
        if len(block) > 0:
            block = block.replace('[![]', '[!]')
            match block[0]:
                case '#':
                    current_block['type'] = 'header'
                    current_block['data']['level'] = len(block.split(' ')[0])
                    current_block['data']['text'] = block.strip('#').strip(' ')
                    datablocks.append(current_block.copy())
                case '-':
                    if block == '--':
                        current_block['type'] = 'paragraph'
                        current_block['data']['text'] = block.strip(' ')
                        if len(current_block['data']['text'].strip(' ')) > 0:
                            datablocks.append(current_block.copy())
                    elif len(block) > 2:
                        if block[1] and block[2]:
                            if block[1] == '-' and block[2] == '-':
                                current_block['type'] = 'delimeter'
                                current_block['data'] = {}
                                datablocks.append(current_block.copy())
                            else:
                                current_block['type'] = 'list'
                                current_block['data']['style'] = 'unordered'
                                current_block['data']['items'] = [b.strip('-') for b in block.split('\n')]
                                datablocks.append(current_block.copy())
                case '1':
                    if len(block) > 1:
                        if block[1] == '.':
                            current_block['type'] = 'list'
                            current_block['data']['style'] = 'ordered'
                            current_block['data']['items'] = [b[2:] for b in block.split('\n')]
                            datablocks.append(current_block.copy())
                case '`':
                    current_block['type'] = 'code'
                    current_block['data']['code'] = block.strip('`')
                    datablocks.append(current_block.copy())
                case '>':
                    if len(block) > 1:
                        if block[0] and block[1]:
                            current_block['type'] = 'list'
                            current_block['data']['style'] = 'unordered'
                            current_block['data']['items'] = [b.strip('>') for b in block.split('\n')]
                            datablocks.append(current_block.copy())
                case '!':
                    current_block['type'] = 'image'
                    block = re.sub(r"!\[[^\]]*\]", '', block)
                    current_block['data']['url'] = block.strip('[').split(':')[-1].strip(']').strip()
                    #str(attachment_id_from_name(block.strip('[').split(':')[-1].strip(']')))
                    datablocks.append(current_block.copy())
                case '<':
                    if re.match(r'\<image>', block):
                        current_block['type'] = 'image'
                        current_block['data']['url'] = block.strip('<').split(':')[-1].strip('>').strip()
                        #str(attachment_id_from_name(block.strip('<').split(':')[-1].strip('>')))
                        datablocks.append(current_block.copy())
                case '[':
                    if re.match(r'\[image', block) or re.match(r'\[!]', block):

                        block = re.sub(r"\[!\]", '', block)
                        current_block['type'] = 'image'
                        current_block['data']['url'] = block.strip('(').strip(')')
                        #str(attachment_id_from_name(block.strip('[').split(':')[-1].strip(']')))
                        datablocks.append(current_block.copy())
                case _:
                    current_block['type'] = 'paragraph'
                    current_block['data']['text'] = block.strip(' ')
                    if len(current_block['data']['text'].strip(' ')) > 0:
                        datablocks.append(current_block.copy())
    return json.dumps({'blocks': datablocks})

def html_to_js(html_string, is_mail=False):
    if not is_mail:
        converted = html2text(html_string, bodywidth=0)
        processed = text_to_js(converted)
        return processed
    else:
        if html_string == '' or html_string is None:
            return ''
        datablocks = []
        html_json = BeautifulSoup(html_string, 'lxml')
        for component in html_json.find_all(recursive=False):
            current_block = {'data': {}}
            if not re.match(component.name, 'h[1-6]'):
                if len(component) > 0:
                    match component.name:
                        case 'p':
                            current_block['type'] = 'paragraph'
                            current_block['data']['text'] = str(component.contents)
                            datablocks.append(current_block.copy())
                        case 'delimeter':
                            current_block['type'] = 'delimeter'
                            current_block['data'] = {}
                            datablocks.append(current_block.copy())
                        case 'code':
                            current_block['type'] = 'code'
                            current_block['data']['code'] = str(component.contents).strip('`')
                            datablocks.append(current_block.copy())
                        case 'blockquote':
                            current_block['type'] = 'quote'
                            current_block['data']['caption'] = str(component.find('cite'))
                            current_block['data']['text'] = str(component.find())
                        case 'ul':
                            current_block['type'] = 'list'
                            current_block['data']['style'] = 'unordered'
                            current_block['data']['items'] = []
                            for list_entry in component.find_all('li'):
                                current_block['data']['items'].append(list_entry.contents)
                            datablocks.append(current_block.copy())
                        case 'ol':
                            current_block['type'] = 'list'
                            current_block['data']['style'] = 'ordered'
                            current_block['data']['items'] = []
                            for list_entry in component.find_all('li'):
                                current_block['data']['items'].append(list_entry.contents)
                            datablocks.append(current_block.copy())
                        case 'form':
                            current_block['type'] = 'checklist'
                            current_block['data']['items'] = []
                            for input in component.find_all('input'):
                                if input.find('checked') == 'true':
                                    checked = 'True'
                                else:
                                    checked = 'False'
                                checkbox = {
                                    'checked': checked,
                                    'text': str(input.find())
                                }
                                current_block['data']['items'].append(checkbox)
                            datablocks.append(current_block.copy())
                        case 'table':
                            current_block['type'] = 'table'
                            current_block['data'] = []
                            current_block['data']['content'] = []
                            for t_row in component.contents:
                                if t_row.name == 'th':
                                    current_block['data']['withHeadings'] = True
                                if t_row.name == 'tr' or t_row.name == 'th':
                                    row = []
                                    for cell in t_row.contents:
                                        if cell.name == 'td':
                                            row.append(cell.contents[0])
                                    current_block['data']['content'].append(row)
                            datablocks.append(current_block.copy())
                        case 'img':
                            current_block['type'] = 'image'
                            current_block['data']['file'] = {}
                            current_block['data']['file']['url'] = str(component)
                            datablocks.append(current_block.copy())
                        case _:
                            current_block['type'] = 'paragraph'
                            current_block['data']['text'] = str(component.contents).strip('[').strip(']')
                            datablocks.append(current_block.copy())
            else:
                current_block['data']['level'] = int(component.name[1])
                current_block['data']['text'] = str(component.contents)
                datablocks.append(current_block.copy())
        return json.dumps({'blocks': datablocks})

def url_from_tryton_to_flask(url, prefix):
    attachment = attachment_from_url(url)
    if not attachment:
        return url
    return prefix + attachment.name

def cid_from_attachment(attachment):
    return hashlib.md5((attachment.name + '/' + str(attachment.id)
            ).encode('utf-8')).hexdigest()

def attachment_from_name(name):
    pool = Pool()
    Attachment = pool.get('ir.attachment')
    attachments = Attachment.search([('name', '=', name)], limit=1)
    if attachments:
        return attachments[0]

def attachment_from_id(id):
    pool = Pool()
    Attachment = pool.get('ir.attachment')
    attachments = Attachment.search([('id', '=', id)], limit=1)
    if attachments:
        return attachments[0]

def attachment_from_url(url):
    if not 'widgets/attachment' in url:
        return
    id_ = url.split('/')[-1]
    try:
        id_ = int(id_)
    except ValueError:
        return
    return attachment_from_id(str(id_))

def migrate_field(sql_table, field, type):
    cursor = Transaction().connection.cursor()
    if type == 'html':
        tool = html_to_js
    else:
        tool = text_to_js
    cursor.execute(*sql_table.select(sql_table.id, field, where=((field != None))))
    records = cursor.fetchall()
    counter = 0
    for id, value in records:
        counter += 1
        if counter % 1000 == 0:
            Transaction().connection.commit()
        if '"blocks"' not in value:
            cursor.execute(*sql_table.update(
                columns=[field],
                values=[tool(value)],
                where=sql_table.id == id
            ))

def has_content(jstext):
    if not jstext:
        return False
    content = json.loads(jstext)
    return bool(content.get('blocks'))
