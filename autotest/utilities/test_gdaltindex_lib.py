#!/usr/bin/env pytest
# -*- coding: utf-8 -*-
###############################################################################
# $Id$
#
# Project:  GDAL/OGR Test Suite
# Purpose:  Library version of gdaltindex testing
# Author:   Even Rouault <even dot rouault @ spatialys.com>
#
###############################################################################
# Copyright (c) 2023, Even Rouault <even dot rouault at spatialys.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

import os

import gdaltest
import pytest

from osgeo import gdal, ogr

###############################################################################
# Simple test


@pytest.fixture(scope="module")
def four_tiles(tmp_path_factory):

    drv = gdal.GetDriverByName("GTiff")
    wkt = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],TOWGS84[0,0,0,0,0,0,0],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9108"]],AUTHORITY["EPSG","4326"]]'

    dirname = tmp_path_factory.mktemp("test_gdaltindex")
    fnames = [f"{dirname}/gdaltindex{i}.tif" for i in (1, 2, 3, 4)]

    ds = drv.Create(fnames[0], 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([49, 0.1, 0, 2, 0, -0.1])
    ds = None

    ds = drv.Create(fnames[1], 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([49, 0.1, 0, 3, 0, -0.1])
    ds = None

    ds = drv.Create(fnames[2], 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([48, 0.1, 0, 2, 0, -0.1])
    ds = None

    ds = drv.Create(fnames[3], 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([48, 0.1, 0, 3, 0, -0.1])
    ds = None

    return fnames


@pytest.fixture()
def four_tile_index(four_tiles, tmp_path):

    gdal.TileIndex(f"{tmp_path}/tileindex.shp", [four_tiles[0], four_tiles[1]])
    gdal.TileIndex(f"{tmp_path}/tileindex.shp", [four_tiles[2], four_tiles[3]])
    return f"{tmp_path}/tileindex.shp"


def test_gdaltindex_lib_basic(four_tile_index):

    ds = ogr.Open(four_tile_index)
    assert ds.GetLayer(0).GetFeatureCount() == 4

    tileindex_wkt = ds.GetLayer(0).GetSpatialRef().ExportToWkt()
    assert "WGS_1984" in tileindex_wkt

    expected_wkts = [
        "POLYGON ((49 2,50 2,50 1,49 1,49 2))",
        "POLYGON ((49 3,50 3,50 2,49 2,49 3))",
        "POLYGON ((48 2,49 2,49 1,48 1,48 2))",
        "POLYGON ((48 3,49 3,49 2,48 2,48 3))",
    ]

    for i, feat in enumerate(ds.GetLayer(0)):
        assert (
            feat.GetGeometryRef().ExportToWkt() == expected_wkts[i]
        ), "i=%d, wkt=%s" % (i, feat.GetGeometryRef().ExportToWkt())


###############################################################################
# Try adding the same rasters again


def test_gdaltindex_lib_already_existing_rasters(four_tiles, four_tile_index, tmp_path):
    class GdalErrorHandler(object):
        def __init__(self):
            self.warnings = []

        def handler(self, err_level, err_no, err_msg):
            if err_level == gdal.CE_Warning:
                self.warnings.append(err_msg)

    err_handler = GdalErrorHandler()
    with gdaltest.error_handler(err_handler.handler):
        ds = gdal.TileIndex(four_tile_index, four_tiles)
        del ds

    assert len(err_handler.warnings) == 4
    assert (
        "gdaltindex1.tif is already in tileindex. Skipping it."
        in err_handler.warnings[0]
    )
    assert (
        "gdaltindex2.tif is already in tileindex. Skipping it."
        in err_handler.warnings[1]
    )
    assert (
        "gdaltindex3.tif is already in tileindex. Skipping it."
        in err_handler.warnings[2]
    )
    assert (
        "gdaltindex4.tif is already in tileindex. Skipping it."
        in err_handler.warnings[3]
    )

    ds = ogr.Open(four_tile_index)
    assert ds.GetLayer(0).GetFeatureCount() == 4


###############################################################################
# Try adding a raster in another projection with -skip_different_projection
# 5th tile should NOT be inserted


def test_gdaltindex_skipDifferentProjection(tmp_path, four_tile_index):

    drv = gdal.GetDriverByName("GTiff")
    wkt = """GEOGCS["WGS 72",
    DATUM["WGS_1972",
        SPHEROID["WGS 72",6378135,298.26],
        TOWGS84[0,0,4.5,0,0,0.554,0.2263]],
    PRIMEM["Greenwich",0],
    UNIT["degree",0.0174532925199433]]"""

    ds = drv.Create(f"{tmp_path}/gdaltindex5.tif", 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([47, 0.1, 0, 2, 0, -0.1])
    ds = None

    class GdalErrorHandler(object):
        def __init__(self):
            self.warning = None

        def handler(self, err_level, err_no, err_msg):
            if err_level == gdal.CE_Warning:
                self.warning = err_msg

    err_handler = GdalErrorHandler()
    with gdaltest.error_handler(err_handler.handler):
        gdal.TileIndex(
            four_tile_index,
            [f"{tmp_path}/gdaltindex5.tif"],
            skipDifferentProjection=True,
        )
    assert (
        "gdaltindex5.tif is not using the same projection system as other files in the tileindex"
        in err_handler.warning
    )

    ds = ogr.Open(four_tile_index)
    assert ds.GetLayer(0).GetFeatureCount() == 4


###############################################################################
# Try adding a raster in another projection with -t_srs
# 5th tile should be inserted, will not be if there is a srs transformation error


def test_gdaltindex_lib_outputSRS_writeAbsoluePath(tmp_path, four_tile_index):

    drv = gdal.GetDriverByName("GTiff")
    wkt = """GEOGCS["WGS 72",
    DATUM["WGS_1972",
        SPHEROID["WGS 72",6378135,298.26],
        TOWGS84[0,0,4.5,0,0,0.554,0.2263]],
    PRIMEM["Greenwich",0],
    UNIT["degree",0.0174532925199433]]"""

    ds = drv.Create(f"{tmp_path}/gdaltindex5.tif", 10, 10, 1)
    ds.SetProjection(wkt)
    ds.SetGeoTransform([47, 0.1, 0, 2, 0, -0.1])
    ds = None

    saved_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        gdal.TileIndex(
            four_tile_index,
            ["gdaltindex5.tif"],
            outputSRS="EPSG:4326",
            writeAbsolutePath=True,
        )
    finally:
        os.chdir(saved_dir)

    ds = ogr.Open(four_tile_index)
    lyr = ds.GetLayer(0)
    assert lyr.GetFeatureCount() == 5, (
        "got %d features, expecting 5" % ds.GetLayer(0).GetFeatureCount()
    )
    filename = lyr.GetFeature(4).GetField("location")
    assert filename.endswith("gdaltindex5.tif")
    assert filename != "gdaltindex5.tif"


###############################################################################
# Test -f, -lyr_name


def test_gdaltindex_lib_format_layerName(tmp_path, four_tiles):

    index_mif = str(tmp_path / "test_gdaltindex6.mif")

    gdal.TileIndex(
        index_mif, [four_tiles[0]], format="MapInfo File", layerName="tileindex"
    )
    ds = ogr.Open(index_mif)
    lyr = ds.GetLayer(0)
    assert lyr.GetFeatureCount() == 1, (
        "got %d features, expecting 1" % lyr.GetFeatureCount()
    )
    ds = None
