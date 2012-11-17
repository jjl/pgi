# Copyright 2012 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

from ctypes import Union
from pgi.glib import gboolean, gint8, guint8, gint16, guint16, gint32, guint32
from pgi.glib import gint64, guint64, gfloat, gdouble, gshort, gushort, gint
from pgi.glib import guint, glong, gulong, gsize, gchar_p, gpointer


class GIArgument(Union):
    _fields_ = [
        ("v_boolean", gboolean),
        ("v_int8", gint8),
        ("v_uint8", guint8),
        ("v_int16", gint16),
        ("v_uint16", guint16),
        ("v_int32", gint32),
        ("v_uint32", guint32),
        ("v_int64", gint64),
        ("v_uint64", guint64),
        ("v_float", gfloat),
        ("v_double", gdouble),
        ("v_short", gshort),
        ("v_ushort", gushort),
        ("v_int", gint),
        ("v_uint", guint),
        ("v_long", glong),
        ("v_ulong", gulong),
        ("v_ssize", gsize),
        ("v_string", gchar_p),
        ("v_pointer", gpointer),
    ]

__all__ = ["GIArgument"]