# -*- coding: utf-8 -*-
################################################################################

'''
'''

################################################################################
# Imports


from . import xsd, xsdspec


################################################################################
# Functions


def get_by_name(_list, fullname):
    '''
    '''
    name = fullname.split(':')[-1]
    for item in _list:
        if item.name == name:
            return item
    raise ValueError("Item '%s' not found in list:%s" % (name, _list))


@xsd.localregistry
def get_wsdl_classes(soap_namespace):
    '''
    '''

    class SOAP_Binding(xsd.ComplexType):
        '''
        '''
        style = xsd.Attribute(xsd.String)
        transport = xsd.Attribute(xsd.String)

    class SOAP_Operation(xsd.ComplexType):
        '''
        '''
        soapAction = xsd.Attribute(xsd.String)
        style = xsd.Attribute(xsd.String, use=xsd.Use.OPTIONAL)

    class SOAP_Header(xsd.ComplexType):
        '''
        '''
        message = xsd.Attribute(xsd.String)
        part = xsd.Attribute(xsd.String)
        use = xsd.Attribute(xsd.String)

    class SOAP_Body(xsd.ComplexType):
        '''
        '''
        use = xsd.Attribute(xsd.String)

    class SOAP_Address(xsd.ComplexType):
        '''
        '''
        location = xsd.Attribute(xsd.String)

    SOAP = xsd.Schema(
        targetNamespace=soap_namespace,
        elementFormDefault=xsd.ElementFormDefault.QUALIFIED,
        simpleTypes=[],
        attributeGroups=[],
        groups=[],
        complexTypes=[SOAP_Binding, SOAP_Operation, SOAP_Header, SOAP_Body, SOAP_Address],
        elements={})

    class Types(xsd.ComplexType):
        '''
        '''
        schema = xsdspec.SCHEMA.Element(xsdspec.Schema)

    class Part(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String)
        element = xsd.Attribute(xsd.FQName, use=xsd.Use.OPTIONAL)
        type = xsd.Attribute(xsd.FQName, use=xsd.Use.OPTIONAL)

    class Message(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String)
        parts = xsd.ListElement(Part, 'part', minOccurs=1)

        @property
        def part(self):
            if len(self.parts) != 1:
                raise ValueError('expected exactly one part', self.name, self.parts)
            return self.parts[0]

    class Input(xsd.ComplexType):
        '''
        '''
        message = xsd.Attribute(xsd.String, use=xsd.Use.OPTIONAL)
        headers = SOAP.ListElement(SOAP_Header, 'header', minOccurs=0)
        body = SOAP.Element(SOAP_Body, minOccurs=0)

    class Operation(xsd.ComplexType):
        '''
        '''
        operation = SOAP.Element(SOAP_Operation)
        name = xsd.Attribute(xsd.String)
        input = xsd.Element(Input)
        output = xsd.Element(Input)
        body = SOAP.Element(SOAP_Body)
        binding = xsd.Element('Binding')
        definition = xsd.Element('Definitions')

        def __init__(self, **kwargs):
            '''
            '''
            super(Operation, self).__init__(**kwargs)
            self.binding = None
            self.definition = None

        def render(self, *args, **kwargs):
            '''
            '''
            self.binding = None
            self.definition = None
            super(Operation, self).render(*args, **kwargs)

        def set_definition(self, definition):
            '''
            '''
            self.definition = definition

        def set_binding(self, binding):
            '''
            '''
            self.binding = binding

        def get_InputMessage(self):
            '''
            '''
            portType = self.binding.getPortType()
            portTypeOperation = get_by_name(portType.operations, self.name)
            messageName = portTypeOperation.input.message
            return get_by_name(self.definition.messages, messageName)

        def get_InputMessageHeaders(self):
            '''
            '''
            operation = get_by_name(self.binding.operations, self.name)
            return self._get_parts(operation.input.headers)

        def get_OutputMessage(self):
            '''
            '''
            portType = self.binding.getPortType()
            portTypeOperation = get_by_name(portType.operations, self.name)
            messageName = portTypeOperation.output.message
            return get_by_name(self.definition.messages, messageName)

        def get_OutputMessageHeaders(self):
            '''
            '''
            operation = get_by_name(self.binding.operations, self.name)
            return self._get_parts(operation.output.headers)
        
        def _get_parts(self, references):
            parts = []
            for ref in references:
                message = get_by_name(self.definition.messages, ref.message)
                parts.append(get_by_name(message.parts, ref.part))
            return parts

    class PortType(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String)
        operations = xsd.ListElement(Operation, 'operation')

    class Binding(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String)
        type = xsd.Attribute(xsd.String)
        binding = SOAP.Element(SOAP_Binding)
        operations = xsd.ListElement(Operation, 'operation')
        definition = xsd.Element('Definitions')

        def render(self, *args, **kwargs):
            '''
            '''
            self.definition = None
            super(Binding, self).render(*args, **kwargs)

        def __init__(self, **kwargs):
            '''
            '''
            super(Binding, self).__init__(**kwargs)
            self.definition = None

        def set_definition(self, definition):
            '''
            '''
            self.definition = definition

        def feedback_Operations(self):
            '''
            '''
            for operation in self.operations:
                operation.set_binding(self)

        def getPortType(self):
            '''
            '''
            return get_by_name(self.definition.portTypes, self.type)

    class Port(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String)
        binding = xsd.Attribute(xsd.String)
        address = SOAP.Element(SOAP_Address)

    class Service(xsd.ComplexType):
        '''
        '''
        name = xsd.Attribute(xsd.String, use=xsd.Use.OPTIONAL)
        documentation = xsd.Element(xsd.String)
        ports = xsd.ListElement(Port, 'port')

    class Import(xsd.ComplexType):
        '''
        '''
        namespace = xsd.Attribute(xsd.String)
        location = xsd.Attribute(xsd.String)

    class Definitions(xsd.ComplexType):
        '''
        '''
        targetNamespace = xsd.Attribute(xsd.String)
        types = xsd.Element(Types)
        messages = xsd.ListElement(Message, 'message')
        portTypes = xsd.ListElement(PortType, 'portType')
        bindings = xsd.ListElement(Binding, 'binding')
        services = xsd.ListElement(Service, 'service')
        imports = xsd.ListElement(Import, 'import')


    SCHEMA = xsd.Schema(
        targetNamespace='http://schemas.xmlsoap.org/wsdl/',
        elementFormDefault=xsd.ElementFormDefault.QUALIFIED,
        simpleTypes=[],
        attributeGroups=[],
        groups=[],
        complexTypes=[Types, Part, Message, Input, Operation, PortType, Binding,
                      Port, Service, Import, Definitions],
        elements={})

    class wsdl(object):
        '''
        '''

        def __init__(self):
            '''
            '''
            self.Binding = Binding
            self.Definitions = Definitions
            self.Input = Input
            self.Message = Message
            self.Operation = Operation
            self.Part = Part
            self.Port = Port
            self.PortType = PortType
            self.SOAP_Address = SOAP_Address
            self.SOAP_Binding = SOAP_Binding
            self.SOAP_Header = SOAP_Header
            self.SOAP_Body = SOAP_Body
            self.SOAP_Operation = SOAP_Operation
            self.Service = Service
            self.Types = Types
            self.Import = Import

    return wsdl()


################################################################################
# vim:et:ft=python:nowrap:sts=4:sw=4:ts=4
