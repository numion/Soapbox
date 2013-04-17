#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


import argparse
import datetime
import jinja2
import logging
import lxml.etree
import textwrap
import zope.dottedname.resolve

from .soap import SOAP_HTTP_Transport, SOAPVersion
from .utils import (
    NAMESPACES,
    capitalize,
    get_get_type,
    Named,
    open_document,
    remove_namespace,
    url_component,
    url_regex,
    url_template,
    use,
)
from .wsdl import get_wsdl_classes, get_by_name
from .xsd2py import XSDLoader, XSDRenderer

try:
    from logging import NullHandler
except ImportError:
    from .compat import NullHandler


################################################################################
# Constants


TEMPLATE_PACKAGE = 'soapbox.templates'


################################################################################
# Globals


logger = logging.getLogger('soapbox')
logger.addHandler(NullHandler())


################################################################################
# Helpers


def get_rendering_environment():
    '''
    '''
    pkg = TEMPLATE_PACKAGE.split('.')
    env = jinja2.Environment(
        extensions=['jinja2.ext.loopcontrols'],
        loader=jinja2.PackageLoader(*pkg),
    )
    env.filters['capitalize'] = capitalize
    env.filters['remove_namespace'] = remove_namespace
    env.filters['url_component'] = url_component
    env.filters['url_regex'] = url_regex
    env.filters['url_template'] = url_template
    env.filters['use'] = use
    env.globals['SOAPTransport'] = SOAP_HTTP_Transport
    env.globals['get_by_name'] = get_by_name
    env.globals['generation_dt'] = datetime.datetime.now()
    return env


class WSDLoader(object):

    def __init__(self, loader=None):
        self.load = loader or open_document
        self.wsdl = get_wsdl_classes(SOAPVersion.SOAP11.BINDING_NAMESPACE)
        self.seen = set()

    def from_location(self, location):
        logger.info('Loading WSDL Document from %r...', location)
        self.seen.add(location)
        return self.from_string(self.load(location))

    def from_string(self, xml):
        xmlelement = lxml.etree.fromstring(xml)
        definitions = self.wsdl.Definitions.parse_xmlelement(xmlelement)
        types = [definitions.types]

        for imp in definitions.imports:
            if imp.location in self.seen:
                continue
            imp_definitions, imp_types = self.from_location(imp.location)

            definitions.messages.extend(imp_definitions.messages)
            definitions.portTypes.extend(imp_definitions.portTypes)
            definitions.bindings.extend(imp_definitions.bindings)
            definitions.services.extend(imp_definitions.services)
            definitions.types = imp_definitions.types
            types.extend(imp_types)

        return definitions, types


def generate(definitions, types, target, loader=None):
    schemas = []
    xsdloader = XSDLoader(loader)
    for t in types:
        if t.schema is not None:
            schemas.extend(xsdloader.from_schema(t.schema))
    schema = XSDRenderer(schemas)()

    named = Named(NAMESPACES)
    env = get_rendering_environment()
    env.filters['type'] = named.type
    env.globals['schema_name'] = named.schema

    tpl = env.get_template('wsdl')
    return tpl.render(
        definitions=definitions,
        schema=schema,
        is_server=bool(target == 'server'),
    )


def from_location(location, target, loader=None):
    definitions, types = WSDLoader(loader).from_location(location)
    return generate(definitions, types, target, loader)


def from_string(xml, target, loader=None):
    definitions, types = WSDLoader(loader).from_string(xml)
    return generate(definitions, types, target, loader)
    

################################################################################
# Program


def parse_arguments():
    '''
    '''
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
            Generates Python code from a WSDL document.

            Code can be generated for a simple HTTP client or a server running
            the Django web framework.
        '''))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-c', '--client', help='Generate code for a client.', action='store_true')
    group.add_argument('-s', '--server', help='Generate code for a server.', action='store_true')
    parser.add_argument('-l', '--loader',
        help='Dotted name of a callable that retrieves the source documents.')
    parser.add_argument('wsdl', help='The path to a WSDL document.')
    return parser.parse_args()


def main():
    '''
    '''
    logging.basicConfig(level=logging.INFO)
    opt = parse_arguments()
    loader = None
    if opt.loader:
        logger.info('Using document loader %r', opt.loader)
        loader = zope.dottedname.resolve.resolve(opt.loader)

    if opt.client:
        logger.info('Generating client code for WSDL document %r...', opt.wsdl)
        print from_location(opt.wsdl, 'client', loader)

    elif opt.server:
        logger.info('Generating server code for WSDL document %r...', opt.wsdl)
        print from_location(opt.wsdl, 'server', loader)


if __name__ == '__main__':
    main()


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
