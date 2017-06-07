# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# (C) British Crown Copyright 2017 Met Office.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Module containing ancillary generation utilities for Improver"""

import iris
import numpy as np
import os
from glob import glob


def _make_mask_cube(mask_data, key, coords,
                    upper_threshold=None, lower_threshold=None):
    """
    Makes cube from numpy masked array generated from orography fields.

    Parameters
    ----------
    mask_data : numpy masked array
        The numpy array to make a cube from.
    key : string
        Key from THRESHOLD_DICT which descibes type of topography band.
    coords : dictionary
        Dictionary of coordinate on the model ancillary file.
    upper_threshold : float
        Upper topographic bound defining the mask.
    lower_threshold : float
        Lower topographic bound defining the mask.

    Returns
    -------
    mask_cube : cube
        Cube containing the mask_data array, with appropriate coordinate
        and attribute information.
    """
    mask_cube = iris.cube.Cube(mask_data, long_name='Topography mask')
    if lower_threshold or lower_threshold == 0:
        coord_name = 'topographic_bound_lower'
        threshold_coord = iris.coords.AuxCoord(lower_threshold,
                                               long_name=coord_name)
        mask_cube.add_aux_coord(threshold_coord)
    if upper_threshold or upper_threshold == 0:
        coord_name = 'topographic_bound_upper'
        threshold_coord = iris.coords.AuxCoord(upper_threshold,
                                               long_name=coord_name)
        mask_cube.add_aux_coord(threshold_coord)
    mask_cube.attributes['Topographical Type'] = key.title()
    for coord in coords:
        if coord.name() in ['projection_y_coordinate', 'latitude']:
            mask_cube.add_dim_coord(coord, 0)
        elif coord.name() in ['projection_x_coordinate', 'longitude']:
            mask_cube.add_dim_coord(coord, 1)
        else:
            mask_cube.add_aux_coord(coord)
    return mask_cube


def find_standard_ancil(grid, stage_ancil):
    """
    Reads standard ancillary from StaGE or raises exception.

    Parameters
    -----------
    grid : string
      String describing standard grid

    stage_ancil : string
      Location of stage ancillaries

    Returns
    --------
    standard_ancil : cube
        The StaGE ancil cube.

    Raises
    -------
    IOError: if input ancillary cannot be found in either StaGE or UM
             directories.
    """
    stage_ancil = glob(stage_ancil)
    if len(stage_ancil) > 0:
        standard_ancil = iris.load(stage_ancil[0])[0]
    else:
        msg = 'Cannot find input ancillary. Tried StaGE: {}'
        raise IOError(msg.format(stage_ancil))
    return standard_ancil


class CorrectLandSeaMask(object):
    """
    Round landsea mask to binary values

    Corrects interpolated land sea masks to boolean values of
    False [sea] and True [land].
    """
    def __init__(self):
        pass

    def __repr__(self):
        """Represent the configured plugin instance as a string"""
        result = ('<CorrectLandSeaMask')
        return result

    def process(self, standard_landmask):
        """Read in the interpolated landmask and assign values round
            values < 0.5 to False and >=0.5 to True.

        Parameters
        ----------
        standard_landmask: cube
            input landmask on standard grid.

        Returns
        -------
        standard_landmask : cube
            output landmask of boolean values.
        """
        mask_sea = np.ma.masked_less(standard_landmask.data, 0.5).mask
        standard_landmask.data[mask_sea] = False
        mask_land = np.ma.masked_greater(standard_landmask.data, 0.).mask
        standard_landmask.data[mask_land] = True
        return standard_landmask


class GenerateOrographyBandAncils(object):
    """
    Generate topographic band ancillaries for the standard grids.

    Reads StaGE output orography files first, then generates binary mask
    of land points within the orography band specified.
    """
    def __init__(self):
        pass

    def __repr__(self):
        """Represent the configured plugin instance as a string."""
        result = ('<GenerateOrographyBandAncils')
        return result

    def gen_orography_masks(
            self, standard_orography, standard_landmask, key, thresholds):
        """
        Function to generate topographical band masks.

        Parameters
        -----------
        standard_orography : cube
            The standard orography, read from StaGE.
        standard_landmask : cube
            The landmask generated by gen_landmask.
        key : string
            Key from THRESHOLD_DICT which descibes type of topography band.
        thresholds: float or list
            Upper and/or lower thresholds of the current topographical band.

        Returns
        -------
        mask_cube : cube
            Cube containing topographical band mask.

        Raises
        ------
        KeyError: if the key does not match any in THRESHOLD_DICT.
        """
        coords = standard_orography.coords()
        if key == 'max_land_threshold':  # mask everything above max bound
            orog_band = np.ma.masked_greater(
                standard_orography.data, thresholds[0]).mask.astype(int)
            mask_data = np.ma.masked_where(
                np.logical_not(standard_landmask.data), orog_band)
            sea_fillvalue = np.ma.default_fill_value(mask_data.data)
            mask_data.data[mask_data.mask] = sea_fillvalue
            mask_cube = _make_mask_cube(mask_data, key, coords,
                                        lower_threshold=thresholds)
        elif key == 'land':  # regular topographical bands above land
            old_threshold, threshold = thresholds
            orog_band = np.ma.masked_inside(
                standard_orography.data, old_threshold,
                threshold).mask.astype(int)
            mask_data = np.ma.masked_where(
                np.logical_not(standard_landmask.data), orog_band)
            sea_fillvalue = np.ma.default_fill_value(mask_data.data)
            mask_data.data[mask_data.mask] = sea_fillvalue
            mask_cube = _make_mask_cube(
                mask_data, key, coords, lower_threshold=old_threshold,
                upper_threshold=threshold)
        else:
            msg = 'Unknown threshold_dict key: {}'
            raise KeyError(msg.format(key))
        return mask_cube

    def process(self, orography, landmask, thresholds_dict):
        """Check for existing ancillary files, generate new files
           if needed and save to the improver_ancillary directory
           for use by IMPROVER plugins.

        Parameters
        ----------
        orography : cube
          orography on standard grid.

        landmask : cube
          land mask on standard grid.

        threshold_dict : dictionary
          definition of orography bands required.

        Returns
        -------
        cubelist : cubelist
          list of orographic band mask cubes.
        """
        cubelist = iris.cube.CubeList()
        for dict_key, dict_bound in thresholds_dict.iteritems():
            if len(dict_bound) == 0:
                msg = 'No threshold(s) found for topographic type: {}'
                raise ValueError(msg.format(dict_key))
            for limits in dict_bound:
                oro_band = self.gen_orography_masks(
                    orography, landmask, dict_key, limits)
                cubelist.append(oro_band)
        return cubelist
