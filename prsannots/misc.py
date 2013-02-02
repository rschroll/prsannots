# Copyright 2013 Robert Schroll
#
# This file is part of prsannots and is distributed under the terms of
# the LGPL license.  See the file COPYING for full details.

import sys
import locale

def u_raw_input(prompt):
    """raw_input with unicode encoding/decoding."""
    return raw_input(prompt.encode(sys.stdout.encoding, 'replace')).decode(sys.stdin.encoding)

def u_print(u_string, stream=sys.stdout):
    """print a unicode string with proper encoding, replacing invalid characters"""
    # If the output stream has an encoding, use that.  If not (pipe or redirection
    # to a file, e.g.), use preferred encoding
    encoding = stream.encoding or locale.getpreferredencoding()
    print >>stream, u_string.encode(encoding, 'replace')

# In Python 2, sys.argv[i] is a byte string, not unicode.  If we want to use
# unicode internally (we do!), we must decode them.  But how are they encoded?
# This thread (http://bytes.com/topic/python/answers/165281-what-encoding-used-when-initializing-sys-argv)
# says that on Windows, the 'mbcs' encoding will pick the right one.  If that
# encoding is available, we'll assume we're on Windows and use it.  Otherwise,
# we'll use locale.getpreferredencoding().
try:
    'a'.decode('mbcs')
except LookupError:
    argenc = locale.getpreferredencoding()
else:
    argenc = 'mbcs'

u_argv = [arg.decode(argenc) for arg in sys.argv]
