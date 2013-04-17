# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


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


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
