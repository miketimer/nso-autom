# -*- mode: python; python-indent: 4 -*-
"""
AUTOM config_comparison

This module is used to compare configuration
"""
import mimetypes
import os
import traceback
import xml.etree.ElementTree as ET


def attr_str(key, val):
    """
    Returns for a key value pair (key, val) a string
      key="vval"
    """
    return "{}=\"{}\"".format(key, val)


def element_str(elem):
    """
    Returns for a given element elem
    a string representation of the element
    """
    attrs = sorted(elem.attrib.items())
    astr = ' '.join(attr_str(k, v) for k, v in attrs)
    res = elem.tag
    value = (elem.text or '').strip()
    if astr:
        res += ' ' + astr
    if value:
        res += ' ' + value
    return res


def get_name_space(elem):
    """
    Return namespace of a given element
    """
    if elem is None:
        return None
    name_space = None
    tag = elem.tag
    if tag.__contains__('{') and tag.__contains__('}'):
        name_space = tag[tag.index('{') + 1:tag.index('}')]
    return name_space


def remove_name_space(string):
    """
    Returns an element string and remove the namespace
    if present
    """
    if string is None:
        return None
    if string.__contains__('}'):
        string = string[string.index('}') + 1:]
    return string


def tag_str(elem, parent=None):
    """
    Returns the tag of elem as a string with attributes
    if present
    """
    attrs = sorted(elem.attrib.items())
    astr = ' '.join(attr_str(k, v) for k, v in attrs)
    res = elem.tag
    name_space = get_name_space(elem)
    if name_space is not None:
        res = remove_name_space(res)
        if name_space != get_name_space(parent):
            astr = attr_str('xmlns', name_space) + \
                ((' ' + astr) if astr else '')
    if astr:
        res += ' ' + astr
    return res


def full_str(elem):
    """
    Returns an element as a string
    """
    children = list(elem)
    children_txt = ' '.join(sorted(element_str(child) for child in children))
    res = elem.tag
    if children_txt:
        res += ' ' + children_txt
    return res


class DiffElement:
    """
    class to compute diff of delement
    """
    def __init__(self, element, diff_kbn=' '):
        self.element = element
        self.diff_kbn = diff_kbn
        self.children = []
        self.text1 = ''
        self.text2 = ''
        if diff_kbn in ['-', '+']:
            self.copy_children(element, diff_kbn)

    def copy_children(self, element, diff_kbn):
        """
        Compute diffs of all the children of the element
        and store them in the children attribute
        """
        for child in list(element):
            diff_child = DiffElement(child, diff_kbn)
            self.children.append(diff_child)

    def extend(self, children):
        """
        extend the children attribute list with the
        passed children argument
        """
        self.children.extend(children)

    def append(self, child):
        """
        append child to the children list attribute
        """
        self.children.append(child)

    def to_string(self, level=0, parent=None):
        """
        Convert to string the diff
        """
        _str = ''
        diff_children = self.children
        diff_children.sort(key=lambda ele: tag_str(ele.element, parent))
        children = list(self.element)
        # TODO - @gmuloche - probably can be rewritten:
        # children.sort(key=tag_str)
        children.sort(key=lambda ele: tag_str(ele))
        text = (self.element.text or '').strip()
        tail = (self.element.tail or '').strip()
        indent = self.diff_kbn + ' ' * level

        if diff_children or children or text:
            _str += indent + '<' + tag_str(self.element, parent) + '>\n'

            if text:
                _str += indent + ' ' + text + '\n'

            if not diff_children and children:
                _str += indent + ' ...\n'

            for child in diff_children:
                _str += child.to_string(level + 1, self.element)

            _str += indent + '</' + self.element.tag + '>\n'
        else:
            _str += indent + '<' + tag_str(self.element, parent) + '/>\n'

        if tail:
            _str += indent + tail + '\n'
        return _str


def find_child(_list, target_element, self_list):
    """
    This function goes through the element in _list
    and search for the target_element.

    There could be 0, 1 or more such element

    if there is 0 - return None
    if the is more than 1:
      go through the list of matching elements and if
      full_str of one of those matches full_str of the
      target_element then return it
    if there is only 1:
      go through the anti_element of self_list to look
      if the tag_str of each of those matches the
      unique element found in _list matching target_element
      if only one such element is found then returns the unique
      element (because it is de facto the target_element)
      Otherwise, if the full_str of target_element matches
      full_str of the unique element initially found, return
      this initially found element
      Otherwise return None

    :param _list: a list of elements in which to find target_element
    :param target_element: the target_element
    :param self_list: a list in which we found the target_element initially
                      used to verify further that if we find a unique
                      target element in the _list it is not a false
                      positive.
    :returns: an element of _list matching target_element is found
              otherwise None
    """
    # TODO - @gmuloche - this function may work but it is not
    # easily understandable - I think the usecase result_list == 1
    # is useless here.
    result_list = []
    for element in _list:
        if tag_str(element) == tag_str(target_element):
            result_list.append(element)
    if len(result_list) == 1:
        anti_result_list = []
        for anti_element in self_list:
            if tag_str(anti_element) == tag_str(result_list[0]):
                anti_result_list.append(anti_element)
        if len(anti_result_list) == 1:
            return result_list[0]
        if full_str(target_element) == full_str(result_list[0]):
            return result_list[0]

    elif len(result_list) > 1:
        for element in result_list:
            if full_str(element) == full_str(target_element):
                return element
    return None


def xml_compare(element1, element2, parent=None):
    """
    Compare two xml elements element1 and element2
    return True, None if the element are identical
    return False, <diff> if the elements are different
    """
    result = True
    if element1 is None and element2 is None:
        return True, None
    if element1 is None and element2 is not None:
        return False, DiffElement(element2, '+')
    if element2 is None and element1 is not None:
        return False, DiffElement(element1, '-')

    diff_element = None

    if tag_str(element1, parent) == tag_str(element2, parent):
        diff_element = DiffElement(element1)
        children1 = list(element1)
        children2 = list(element2)

        for child1 in children1:
            child2 = find_child(children2, child1, children1)
            if child2 is None:
                del_element = DiffElement(child1, '-')
                diff_element.append(del_element)
                result = False
            else:
                result_child, diff_child = xml_compare(child1, child2,
                                                       element1)
                if not result_child:
                    result = False
                if diff_child is not None:
                    diff_element.append(diff_child)
                children2.remove(child2)

        for child2 in children2:
            child1 = find_child(children1, child2, children2)
            if child1 is None:
                add_element = DiffElement(child2, '+')
                diff_element.append(add_element)
                result = False

        if element1.text != element2.text:
            if diff_element is None:
                diff_element = DiffElement(element1, '*')
            else:
                diff_element.diff_kbn = '*'
            diff_element.text1 = element1.text
            diff_element.text2 = element2.text
            result = False

    else:
        element = ET.Element('')
        diff_element = DiffElement(element)
        del_element = DiffElement(element1, '-')
        add_element = DiffElement(element2, '+')
        diff_element.append(del_element)
        diff_element.append(add_element)
        result = False

    if diff_element is None:
        diff_element = DiffElement(element1)
    return result, diff_element


def read_and_decode_file(filepath, logger):
    """
    Get an input file, check the extension and attempt to decode it.
    Indeed Cisco configuration are supposed to be utf-8, but other
    types are tried anyway in a best effort fashion.
    :param filepath: path to the file
    :return: None if no encoding manages to decode the file without error.
    """
    # Check extension to rule out all file that are not text files
    # If the extension says that it is not a text file, it will be refused
    # If it cannot be guessed (extension unknown or no extension), we proceed
    # further with trying to open it
    mimetype = mimetypes.guess_type(filepath)[0]
    if mimetype and not mimetype.startswith('text/') and not mimetype.endswith(
            '/xml') and not mimetype.endswith('/json'):
        raise TypeError('Invalid type of file for {}'.format(filepath))

    # Try different encodings
    valid_encodings = [
        'utf_8',
        # following encodings are tried in a best effort fashion
        # their order has been blindly copied blindly from another script
        # TODO: optimise order and maybe do proper charset detection (chardet package?)
        'euc_kr',
        'euc_jp',
        'iso8859_2',
        'latin_1',
        'cp1251',
        'greek8',
        'shift_jis',
        'cp1252',
        'iso_ir_138',
        'cp1256',
        'iso8859_15',
        'iso8859_9',
        'cp1250',
        'cp1254',
        'big5',
        'ascii',
        'utf_16',
        'utf_32',
    ]
    with open(filepath, 'rb') as fd:
        text = fd.read()
        for enc in valid_encodings:
            try:
                res = text.decode(enc)
                logger.debug(
                    u'Successfully decoded file {} with encoding {}'.format(
                        filepath, enc))
                return res
            except UnicodeDecodeError as e:
                logger.debug(u'read_and_decode_file: {} {}'.format(
                    str(e), filepath))
                continue
        logger.error(
            u'read_and_decode_file: NO ENCODING FOUND for {}'.format(filepath))
        # Raising the UnicodeDecodeError again with generic parameters to be
        # caught by main/BDB task
        raise TypeError(
            'No valid encoding found to decode {}'.format(filepath))


def make_html_xml_line(diff_root, level=0, parent=None):
    """
    Convert XML to HTML
    """
    diff_children = diff_root.children
    # diff_children.sort(key=lambda ele: tag_str(ele.element, diff_root.element))

    children = list(diff_root.element)
    # children.sort(key=lambda ele: tag_str(ele, diff_root.element))

    text = (diff_root.element.text or '').strip()
    text1 = (diff_root.text1 or '').strip()
    text2 = (diff_root.text2 or '').strip()
    tail = (diff_root.element.tail or '').strip()
    indent = '  ' * level
    html_txt = ''

    td_style_normal = ('style="border: 1px solid #ccc; border-top-style:none;'
                       'border-bottom-style:none"')
    td_style_green = ('style="border: 1px solid #ccc; border-top-style:none;'
                      'border-bottom-style:none; background: #5CB85C"')
    td_style_red = ('style="border: 1px solid #ccc; border-top-style:none;'
                    'border-bottom-style:none; background: #D9534F"')
    td_style_yellow = ('style="border: 1px solid #ccc; border-top-style:none;'
                       'border-bottom-style:none; background: #FFDC35"')

    if diff_children or children:

        if diff_root.diff_kbn == ' ' or diff_root.diff_kbn == '*':
            html_txt += ('<tr><td ' + td_style_normal + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' +
                         '</td>' + '<td ' + td_style_normal + '>' + indent +
                         '&lt;' + tag_str(diff_root.element, parent) + '&gt;' +
                         '</td></tr>')
        if diff_root.diff_kbn == '-':
            html_txt += ('<tr><td ' + td_style_green + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' +
                         '</td>' + '<td ' + td_style_normal + '></td></tr>')
        if diff_root.diff_kbn == '+':
            html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                         td_style_red + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' +
                         '</td></tr>')
        if diff_root.diff_kbn == '*':
            if text1 == '':
                html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                             td_style_red + '>' + indent + '  ' + text2 +
                             '</td></tr>')
            elif text2 == '':
                html_txt += ('<tr><td ' + td_style_green + '>' + indent +
                             '  ' + text1 + '</td>' + '<td ' +
                             td_style_normal + '></td></tr>')
            else:
                html_txt += ('<tr><td ' + td_style_yellow + '>' + indent +
                             '  ' + text1 + '</td>' + '<td ' +
                             td_style_yellow + '>' + indent + '  ' + text2 +
                             '</td></tr>')
        elif text:
            if diff_root.diff_kbn == ' ':
                html_txt += ('<tr><td ' + td_style_normal + '>' + indent +
                             '  ' + text + '</td>' + '<td ' + td_style_normal +
                             '>' + indent + '  ' + text + '</td></tr>')
            if diff_root.diff_kbn == '-':
                html_txt += ('<tr><td ' + td_style_green + '>' + indent +
                             '  ' + text + '</td>' + '<td ' + td_style_normal +
                             '></td></tr>')
            if diff_root.diff_kbn == '+':
                html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                             td_style_red + '>' + indent + '  ' + text +
                             '</td></tr>')

        if not diff_children and children:
            if diff_root.diff_kbn == '-':
                html_txt += ('<tr><td ' + td_style_green + '>' + indent +
                             '  ' + '...</td>' + '<td ' + td_style_normal +
                             '></td></tr>')
            if diff_root.diff_kbn == '+':
                html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                             td_style_red + '>' + indent + '  ' +
                             '...</td></tr>')

        for child in diff_children:
            html_txt += make_html_xml_line(child, level + 1, diff_root.element)

        if diff_root.diff_kbn == ' ' or diff_root.diff_kbn == '*':
            html_txt += ('<tr><td ' + td_style_normal + '>' + indent +
                         '&lt;/' + remove_name_space(diff_root.element.tag) +
                         '&gt;' + '</td>' + '<td ' + td_style_normal + '>' +
                         indent + '&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td></tr>')
        if diff_root.diff_kbn == '-':
            html_txt += ('<tr><td ' + td_style_green + '>' + indent + '&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td>' + '<td ' + td_style_normal + '></td></tr>')
        if diff_root.diff_kbn == '+':
            html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                         td_style_red + '>' + indent + '&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td></tr>')

    elif text or text1 or text2:
        if diff_root.diff_kbn == ' ':
            html_txt += ('<tr><td ' + td_style_normal + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' + text +
                         '&lt;/' + remove_name_space(diff_root.element.tag) +
                         '&gt;' + '</td>' + '<td ' + td_style_normal + '>' +
                         indent + '&lt;' + tag_str(diff_root.element, parent) +
                         '&gt;' + text + '&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td></tr>')
        if diff_root.diff_kbn == '*':
            html_txt += ('<tr><td ' + td_style_yellow + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) +
                         '&gt;<b style="background: #FF8040">' + text1 +
                         '</b>&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td>' + '<td ' + td_style_yellow + '>' + indent +
                         '&lt;' + tag_str(diff_root.element, parent) +
                         '&gt;<b style="background: #FF8040">' + text2 +
                         '</b>&lt;/' +
                         remove_name_space(diff_root.element.tag) + '&gt;' +
                         '</td></tr>')
        if diff_root.diff_kbn == '-':
            html_txt += ('<tr><td ' + td_style_green + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' + text +
                         '&lt;/' + remove_name_space(diff_root.element.tag) +
                         '&gt;' + '</td>' + '<td ' + td_style_normal +
                         '></td></tr>')
        if diff_root.diff_kbn == '+':
            html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                         td_style_red + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '&gt;' + text +
                         '&lt;/' + remove_name_space(diff_root.element.tag) +
                         '&gt;' + '</td></tr>')
    else:
        if diff_root.diff_kbn == ' ' or diff_root.diff_kbn == '*':
            html_txt += ('<tr><td ' + td_style_normal + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '/&gt;' +
                         '</td>' + '<td ' + td_style_normal + '>' + indent +
                         '&lt;' + tag_str(diff_root.element, parent) +
                         '/&gt;' + '</td></tr>')
        if diff_root.diff_kbn == '-':
            html_txt += ('<tr><td ' + td_style_green + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '/&gt;' +
                         '</td>' + '<td ' + td_style_normal + '></td></tr>')
        if diff_root.diff_kbn == '+':
            html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                         td_style_red + '>' + indent + '&lt;' +
                         tag_str(diff_root.element, parent) + '/&gt;' +
                         '</td></tr>')

    if tail:
        if diff_root.diff_kbn == ' ' or diff_root.diff_kbn == '*':
            html_txt += ('<tr><td ' + td_style_normal + '>' + indent + tail +
                         '</td>' + '<td ' + td_style_normal + '>' + indent +
                         tail + '</td></tr>')
        if diff_root.diff_kbn == '-':
            html_txt += ('<tr><td ' + td_style_green + '>' + indent + tail +
                         '</td>' + '<td ' + td_style_normal + '></td></tr>')
        if diff_root.diff_kbn == '+':
            html_txt += ('<tr><td ' + td_style_normal + '></td>' + '<td ' +
                         td_style_red + '>' + indent + tail + '</td></tr>')
    return html_txt


def make_html_xml(diff_root):
    """
    Convert XML to HTML
    """

    html_txt = ('<table style="font-size: 0.75em; '
                'border-collapse: collapse">')
    html_txt += '<thead><tr>'
    html_txt += ('<th style="background-color: #ddd; border: 1px solid #ccc; '
                 'min-width:200px">Expected</th>')
    html_txt += ('<th style="background-color: #ddd; border: 1px solid #ccc; '
                 ' min-width:200px">Actual</th>')
    html_txt += '</tr></thead>'
    html_txt += '<tbody>'

    if diff_root.element.tag == '':
        for child in diff_root.children:
            html_txt += make_html_xml_line(child)
    else:
        html_txt += make_html_xml_line(diff_root)

    html_txt = html_txt[:html_txt.rfind('<tr>')] + html_txt[
        html_txt.rfind('<tr>'):].replace('; border-bottom-style:none', '')

    html_txt += '</tbody></table>'

    return html_txt


def compare_xml(expected_xml, actual_xml, logger, diff_log_filename, directory):
    """ Compares xml content.
    You can pass the xml as strings or as filenames.
    The keyword fails if the xml content is different, the results are printed
    as table in log.html.
    The keyword also fails if the files do not exist or don't contain valid xml context.
    """
    try:
        expect_root = None
        actual_root = None
        output_directory = os.path.dirname(actual_xml)
        if expected_xml is None or expected_xml == '':
            expect_root = None
        elif os.path.exists(expected_xml):
            expected_xml = read_and_decode_file(expected_xml, logger)
            expect_root = ET.XML(expected_xml)
        else:
            expect_root = ET.XML(expected_xml)

        if actual_xml is None or actual_xml == '':
            actual_root = None
        elif os.path.exists(actual_xml):
            actual_xml = read_and_decode_file(actual_xml, logger)
            actual_root = ET.XML(actual_xml)
        else:
            actual_root = ET.XML(actual_xml)

        result, diff_root = xml_compare(expect_root, actual_root)
        if not result:
            html_content = make_html_xml(diff_root)
            with open(os.path.join(directory, diff_log_filename + '.html'), "w+") as fd:
                fd.write(html_content)
            logger.info(
                'xml comparison failed, please check '+ diff_log_filename + '.html for details')
            return False, fd

        return True, None

    except RuntimeError as e:
        raise e
    except ET.ParseError as e:
        raise RuntimeError('illegal xml. \n' + e.msg) from e
    except BaseException:
        raise AssertionError(traceback.format_exc()) from e
