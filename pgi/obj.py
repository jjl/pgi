# Copyright 2012, 2013 Christoph Reiter
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

import itertools
from ctypes import cast
import weakref

from .clib import gobject
from .clib.gobject import GClosureNotify, signal_connect_data
from .clib.gobject import signal_handler_unblock, signal_handler_block
from .clib.gobject import GConnectFlags, signal_handler_disconnect
from .clib.gir import GIInterfaceInfoPtr, GIFunctionInfoFlags, GIObjectInfoPtr

from .clib.ctypesutil import gicast
from .util import import_attribute, escape_identifier
from .gtype import PGType
from .properties import PropertyAttribute, PROPS_NAME
from .field import FieldAttribute
from .constant import ConstantAttribute
from .signals import SignalsAttribute
from .codegen import generate_function, generate_constructor
from .codegen import generate_signal_callback


class _Object(object):
    pass


class Object(object):

    __gtype__ = None
    _obj = 0
    __weak = {}
    _constructors = None
    __signal_cb_ref = {}

    def __init__(self, **kwargs):
        cls = type(self)
        gtype = cls.__gtype__

        if gtype.is_abstract():
            raise TypeError("Cannot create instance of abstract type %r" %
                            gtype.name)

        names = kwargs.keys()
        obj = generate_constructor(cls, tuple(names))(*kwargs.values())

        # sink unowned objects
        if self._unowned:
            gobject.ref_sink(obj)

        self.__weak[weakref.ref(self, self.__destroy)] = obj
        self._obj = obj

    def set_property(self, name, value):
        """set_property(property_name: str, value: object)

        Set property *property_name* to *value*.
        """

        if not hasattr(self.props, name):
            raise TypeError("Unknown property: %r" % name)
        setattr(self.props, name, value)

    def get_property(self, name):
        """get_property(property_name: str) -> object

        Retrieves a property value.
        """

        if not hasattr(self.props, name):
            raise TypeError("Unknown property: %r" % name)
        return getattr(self.props, name)

    def _ref(self):
        gobject.ref_sink(self._obj)

    @classmethod
    def __destroy(cls, ref):
        gobject.unref(cls.__weak.pop(ref))

    @property
    def __grefcount__(self):
        return cast(self._obj, gobject.GObjectPtr).contents.ref_count

    def __get_signal(self, name):
        name = name.replace("_", "-")
        for base in type(self).__mro__[:-1]:
            if base is InterfaceBase:
                continue
            if "__sigs__" in base.__dict__:
                if name in base.__sigs__:
                    return base.__sigs__[name]

    def __connect(self, flags, name, callback, *user_args):
        if not callable(callback):
            raise TypeError("second argument must be callable")

        info = self.__get_signal(name)
        if not info:
            raise TypeError("unknown signal name %r" % name)

        def _add_self(*args):
            return callback(self, *itertools.chain(args, user_args))
        cb = generate_signal_callback(info)(_add_self)

        destroy = GClosureNotify()
        id_ = signal_connect_data(self._obj, name, cb, None, destroy, flags)
        self.__signal_cb_ref[id_] = (cb, destroy)
        return id_

    def connect(self, detailed_signal, handler, *args):
        """connect(detailed_signal: str, handler: function, *args) -> handler_id: int

        The connect() method adds a function or method (handler) to the end
        of the list of signal handlers for the named detailed_signal but
        before the default class signal handler. An optional set of
        parameters may be specified after the handler parameter. These will
        all be passed to the signal handler when invoked.

        For example if a function handler was connected to a signal using::

            handler_id = object.connect("signal_name", handler, arg1, arg2, arg3)

        The handler should be defined as::

            def handler(object, arg1, arg2, arg3):

        A method handler connected to a signal using::

            handler_id = object.connect("signal_name", self.handler, arg1, arg2)

        requires an additional argument when defined::

            def handler(self, object, arg1, arg2)

        A TypeError exception is raised if detailed_signal identifies a
        signal name that is not associated with the object.
        """

        return self.__connect(0, detailed_signal, handler, *args)

    def connect_after(self, detailed_signal, handler, *args):
        """connect_after(detailed_signal: str, handler: function, *args) -> handler_id: int

        The connect_after() method is similar to the connect() method
        except that the handler is added to the signal handler list after
        the default class signal handler. Otherwise the details of handler
        definition and invocation are the same.
        """

        flags = GConnectFlags.CONNECT_AFTER
        return self.__connect(flags, detailed_signal, handler, *args)

    def disconnect(self, id_):
        if id_ in self.__signal_cb_ref:
            signal_handler_disconnect(self._obj, id_)
            del self.__signal_cb_ref[id_]

    def handler_block(self, handler_id):
        """handler_block(handler_id: int) -> None

        Blocks a handler of an instance so it will not be called during any
        signal emissions unless :meth:`handler_unblock` is called for that
        *handler_id*. Thus "blocking" a signal handler means to temporarily
        deactivate it, a signal handler has to be unblocked exactly the
        same amount of times it has been blocked before to become active
        again.

        It is recommended to use :meth:`handler_block` in conjunction with
        the *with* statement which will call :meth:`handler_unblock`
        implicitly at the end of the block::

            with an_object.handler_block(handler_id):
                # Do your work here
                ...
        """

        signal_handler_block(self._obj, handler_id)

    def handler_unblock(self, handler_id):
        """handler_unblock(handler_id: int) -> None"""

        signal_handler_unblock(self._obj, handler_id)

    def emit(self, signal_name, *args):
        """emit(signal_name: str, *args) -> None

        Emit signal *signal_name*. Signal arguments must follow, e.g. if your
        signal is of type ``(int,)``, it must be emitted with::

            self.emit(signal_name, 42)
        """

        raise NotImplementedError

    def freeze_notify(self):
        """freeze_notify() -> None

        This method freezes all the "notify::" signals (which are emitted
        when any property is changed) until the :meth:`thaw_notify` method
        is called.

        It recommended to use the *with* statement when calling
        :meth:`freeze_notify`, that way it is ensured that
        :meth:`thaw_notify` is called implicitly at the end of the block::

            with an_object.freeze_notify():
                # Do your work here
                ...
        """

        raise NotImplementedError

    def thaw_notify(self):
        """thaw_notify() -> None

        Thaw all the "notify::" signals which were thawed by
        :meth:`freeze_notify`.

        It is recommended to not call :meth:`thaw_notify` explicitly but use
        :meth:`freeze_notify` together with the *with* statement.
        """

        raise NotImplementedError

    def __hash__(self):
        return hash(self._obj)

    def __eq__(self, other):
        return self._obj == other._obj

    def __cmp__(self, other):
        return cmp(self._obj, other._obj)

    def __repr__(self):
        form = "<%s object at 0x%x (%s at 0x%x)>"
        name = type(self).__name__
        return form % (name, id(self), self.__gtype__.name, self._obj)


class MethodAttribute(object):
    def __init__(self, info, real_owner, name):
        super(MethodAttribute, self).__init__()
        self._info = info
        self._name = name
        self._real_owner = real_owner

    def __get__(self, instance, owner):
        info = self._info
        real_owner = self._real_owner
        flags = info.flags
        func_flags = flags.value
        name = self._name

        throws = func_flags & GIFunctionInfoFlags.THROWS

        if func_flags & GIFunctionInfoFlags.IS_METHOD:
            func = generate_function(info, method=True, throws=throws)
            setattr(real_owner, name, func)
            return getattr(instance or owner, name)
        elif not func_flags or func_flags & GIFunctionInfoFlags.IS_CONSTRUCTOR:
            func = generate_function(info, method=False, throws=throws)
            func = staticmethod(func)
            setattr(real_owner, name, func)
            return getattr(owner, name)
        else:
            raise NotImplementedError("%r not supported" % flags)


def add_method(info, target_cls):
    """Add a method to the target class"""

    name = escape_identifier(info.name)
    attr = MethodAttribute(info, target_cls, name)
    setattr(target_cls, name, attr)


class InterfaceBase(object):
    pass

InterfaceBase.__module__ = "GObject"
InterfaceBase.__name__ = "GInterface"


class _Interface(InterfaceBase):
    def __init__(self):
        raise NotImplementedError("Interface can not be constructed")


def InterfaceAttribute(info):
    """Creates a GInterface class"""

    iface_info = gicast(info, GIInterfaceInfoPtr)

    # Create a new class
    cls = type(info.name, _Interface.__bases__, dict(_Interface.__dict__))
    cls.__module__ = iface_info.namespace

    # GType
    cls.__gtype__ = PGType(iface_info.g_type)

    # Properties
    cls.props = PropertyAttribute(iface_info)

    # Signals
    cls.signals = SignalsAttribute()

    # Add constants
    for constant in iface_info.get_constants():
        constant_name = constant.name
        attr = ConstantAttribute(constant)
        setattr(cls, constant_name, attr)

    # Add methods
    for method_info in iface_info.get_methods():
        add_method(method_info, cls)

    cls._sigs = {}

    return cls


def new_class_from_gtype(gtype):
    """Create a new class for a gtype not in the gir.
    The caller is responsible for caching etc.
    """

    if gtype.is_a(PGType.from_name("GObject")):
        parent = gtype.parent.pytype
        if parent is None or parent == PGType.from_name("void"):
            return
        interfaces = [i.pytype for i in gtype.interfaces]
        bases = tuple([parent] + interfaces)

        cls = type(gtype.name, bases, dict(_Object.__dict__))
        cls.__gtype__ = gtype

        return cls
    elif gtype.is_a(PGType.from_name("GEnum")):
        from pgi.enum import EnumBase
        return EnumBase


def ObjectAttribute(obj_info):
    """Creates a GObject class.

    It inherits from the base class and all interfaces it implements.
    """

    obj_info = gicast(obj_info, GIObjectInfoPtr)

    if obj_info.name == "Object" and obj_info.namespace == "GObject":
        cls = Object
    else:
        # Get the parent class
        parent_obj = obj_info.get_parent()
        if parent_obj:
            attr = import_attribute(parent_obj.namespace, parent_obj.name)
            bases = (attr,)
        else:
            bases = _Object.__bases__

        # Get all object interfaces
        ifaces = []
        for interface in obj_info.get_interfaces():
            attr = import_attribute(interface.namespace, interface.name)
            # only add interfaces if the base classes don't have it
            for base in bases:
                if attr in base.__mro__:
                    break
            else:
                ifaces.append(attr)

        # Combine them to a base class list
        if ifaces:
            bases = tuple(list(bases) + ifaces)

        # Create a new class
        cls = type(obj_info.name, bases, dict(_Object.__dict__))

    cls.__module__ = obj_info.namespace

    # Set root to unowned= False and InitiallyUnowned=True
    if obj_info.namespace == "GObject":
        if obj_info.name == "InitiallyUnowned":
            cls._unowned = True
        elif obj_info.name == "Object":
            cls._unowned = False

    # GType
    cls.__gtype__ = PGType(obj_info.g_type)

    # Constructor cache
    cls._constructors = {}

    # Properties
    setattr(cls, PROPS_NAME, PropertyAttribute(obj_info))

    # Signals
    cls.signals = SignalsAttribute()

    # Add constants
    for constant in obj_info.get_constants():
        constant_name = constant.get_name()
        attr = ConstantAttribute(constant)
        setattr(cls, constant_name, attr)

    # Fields
    for field in obj_info.get_fields():
        field_name = escape_identifier(field.name)
        attr = FieldAttribute(field_name, field)
        setattr(cls, field_name, attr)

    # we implement the base object ourself
    if cls is not Object:
        # Add methods
        for method_info in obj_info.get_methods():
            add_method(method_info, cls)

    # Signals
    cls.__sigs__ = {}
    for sig_info in obj_info.get_signals():
        signal_name = sig_info.name
        cls.__sigs__[signal_name] = sig_info

    return cls
