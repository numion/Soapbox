# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


import hashlib
import httplib2
import logging
import os

from urlparse import urlparse, urlunparse

from . import settings, xsd

try:
    from logging import NullHandler
except ImportError:
    from .compat import NullHandler


################################################################################
# Globals


logger = logging.getLogger('soapbox')
logger.addHandler(NullHandler())

NAMESPACES = {
    'http://www.w3.org/2000/10/XMLSchema': 'xsd',
    'http://www.w3.org/2001/XMLSchema': 'xsd',
}

################################################################################
# File Functions


def open_document(path):
    '''
    '''
    logger.info('Opening document \'%s\'...' % path)
    # Handle documents available on the Internet:
    if path.startswith(('http:', 'https:')):
        disable_validation = not os.path.exists(settings.CA_CERTIFICATE_FILE)
        http = httplib2.Http(
            ca_certs=settings.CA_CERTIFICATE_FILE,
            disable_ssl_certificate_validation=disable_validation,
            timeout=settings.REQUEST_TIMEOUT,
        )
        _, content = http.request(path)
        return content

    # Attempt to open the document from the filesystem:
    else:
        return open(path, 'r').read()


################################################################################
# Template Filters


def remove_namespace(full_typename):
    '''
    '''
    if not full_typename:
        return None
    return split_qname(full_typename)[1]


def capitalize(value):
    '''
    '''
    return value[0].upper() + value[1:]


def uncapitalize(value):
    '''
    '''
    if value == 'QName':
        return value
    return value[0].lower() + value[1:]


def get_get_type(namespaces):
    '''
    '''
    def get_type(full_typename):
        '''
        '''
        if not full_typename:
            return None
        ns, typename = split_qname(full_typename)
        if ns in namespaces:
            return '%s.%s' % (namespaces[ns], capitalize(typename))
        else:
            return '\'%s\'' % capitalize(typename)
    return get_type


def use(usevalue):
    '''
    '''
    if usevalue == xsd.Use.OPTIONAL:
        return 'xsd.Use.OPTIONAL'
    elif usevalue == xsd.Use.REQUIRED:
        return 'xsd.Use.REQUIRED'
    elif usevalue == xsd.Use.PROHIBITED:
        return 'xsd.Use.PROHIBITED'
    else:
        raise ValueError


def url_regex(url):
    '''
    http://example.net/ws/endpoint --> ^ws/endpoint$
    '''
    o = urlparse(url)
    return r'^%s$' % o.path.lstrip('/')


def url_component(url, item):
    '''
    '''
    parts = urlparse(url)
    try:
        return getattr(parts, item)
    except AttributeError:
        raise ValueError('Unknown URL component: %s' % item)


def url_template(url):
    '''
    http://example.net/ws/endpoint --> %s/ws/endpoint
    '''
    o = list(urlparse(url))
    o[0:2] = ['%(scheme)s', '%(host)s']
    return urlunparse(o)


################################################################################
# Other Functions


def split_qname(qname):
    ns, sep, name = qname.partition('}')
    if not sep:
        return None, qname
    return ns.lstrip('{'), name


def notbuiltin(qname):
    ns, name = qname
    return NAMESPACES.get(ns) != 'xsd'


def schema_name(namespace):
    '''
    '''
    return hashlib.sha512(namespace).hexdigest()[0:5]


def toposort(index):
    while True:
        free = set(index) - set(elt for elt, dep in index.iteritems() if dep)
        if not free:
            break
        for elt in sorted(free):
            yield elt
            index.pop(elt)
        for dep in index.itervalues():
            dep.difference_update(free)


def cycles(dependencies, k, seen):
    seen.append(k)
    for p in tuple(dependencies[k]):
        if p in seen:
            yield p
        else:
            for pp in cycles(dependencies, p, seen):
                yield pp
    seen.pop()


def toposort_full(dependencies, references):
    elements = list(toposort(dependencies))
    while dependencies:
        for qname in cycles(dependencies, dependencies.keys()[0], []):
            references.add(qname)
            for dep in dependencies.values():
                dep.discard(qname)
        elements.extend(toposort(dependencies))
    return elements


class dict2object(object):
    
    def __init__(self, d):
        self._d = d

    def __getattr__(self, name):
        return self._d[name]


class Named(object):

    def __init__(self, external_namespaces=None, references=None):
        self.external_namespaces = external_namespaces or NAMESPACES
        self.references = references or ()

    def schema(self, namespace):
        name = 'Schema_' + schema_name(namespace)
        if namespace not in self.external_namespaces:
            return name
        module = self.external_namespaces[namespace]
        return '{}.{}'.format(module, name)

    def type(self, qname):
        qname = split_qname(qname)
        namespace, name = qname
        name = capitalize(name)
        if namespace not in self.external_namespaces and qname not in self.references:
            return '_.' + name
        module = self.external_namespaces.get(namespace)
        if module:
            name = '{}.{}'.format(module, name)
        if qname in self.references:
            return repr(name)
        return name


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
