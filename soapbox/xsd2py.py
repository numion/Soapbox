#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


import argparse
import functools
import itertools
import jinja2
import keyword
import logging
import lxml.etree
import operator
import textwrap
import zope.dottedname.resolve

from .xsdspec import Schema
from .utils import (
    NAMESPACES,
    capitalize,
    Named,
    notbuiltin,
    open_document,
    remove_namespace,
    split_qname,
    toposort_full,
    url_template,
    use,
)

try:
    from logging import NullHandler
except ImportError:
    from .compat import NullHandler


################################################################################
# Constants


TEMPLATE_PACKAGE = 'soapbox.templates'
TEMPLATE_PREAMBLE = """\
from soapbox import xsd
from soapbox.utils import dict2object

_ = dict2object(globals())

"""


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
    env.filters['url_template'] = url_template
    env.filters['use'] = use
    env.globals['keywords'] = keyword.kwlist
    return env


def simple_type_depends_on(st):
    if st.restriction:
        yield st.restriction.base


def complex_type_depends_on(ct):
    content = ct
    if ct.complexContent:
        if ct.complexContent.restriction:
            content = ct.complexContent.restriction
        else:
            content = ct.complexContent.extension
        yield content.base
    for attribute in content.attributes:
        if attribute.ref:
            yield attribute.ref
        else:
            yield attribute.type
    for attrGroupRef in content.attributeGroups:
        yield attrGroupRef.ref
    if content.sequence:
        elements = content.sequence.elements
    elif content.all:
        elements = content.all.elements
    #~ elif content.choice:
        #~ elements = content.choice.elements
    else:
        elements = ()
    for element in elements:
        if element.type:
            yield element.type
        if element.simpleType:
            yield element.simpleType.restriction.base
        if element.ref:
            yield element.ref


def group_depends_on(g):
    for element in g.sequence.elements:
        if element.ref:
            yield element.ref
        yield element.type


def attribute_group_depends_on(g):
    for attribute in g.attributes:
        yield attribute.type


def element_depends_on(element):
    if element.complexType:
        for dep in complex_type_depends_on(element.complexType):
            yield dep


class XSDLoader(object):

    def __init__(self, loader=None):
        self.known_namespaces = set()
        self.load = loader or open_document

    def from_location(self, location):
        logger.info('Loading XSD Document from %r...', location)
        return self.from_string(self.load(location))

    def from_string(self, xml):
        xmlelement = lxml.etree.fromstring(xml)
        schema = Schema.parse_xmlelement(xmlelement)
        for elt in self.from_schema(schema):
            yield elt

    def from_schema(self, schema):
        if schema.targetNamespace in self.known_namespaces:
            return
        self.known_namespaces.add(schema.targetNamespace)
        for xsdimport in schema.imports:
            for elt in self.from_location(xsdimport.schemaLocation):
                yield elt
        yield schema


class XSDRenderer(object):

    def __init__(self, schemas):
        self.schemas = {schema.targetNamespace: schema for schema in schemas}
        self.objects = {}
        self.dependencies = {}
        self.references = set()
        self.modules = []
        self.rendered = []

    def load(self):
        for schema in self.schemas.values():
            for group, depends_on, tag in (
                (schema.simpleTypes, simple_type_depends_on, 'simple'),
                (schema.groups, group_depends_on, 'group'),
                (schema.attributeGroups, attribute_group_depends_on, 'attribute_group'),
                (schema.complexTypes, complex_type_depends_on, 'complex'),
                (schema.elements, element_depends_on, 'element'),
                ):
                for element in group:
                    qname = (schema.targetNamespace, element.name)
                    if qname in self.objects:
                        if tag == 'element':
                            continue
                        raise ValueError('Duplicate type definition', qname, tag, self.objects[qname][1])
                    self.objects[qname] = (element, tag)
                    self.dependencies[qname] = set(
                        filter(notbuiltin, map(split_qname, depends_on(element))))

    def sort(self):
        elements = list(toposort_full(self.dependencies, self.references))

        seen = set()
        for namespace, elementset in itertools.groupby(reversed(elements),
            key=operator.itemgetter(0)):
            schema = None
            if namespace not in seen:
                schema = self.schemas[namespace]
            self.modules.append((schema, namespace, reversed(list(elementset))))
            seen.add(namespace)
        self.modules.reverse()
        for namespace in set(self.schemas) - seen:
            self.modules.append((self.schemas[namespace], namespace, []))
        seen = set()
        for schema, namespace, elementset in self.modules:
            if schema is None:
                continue
            for imp in schema.imports[:]:
                if imp.namespace not in seen:
                    schema.imports.remove(imp)
            seen.add(schema.targetNamespace)

    def render(self):
        for schema, namespace, elements in self.modules:
            elements = [self.objects[qname] for qname in elements]
            named = Named(NAMESPACES, self.references)

            env = get_rendering_environment()
            env.filters['type'] = named.type
            env.filters['typeref'] = named.type
            env.globals['schema_name'] = named.schema
            env.globals['render_complex_type'] = functools.partial(self.render_complex_type, env)
            tpl = env.get_template('xsd')
            self.rendered.append(tpl.render(schema=schema, namespace=namespace, xsd_elements=elements))

    @staticmethod
    def render_complex_type(env, ct, name):
        tpl = env.get_template('xsd-complex-type')
        return tpl.render(ct=ct, name=name)

    def __call__(self, preamble=True):
        self.load()
        self.sort()
        if preamble:
            self.rendered.append(TEMPLATE_PREAMBLE)
        self.render()
        return ''.join(self.rendered)


def from_string(xml, loader=None):
    schemas = XSDLoader(loader).from_string(xml)
    return XSDRenderer(schemas)()


def from_location(location, loader=None):
    schemas = XSDLoader(loader).from_location(location)
    return XSDRenderer(schemas)()


################################################################################
# Program


def parse_arguments():
    '''
    '''
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
            Generates Python code from an XSD document.
        '''))
    parser.add_argument('xsd', help='The path to an XSD document.')
    parser.add_argument('-l', '--loader',
        help='Dotted name of a callable that retrieves the source documents.')
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
    logger.info('Generating code for XSD document %r...', opt.xsd)
    print from_location(opt.xsd, loader)


if __name__ == '__main__':
    main()


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
