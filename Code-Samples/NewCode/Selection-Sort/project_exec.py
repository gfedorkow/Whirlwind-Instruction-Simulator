# project-specific python
# These project-specific files would usually contain functions called by .exec statements
# embedded in ww source code.

import wwinfra

# Undo the ones-complement
def py_int(ww_int):
    if ww_int & 0o100000:
        py_int = -(ww_int ^ 0o177777)
    else:
        py_int = ww_int
    return py_int