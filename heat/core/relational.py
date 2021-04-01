"""
Functions for relational oprations, i.e. equal/no equal...
"""
from __future__ import annotations

import torch

from .communication import MPI
from .dndarray import DNDarray
from . import _operations
from . import dndarray
from . import types

__all__ = ["eq", "equal", "ge", "gt", "le", "lt", "ne"]


def eq(t1, t2) -> DNDarray:
    """
    Element-wise rich comparison of equality between values from two operands, commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
        The first operand involved in the comparison
    t2: DNDarray or scalar
        The second operand involved in the comparison

    Examples
    ---------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.eq(T1, 3.0)
    tensor([[0, 0],
            [1, 0]])
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.eq(T1, T2)
    tensor([[0, 1],
            [0, 0]])
    """
    res = _operations.__binary_op(torch.eq, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__eq__ = lambda self, other: eq(self, other)
DNDarray.__eq__.__doc__ = eq.__doc__


def equal(t1, t2) -> bool:
    """
    Overall comparison of equality between two ``DNDarrays``. Returns ``True`` if two arrays have the same size and elements,
    and ``False`` otherwise.

    Parameters
    ----------
    t1: DNDarray or scalar
        The first operand involved in the comparison
    t2: DNDarray or scalar
        The second operand involved in the comparison

    Examples
    ---------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.equal(T1, ht.float32([[1, 2],[3, 4]]))
    True
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.eq(T1, T2)
    False
    >>> ht.eq(T1, 3.0)
    False
    """
    result_tensor = _operations.__binary_op(torch.equal, t1, t2)

    if result_tensor.larray.numel() == 1:
        result_value = result_tensor.larray.item()
    else:
        result_value = True

    return result_tensor.comm.allreduce(result_value, MPI.LAND)


def ge(t1, t2) -> DNDarray:
    """
    Element-wise rich greater than or equal comparison between values from operand ``t1`` with respect to values of
    operand ``t2`` (i.e. ``t1>=t2``), not commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
        The first operand to be compared greater than or equal to second operand
    t2: DNDarray or scalar
       The second operand to be compared less than or equal to first operand

    Examples
    -------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.ge(T1, 3.0)
    tensor([[0, 0],
            [1, 1]], dtype=torch.uint8)
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.ge(T1, T2)
    tensor([[0, 1],
            [1, 1]], dtype=torch.uint8)
    """
    res = _operations.__binary_op(torch.ge, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__ge__ = lambda self, other: ge(self, other)
DNDarray.__ge__.__doc__ = ge.__doc__


def gt(t1, t2) -> DNDarray:
    """
    Element-wise rich greater than comparison between values from operand ``t1`` with respect to values of
    operand ``t2`` (i.e. ``t1>t2``), not commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
       The first operand to be compared greater than second operand
    t2: DNDarray or scalar
       The second operand to be compared less than first operand

    Examples
    -------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.gt(T1, 3.0)
    tensor([[0, 0],
            [0, 1]], dtype=torch.uint8)
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.gt(T1, T2)
    tensor([[0, 0],
            [1, 1]], dtype=torch.uint8)
    """
    res = _operations.__binary_op(torch.gt, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__gt__ = lambda self, other: gt(self, other)
DNDarray.__gt__.__doc__ = gt.__doc__


def le(t1, t2) -> DNDarray:
    """
    Element-wise rich less than or equal comparison between values from operand ``t1`` with respect to values of
    operand ``t2`` (i.e. ``t1<=t2``), not commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
       The first operand to be compared less than or equal to second operand
    t2: DNDarray or scalar
       The second operand to be compared greater than or equal to first operand

    Examples
    -------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.le(T1, 3.0)
    tensor([[1, 1],
            [1, 0]], dtype=torch.uint8)
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.le(T1, T2)
    tensor([[1, 1],
            [0, 0]], dtype=torch.uint8)
    """
    res = _operations.__binary_op(torch.le, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__le__ = lambda self, other: le(self, other)
DNDarray.__le__.__doc__ = le.__doc__


def lt(t1, t2) -> DNDarray:
    """
    Element-wise rich less than comparison between values from operand t1 with respect to values of
    operand ``t2`` (i.e. ``t1<t2``), not commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
        The first operand to be compared less than second operand
    t2: DNDarray or scalar
        The second operand to be compared greater than first operand

    Examples
    -------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.lt(T1, 3.0)
    tensor([[1, 1],
            [0, 0]], dtype=torch.uint8)
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.lt(T1, T2)
    tensor([[1, 0],
            [0, 0]], dtype=torch.uint8)
    """
    res = _operations.__binary_op(torch.lt, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__lt__ = lambda self, other: lt(self, other)
DNDarray.__lt__.__doc__ = lt.__doc__


def ne(t1, t2) -> DNDarray:
    """
    Element-wise rich comparison of non-equality between values from two operands, commutative.
    Takes the first and second operand (scalar or ``DNDarray``) whose elements are to be compared as argument.

    Parameters
    ----------
    t1: DNDarray or scalar
        The first operand involved in the comparison
    t2: DNDarray or scalar
        The second operand involved in the comparison

    Examples
    ---------
    >>> import heat as ht
    >>> T1 = ht.float32([[1, 2],[3, 4]])
    >>> ht.ne(T1, 3.0)
    tensor([[1, 1],
            [0, 1]])
    >>> T2 = ht.float32([[2, 2], [2, 2]])
    >>> ht.ne(T1, T2)
    tensor([[1, 0],
            [1, 1]])
    """
    res = _operations.__binary_op(torch.ne, t1, t2)

    if res.dtype != types.bool:
        res = dndarray.DNDarray(
            res.larray.type(torch.bool),
            res.gshape,
            types.bool,
            res.split,
            res.device,
            res.comm,
            res.balanced,
        )

    return res


DNDarray.__ne__ = lambda self, other: ne(self, other)
DNDarray.__ne__.__doc__ = ne.__doc__
