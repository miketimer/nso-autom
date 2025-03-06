# -*- mode: python; python-indent: 4 -*-
"""
NSO-ARC helpers xmlns_parser
"""
import xml.etree.ElementTree as ET


def parse_xmlns(file):
    """
    Parse an XML file and returns an ElementTree
    """
    events = "start", "start-ns"
    root = None
    ns_map = []
    for event, elem in ET.iterparse(file, events):

        if event == "start-ns":
            ns_map.append(elem)

        elif event == "start":
            if root is None:
                root = elem
            for prefix, uri in ns_map:
                if prefix != '':
                    elem.set("xmlns:" + prefix, uri)
                else:
                    elem.set("xmlns", uri)
            ns_map = []

    return ET.ElementTree(root)


def fixup_element_prefixes(elem, uri_map, memo):
    """
    For fixing prefixes of xml elements
    input self, ElementTree element, uri_map, memo
    """
    def fixup(name2fix):
        try:
            return memo[name2fix]
        except KeyError:
            if name2fix[0] != "{":
                return None
            uri, tag = name2fix[1:].split("}")
            if uri in uri_map:
                new_name = uri_map[uri] + ":" + tag
                memo[name2fix] = new_name
                return new_name

    # fix element name
    name = fixup(elem.tag)
    if name:
        elem.tag = name
    # fix attribute names
    for key, value in elem.items():
        name = fixup(key)
        if name:
            elem.set(name, value)
            del elem.attrib[key]


def fixup_xmlns(elem, maps=None):
    """
    Fix XML element using namespace maps if required
    """
    if maps is None:
        maps = [{}]

    # check for local overrides
    xmlns = {}
    for key, value in elem.items():
        if key[:6] == "xmlns:":
            xmlns[value] = key[6:]
    if xmlns:
        uri_map = maps[-1].copy()
        uri_map.update(xmlns)
    else:
        uri_map = maps[-1]

    # fixup this element
    fixup_element_prefixes(elem, uri_map, {})

    # process elements
    maps.append(uri_map)
    for child in elem:
        fixup_xmlns(child, maps)
    maps.pop()


def write_xmlns(elem, file):
    """
    For writing the XML file including the original namespaces to file

    input self, ElementTree element, file
    """
    if not ET.iselement(elem):
        elem = elem.getroot()
    fixup_xmlns(elem)
    ET.ElementTree(elem).write(file)
