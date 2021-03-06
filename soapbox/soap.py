# -*- coding: utf-8 -*-
################################################################################

'''
SOAP protocol implementation, dispatchers and client stub.
'''

################################################################################
# Imports


import httplib2
import logging
import os

from urlparse import urlparse

from lxml import etree

from . import settings, soap11, soap12
from .utils import uncapitalize

try:
    from logging import NullHandler
except ImportError:
    from .compat import NullHandler


################################################################################
# Constants


SOAP_HTTP_Transport = 'http://schemas.xmlsoap.org/soap/http'


################################################################################
# Globals


logger = logging.getLogger('soapbox')
logger.addHandler(NullHandler())


################################################################################
# Classes


class SOAPVersion:
    '''
    '''
    SOAP12 = soap12
    SOAP11 = soap11

    @classmethod
    def get_version(cls, namespace):
        '''
        '''
        if namespace == cls.SOAP11.ENVELOPE or namespace == cls.SOAP11.BINDING:
            return cls.SOAP11
        elif  namespace == cls.SOAP12.ENVELOPE or namespace == cls.SOAP12.BINDING:
            return cls.SOAP11
        else:
            raise ValueError("SOAP version with namespace '%s' is not supported." % namespace)

    @classmethod
    def get_version_name(cls, namespace):
        '''
        '''
        version = cls.get_version(namespace)
        return version.__name__


class SOAPError(Exception):
    '''
    '''
    pass


class Service(object):
    '''
    Describes service aggregating informations required for dispatching and
    WSDL generation.
    '''

    def __init__(self, targetNamespace, location, schema, methods,
                 version=SOAPVersion.SOAP11, name='Service'):
        '''
        :param targetNamespace: string
        :param location: string, endpoint url.
        :param schema: xsd.Schema instance.
        :param methods: list of xsd.Methods
        '''
        self.name = name
        self.targetNamespace = targetNamespace
        self.location = location
        self.schema = schema
        self.methods = methods
        self.version = version

    def get_method(self, operationName):
        '''
        '''
        return self.methods[operationName]


class Stub(object):
    '''
    Client stub. Handles only document style calls.
    '''
    SERVICE = None
    SCHEME = 'http'
    HOST = 'www.example.net'

    def __init__(self, username=None, password=None, service=None, location=None, base_url=None):
        '''
        '''
        self.username = username
        self.password = password
        self.service = service if service else self.SERVICE
        if location:
            self.location = location
        elif base_url:
            p = urlparse(base_url)
            self.location = self.service.location % {
                'scheme': p.scheme,
                'host': p.netloc,
            }
        else:
            self.location = self.service.location % {
                'scheme': self.SCHEME,
                'host': self.HOST,
            }
        self.header = None

    def _handle_response(self, method, response, content):
        '''
        '''
        SOAP = self.SERVICE.version
        envelope = SOAP.Envelope.parsexml(content)

        if envelope.Body.Fault:
            code, message = SOAP.parse_fault_message(envelope.Body.Fault)
            error = 'Fault Code: %s, Fault Message: %s' % (code, message)
            logger.error(error)
            raise SOAPError(error)

        self.response_header = None
        if envelope.Header and method.outputHeader:
            self.response_header = envelope.Header.parse_as(method.outputHeader)

        if isinstance(method.output, basestring):
            element = self.SERVICE.schema.get_element_by_name(method.output)
            _type = element._type.__class__
        else:
            _type = method.output

        return envelope.Body.parse_as(_type)

    def call(self, operationName, **kw):
        '''
        :raises: lxml.etree.XMLSyntaxError -- validation problems.
        '''
        SOAP = self.SERVICE.version
        method = self.SERVICE.get_method(operationName)

        if isinstance(method.input, basestring):
            element = self.SERVICE.schema.get_element_by_name(method.input)
            _type = element._type.__class__
        else:
            _type = method.input

        if method.inputHeader:
            header = self.header
            if isinstance(header, dict):
                header = method.inputHeader(**header)
        else:
            header = SOAP.Header()

        parameter = _type(**kw)

        disable_validation = not os.path.exists(settings.CA_CERTIFICATE_FILE)
        http = httplib2.Http(
            ca_certs=settings.CA_CERTIFICATE_FILE,
            disable_ssl_certificate_validation=disable_validation,
            timeout=settings.REQUEST_TIMEOUT,
        )
        if self.username:
            http.add_credentials(self.username, self.password)

        headers = SOAP.build_header(method.soapAction)
        envelope = SOAP.Envelope.response(operationName, parameter, header)

        logger.info('Request \'%s\'...' % self.location)
        logger.debug('Request Headers:\n\n%s\n' % headers)
        logger.debug('Request Envelope:\n\n%s\n' % envelope)
        response, content = http.request(self.location, 'POST',
             body=envelope, headers=headers)
        logger.debug('Response Headers:\n\n%s\n' % response)
        logger.debug('Response Envelope:\n\n%s\n' % content)

        return self._handle_response(method, response, content)


################################################################################
# Dispatcher


def get_django_dispatch(service):
    '''
    '''

    def call_the_method(request, message, soap_action):
        '''
        '''
        from . import xsd

        for method in service.methods:
            if soap_action != method.soapAction:
                continue

            if isinstance(method.input, basestring):
                element = service.schema.elements[method.input]
                # 28/01/2013 SGC
                if service.schema.elementFormDefault == xsd.ElementFormDefault.QUALIFIED:
                    input_object = element._type.parsexml(message, service.schema)
                else:
                    input_object = element._type.parsexml(message)
            else:
                # 28/01/2013 SGC
                if service.schema.elementFormDefault == xsd.ElementFormDefault.QUALIFIED:
                    input_object = method.input.parsexml(message, service.schema)
                else:
                    input_object = method.input.parsexml(message)

            return_object = method.function(request, input_object)
            try:
                tagname = uncapitalize(return_object.__class__.__name__)
                return_object.xml(tagname, namespace=service.schema.targetNamespace,
                                  schema=service.schema)  # Validation.
            except Exception, e:
                raise ValueError(e)

            if isinstance(method.output, basestring):
                tagname = method.output
            else:
                tagname = uncapitalize(return_object.__class__.__name__)
            return tagname, return_object
        raise ValueError('Method not found!')


    def django_dispatch(request):
        '''
        '''
        from django.http import HttpResponse
        from . import py2wsdl

        SOAP = service.version

        if request.method == 'GET' and 'wsdl' in request.GET:
            wsdl = py2wsdl.generate_wsdl(service)
            wsdl = etree.tostring(wsdl, encoding='utf-8', pretty_print=True,
                xml_declaration=True)
            return HttpResponse(wsdl, mimetype='text/xml')

        try:
            xml = request.raw_post_data
            envelope = SOAP.Envelope.parsexml(xml)
            message = envelope.Body.content()
            soap_action = SOAP.determin_soap_action(request)
            tagname, return_object = call_the_method(request, message, soap_action)
            soap_message = SOAP.Envelope.response(tagname, return_object)
            return HttpResponse(soap_message, content_type=SOAP.CONTENT_TYPE)
        except (ValueError, etree.XMLSyntaxError) as e:
            response = SOAP.get_error_response(SOAP.Code.CLIENT, str(e))
        except Exception, e:
            response = SOAP.get_error_response(SOAP.Code.SERVER, str(e))
        return HttpResponse(response, content_type=SOAP.CONTENT_TYPE)

    return django_dispatch


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
