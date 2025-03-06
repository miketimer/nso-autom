# -*- mode: python; python-indent: 4 -*-
import ncs
import _ncs

def runx(t,xn):
    """Run an XPath xn using transaction t.

    xn can be either a simple string containing an XPath expression or a tuple in which case the first element is the
    XPath expression and the second is a keypath pointing to the context node.
    """
    try:
        ctxt = '/'
        prfx = ''
        if len(xn) == 2:
            x = xn[0]
            ctxt = xn[1]
            prfx = f'{ctxt}: '
        else:
            x = xn
        r = t.xpath_eval_expr(x, trace, ctxt)
        print(f'{prfx}{x} -> {r}')
    except Exception as e:
        print(f'Failed with xpath {x}: {e}')

def xpath(node):
    if type(node) == ncs.maagic.Root:
        return '/'
    elif type(node._parent) == ncs.maagic.Root:
        return '/' + node_full_name(node)
    elif type(node) == ncs.maagic.ListElement:
        return xpath(node._parent) +  xpath_condition(node)
    else:
        return xpath(node._parent) + '/' + node_full_name(node)

def node_name(node):
    return _ncs.hash2str(node._cs_node.tag())

def node_prefix(node):
    return _ncs.ns2prefix(node._cs_node.ns())

def node_full_name(node):
    return node_prefix(node) + ':' + node_name(node)

def xpath_quote(s):
    s = str(s)
    if not "'" in s:
        return "'" + s + "'"
    elif not '"' in s:
        return '"' + s + '"'
    else:
        # for a string with both double and single quotes NSO has non standard behavior - use concat?
        return '"' + s.replace("'", "\\'") + '"'

def child(list_elem, childname):
    if not list_elem._populated:
        list_elem._populate()
    return list_elem._children.get_by_py(list_elem._backend, list_elem, childname)

def one_xpath_condition(list_elem, childname):
    return (node_full_name(child(list_elem, childname))
            + '='
            + xpath_quote(getattr(list_elem, childname))
            )

def xpath_condition(list_elem):
    conditions = [ one_xpath_condition(list_elem, childname) for childname in dir(list_elem)
                if not childname.startswith('__') and child(list_elem, childname)._cs_node.is_key()]
    return '[' + ']['.join(conditions) + ']'
