# Copyright 2012 Christoph Reiter
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from warnings import warn
from ctypes import cast, byref

from pgi.gir import GIConstantInfoPtr, GIArgument


_union_access = [None, "v_boolean", "v_int8", "v_uint8", "v_int16",
                 "v_uint16", "v_int32", "v_uint32", "v_int64", "v_uint64",
                 "v_float", "v_double", None, "v_string", "v_string",
                 None, None, None, None, None, None, None]


def ConstantAttribute(info, namespace, name, lib):
    const = cast(info, GIConstantInfoPtr)

    arg = GIArgument()
    const.get_value(byref(arg))

    const_type = const.get_type()
    tag_type = const_type.tag.value
    const_type.unref()

    value_member = _union_access[tag_type]
    if not value_member:
        warn("Not supported const type", Warning)
        value = None
    else:
        value = getattr(arg, value_member)

    return value
