# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


from lxml import etree

from . import xsd


################################################################################
# Constants


ENVELOPE_NAMESPACE = 'http://schemas.xmlsoap.org/soap/envelope/'
BINDING_NAMESPACE = 'http://schemas.xmlsoap.org/wsdl/soap/'
CONTENT_TYPE = 'text/xml'


################################################################################
# Functions


def determin_soap_action(request):
    '''
    '''
    if request.META.get('HTTP_SOAPACTION'):
        return request.META.get('HTTP_SOAPACTION').replace('"', '')
    elif request.META.get('HTTP_ACTION'):
        return request.META.get('HTTP_ACTION').replace('"', '')
    else:
        return None


def get_error_response(code, message):
    '''
    '''
    return Envelope.error_response(code, message)


def parse_fault_message(fault):
    '''
    '''
    return fault.faultcode, fault.faultstring


def build_header(soapAction):
    '''
    '''
    return {'content-type': CONTENT_TYPE, 'SOAPAction': soapAction}


################################################################################
# Classes


class Code:
    '''
    '''
    CLIENT = 'Client'
    SERVER = 'Server'


class Header(xsd.ComplexType):
    '''
    SOAP Envelope Header.
    '''
    def accept(self, value):
        return value

    def parse_as(self, ContentType):
        return ContentType.parse_xmlelement(self._xmlelement,
            namespace=ContentType.SCHEMA.targetNamespace)

    def render(self, parent, instance, namespace=None):
        return instance.render(parent, instance,
            namespace=instance.SCHEMA.targetNamespace)


class Fault(xsd.ComplexType):
    '''
    SOAP Envelope Fault.
    '''
    faultcode = xsd.Element(xsd.String)
    faultstring = xsd.Element(xsd.String)


class Body(xsd.ComplexType):
    '''
    SOAP Envelope Body.
    '''
    message = xsd.ClassNamedElement(xsd.NamedType, minOccurs=0)
    Fault = xsd.Element(Fault, minOccurs=0, namespace=ENVELOPE_NAMESPACE)

    def parse_as(self, ContentType):
        return ContentType.parse_xmlelement(self._xmlelement[0])

    def content(self):
        '''
        '''
        return etree.tostring(self._xmlelement[0], pretty_print=True)


class Envelope(xsd.ComplexType):
    '''
    SOAP Envelope.
    '''
    Header = xsd.Element(Header, nillable=True, namespace=ENVELOPE_NAMESPACE)
    Body = xsd.Element(Body, namespace=ENVELOPE_NAMESPACE)

    @classmethod
    def response(cls, tagname, return_object, header=None):
        '''
        '''
        envelope = cls()
        if header is not None:
            envelope.Header = header
        envelope.Body = Body()
        envelope.Body.message = xsd.NamedType(name=tagname, value=return_object)

        return envelope.xml('Envelope', namespace=ENVELOPE_NAMESPACE)

    @classmethod
    def error_response(cls, code, message, header=None):
        envelope = cls()
        if header is not None:
            envelope.Header = header
        envelope.Body = Body()
        envelope.Body.Fault = Fault(faultcode=code, faultstring=message)
    
        return envelope.xml('Envelope', namespace=ENVELOPE_NAMESPACE)


SCHEMA = xsd.Schema(
    targetNamespace=ENVELOPE_NAMESPACE,
    elementFormDefault=xsd.ElementFormDefault.UNQUALIFIED,
    complexTypes=[Header, Body, Envelope, Fault],
)

################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
