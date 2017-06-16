# Copyright (c) 2008-2015 MetPy Developers.
# Distributed under the terms of the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause
"""Contains calculation of kinematic parameters (e.g. divergence or vorticity)."""
from __future__ import division

import functools
import warnings

import numpy as np

from ..calc import log_interp
from ..cbook import is_string_like, iterable
from ..constants import g
from ..package_tools import Exporter
from ..units import atleast_2d, check_units, concatenate, units

exporter = Exporter(globals())


def _gradient(f, *args, **kwargs):
    """Wrap :func:`numpy.gradient` to handle units."""
    if len(args) < f.ndim:
        args = list(args)
        args.extend([units.Quantity(1., 'dimensionless')] * (f.ndim - len(args)))
    grad = np.gradient(f, *(a.magnitude for a in args), **kwargs)
    if f.ndim == 1:
        return units.Quantity(grad, f.units / args[0].units)
    return [units.Quantity(g, f.units / dx.units) for dx, g in zip(args, grad)]


def _stack(arrs):
    return concatenate([a[np.newaxis] for a in arrs], axis=0)


def _get_gradients(u, v, dx, dy):
    """Return derivatives for components to simplify calculating convergence and vorticity."""
    dudy, dudx = _gradient(u, dy, dx)
    dvdy, dvdx = _gradient(v, dy, dx)
    return dudx, dudy, dvdx, dvdy


def _is_x_first_dim(dim_order):
    """Determine whether x is the first dimension based on the value of dim_order."""
    if dim_order is None:
        warnings.warn('dim_order is using the default setting (currently "xy"). This will '
                      'change to "yx" in the next version. It is recommended that you '
                      'specify the appropriate ordering ("xy", "yx") for your data by '
                      'passing the `dim_order` argument to the calculation.', FutureWarning)
        dim_order = 'xy'
    return dim_order == 'xy'


def _check_and_flip(arr):
    """Transpose array or list of arrays if they are 2D."""
    if hasattr(arr, 'ndim'):
        if arr.ndim >= 2:
            return arr.T
        else:
            return arr
    elif not is_string_like(arr) and iterable(arr):
        return tuple(_check_and_flip(a) for a in arr)
    else:
        return arr


def ensure_yx_order(func):
    """Wrap a function to ensure all array arguments are y, x ordered, based on kwarg."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check what order we're given
        dim_order = kwargs.pop('dim_order', None)
        x_first = _is_x_first_dim(dim_order)

        # If x is the first dimension, flip (transpose) every array within the function args.
        if x_first:
            args = tuple(_check_and_flip(arr) for arr in args)
            for k, v in kwargs:
                kwargs[k] = _check_and_flip(v)

        ret = func(*args, **kwargs)

        # If we flipped on the way in, need to flip on the way out so that output array(s)
        # match the dimension order of the original input.
        if x_first:
            return _check_and_flip(ret)
        else:
            return ret

    # Inject a docstring for the dim_order argument into the function's docstring.
    dim_order_doc = """
    dim_order : str or ``None``, optional
        The ordering of dimensions in passed in arrays. Can be one of ``None``, ``'xy'``,
        or ``'yx'``. ``'xy'`` indicates that the dimension corresponding to x is the leading
        dimension, followed by y. ``'yx'`` indicates that x is the last dimension, preceded
        by y. ``None`` indicates that the default ordering should be assumed,
        which will change in version 0.6 from 'xy' to 'yx'. Can only be passed as a keyword
        argument, i.e. func(..., dim_order='xy')."""

    # Find the first blank line after the start of the parameters section
    params = wrapper.__doc__.find('Parameters')
    blank = wrapper.__doc__.find('\n\n', params)
    wrapper.__doc__ = wrapper.__doc__[:blank] + dim_order_doc + wrapper.__doc__[blank:]

    return wrapper


@exporter.export
@ensure_yx_order
def v_vorticity(u, v, dx, dy):
    r"""Calculate the vertical vorticity of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    (M, N) ndarray
        vertical vorticity

    See Also
    --------
    h_convergence, convergence_vorticity

    """
    _, dudy, dvdx, _ = _get_gradients(u, v, dx, dy)
    return dvdx - dudy


@exporter.export
@ensure_yx_order
def h_convergence(u, v, dx, dy):
    r"""Calculate the horizontal convergence of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    (M, N) ndarray
        The horizontal convergence

    See Also
    --------
    v_vorticity, convergence_vorticity

    """
    dudx, _, _, dvdy = _get_gradients(u, v, dx, dy)
    return dudx + dvdy


@exporter.export
@ensure_yx_order
def convergence_vorticity(u, v, dx, dy):
    r"""Calculate the horizontal convergence and vertical vorticity of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    convergence, vorticity : tuple of (M, N) ndarrays
        The horizontal convergence and vertical vorticity, respectively

    See Also
    --------
    v_vorticity, h_convergence

    Notes
    -----
    This is a convenience function that will do less work than calculating
    the horizontal convergence and vertical vorticity separately.

    """
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return dudx + dvdy, dvdx - dudy


@exporter.export
@ensure_yx_order
def shearing_deformation(u, v, dx, dy):
    r"""Calculate the shearing deformation of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    (M, N) ndarray
        Shearing Deformation

    See Also
    --------
    stretching_convergence, shearing_stretching_deformation

    """
    _, dudy, dvdx, _ = _get_gradients(u, v, dx, dy)
    return dvdx + dudy


@exporter.export
@ensure_yx_order
def stretching_deformation(u, v, dx, dy):
    r"""Calculate the stretching deformation of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    (M, N) ndarray
        Stretching Deformation

    See Also
    --------
    shearing_deformation, shearing_stretching_deformation

    """
    dudx, _, _, dvdy = _get_gradients(u, v, dx, dy)
    return dudx - dvdy


@exporter.export
@ensure_yx_order
def shearing_stretching_deformation(u, v, dx, dy):
    r"""Calculate the horizontal shearing and stretching deformation of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    shearing, strectching : tuple of (M, N) ndarrays
        The horizontal shearing and stretching deformation, respectively

    See Also
    --------
    shearing_deformation, stretching_deformation

    Notes
    -----
    This is a convenience function that will do less work than calculating
    the shearing and streching deformation terms separately.

    """
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return dvdx + dudy, dudx - dvdy


@exporter.export
@ensure_yx_order
def total_deformation(u, v, dx, dy):
    r"""Calculate the horizontal total deformation of the horizontal wind.

    The grid must have a constant spacing in each direction.

    Parameters
    ----------
    u : (M, N) ndarray
        x component of the wind
    v : (M, N) ndarray
        y component of the wind
    dx : float
        The grid spacing in the x-direction
    dy : float
        The grid spacing in the y-direction

    Returns
    -------
    (M, N) ndarray
        Total Deformation

    See Also
    --------
    shearing_deformation, stretching_deformation, shearing_stretching_deformation

    Notes
    -----
    This is a convenience function that will do less work than calculating
    the shearing and streching deformation terms separately and calculating the
    total deformation "by hand".

    """
    dudx, dudy, dvdx, dvdy = _get_gradients(u, v, dx, dy)
    return np.sqrt((dvdx + dudy)**2 + (dudx - dvdy)**2)


@exporter.export
@ensure_yx_order
def advection(scalar, wind, deltas):
    r"""Calculate the advection of a scalar field by the wind.

    The order of the dimensions of the arrays must match the order in which
    the wind components are given.  For example, if the winds are given [u, v],
    then the scalar and wind arrays must be indexed as x,y (which puts x as the
    rows, not columns).

    Parameters
    ----------
    scalar : N-dimensional array
        Array (with N-dimensions) with the quantity to be advected.
    wind : sequence of arrays
        Length N sequence of N-dimensional arrays.  Represents the flow,
        with a component of the wind in each dimension.  For example, for
        horizontal advection, this could be a list: [u, v], where u and v
        are each a 2-dimensional array.
    deltas : sequence
        A (length N) sequence containing the grid spacing in each dimension.

    Returns
    -------
    N-dimensional array
        An N-dimensional array containing the advection at all grid points.

    """
    # This allows passing in a list of wind components or an array.
    wind = _stack(wind)

    # If we have more than one component, we need to reverse the order along the first
    # dimension so that the wind components line up with the
    # order of the gradients from the ..., y, x ordered array.
    if wind.ndim > scalar.ndim:
        wind = wind[::-1]

    # Gradient returns a list of derivatives along each dimension. We convert
    # this to an array with dimension as the first index. Reverse the deltas to line up
    # with the order of the dimensions.
    grad = _stack(_gradient(scalar, *deltas[::-1]))

    # Make them be at least 2D (handling the 1D case) so that we can do the
    # multiply and sum below
    grad, wind = atleast_2d(grad, wind)

    return (-grad * wind).sum(axis=0)


@exporter.export
@ensure_yx_order
def geostrophic_wind(heights, f, dx, dy):
    r"""Calculate the geostrophic wind given from the heights or geopotential.

    Parameters
    ----------
    heights : (M, N) ndarray
        The height field, with either leading dimensions of (x, y) or trailing dimensions
        of (y, x), depending on the value of ``dim_order``.
    f : array_like
        The coriolis parameter.  This can be a scalar to be applied
        everywhere or an array of values.
    dx : scalar
        The grid spacing in the x-direction
    dy : scalar
        The grid spacing in the y-direction

    Returns
    -------
    A 2-item tuple of arrays
        A tuple of the u-component and v-component of the geostrophic wind.

    """
    if heights.dimensionality['[length]'] == 2.0:
        norm_factor = 1. / f
    else:
        norm_factor = g / f

    # If heights has more than 2 dimensions, we need to pass in some dummy
    # grid deltas so that we can still use np.gradient. It may be better to
    # to loop in this case, but that remains to be done.
    deltas = [dy, dx]
    if heights.ndim > 2:
        deltas = [units.Quantity(1., units.m)] * (heights.ndim - 2) + deltas

    grad = _gradient(heights, *deltas)
    dy, dx = grad[-2:]  # Throw away unused gradient components
    return -norm_factor * dy, norm_factor * dx


@exporter.export
@check_units('[speed]', '[speed]', '[pressure]', '[length]',
             '[length]', '[length]', '[speed]', '[speed]')
def storm_relative_helicity(u, v, p, srh_top, hgt, srh_bottom=0, storm_u=0 * units('m/s'),
                            storm_v=0 * units('m/s'), dp=-1, exact=True):
    r"""Calculate Storm Relative Helicity.

    Needs u and v wind components, heights and pressures,
    and top and bottom of SRH layer. An optional storm
    motion vector can be specified.

    Parameters
    ----------
    srh_top : number
        The height of the top of the desired layer for SRH.
    srh_bottom : number
        The height at the bottom of the SRH layer. Default is sfc.
    hgts : array-like
        The heights associatd with the data, provided in meters above mean
        sea level and converted into meters AGL.
    u : array-like
        The u components of winds, same length as hgts
    v : array-like
        The u components of winds, same length as hgts
    p : array-like
        Pressure in hPa, same length as hgts
    storm_u : number
        u component of storm motion
    storm_v : number
        v component of storm motion
    dp : negative integer
        Pressure interval to interpolate the winds over.
    exact: bool (optional, default = True)
        switch between faster interpolated data and slower exact data

    Returns
    -------
    number
        p_srh : positive storm-relative helicity
    number
        n_srh : negative storm-relative helicity
    number
        T_srh : total storm-relative helicity

    """
    u = u.to('meters/second')
    v = v.to('meters/second')
    storm_u = storm_u.to('meters/second')
    storm_v = storm_v.to('meters/second')

    if hasattr(p, 'units'):
        p = p.magnitude

    if hasattr(u, 'units'):
        u = u.magnitude

    if hasattr(v, 'units'):
        v = v.magnitude

    if hasattr(storm_u, 'units'):
        storm_u = storm_u.magnitude

    if hasattr(storm_v, 'units'):
        storm_v = storm_v.magnitude

    p_srh_top = np.interp(srh_top, hgt - hgt[0], np.log(p))
    p_srh_top = np.exp(p_srh_top)
    if srh_bottom != 0:
        p_srh_bottom = np.interp(srh_bottom, hgt - hgt[0], np.log(p))
        p_srh_bottom = np.exp(p_srh_bottom)
    else:
        p_srh_bottom = p[0]

    if exact:
        ind1 = np.min(np.where(p_srh_bottom >= p)[0])
        ind2 = np.max(np.where(p_srh_top <= p)[0])
        u1 = log_interp(p_srh_bottom, p, u)
        v1 = log_interp(p_srh_bottom, p, v)
        u2 = log_interp(p_srh_top, p, u)
        v2 = log_interp(p_srh_top, p, v)
        u_int = np.concatenate([[u1], u[ind1:ind2 + 1], [u2]])
        v_int = np.concatenate([[v1], v[ind1:ind2 + 1], [v2]])

    else:
        interp_levels = np.arange(p_srh_bottom, p_srh_top + dp, dp)
        u_int = log_interp(interp_levels, p, u)
        v_int = log_interp(interp_levels, p, v)

    sru = (u_int - storm_u)
    srv = (v_int - storm_v)

    int_layers = (sru[1:] * srv[:-1] - sru[:-1] * srv[1:])

    p_srh = int_layers[int_layers > 0.].sum() * units('m^2/s^2')
    n_srh = int_layers[int_layers < 0.].sum() * units('m^2/s^2')
    t_srh = p_srh + n_srh

    return p_srh, n_srh, t_srh
