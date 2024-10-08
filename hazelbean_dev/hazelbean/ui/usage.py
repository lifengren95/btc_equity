"""Module to that provides functions for usage logging."""
import contextlib
import hashlib
import json
import locale
import logging
import os
import platform
import sys
import threading
import traceback
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import uuid

from osgeo import gdal
from osgeo import ogr
from osgeo import osr
# import natcap.invest
# import pygeoprocessing3

from .. import utils

ENCODING = sys.getfilesystemencoding()

_ENDPOINTS_INDEX_URL = (
    'http://data.naturalcapitalproject.org/server_registry/'
    'invest_usage_logger_v2/index.html')


@contextlib.contextmanager
def log_run(module, args):
    """Context manager to log an InVEST model run and exit status.

    Parameters:
        module (string): The string module name that identifies the model.
        args (dict): The full args dictionary.

    Returns:
        ``None``
    """
    session_id = str(uuid.uuid4())
    log_thread = threading.Thread(
        target=_log_model, args=(module, args, session_id))
    log_thread.start()

    try:
        yield
    except Exception:
        exit_status_message = traceback.format_exc()
        raise
    else:
        exit_status_message = ':)'
    finally:
        log_exit_thread = threading.Thread(
            target=_log_exit_status, args=(session_id, exit_status_message))
        log_exit_thread.start()


def _calculate_args_bounding_box(args_dict):
    """Calculate the bounding boxes of any GIS types found in `args_dict`.

    Args:
        args_dict (dict): a string key and any value pair dictionary.

    Returns:
        bb_intersection, bb_union tuple that's either the lat/lng bounding
            intersection and union bounding boxes of the gis types referred to
            in args_dict.  If no GIS types are present, this is a (None, None)
            tuple.
    """
    def _merge_bounding_boxes(bb1, bb2, mode):
        """Merge two bounding boxes through union or intersection.

        Parameters:
            bb1 (list of float): bounding box of the form
                [minx, maxy, maxx, miny] or None
            bb2 (list of float): bounding box of the form
                [minx, maxy, maxx, miny] or None
            mode (string): either "union" or "intersection" indicating the
                how to combine the two bounding boxes.

        Returns:
            either the intersection or union of bb1 and bb2 depending
            on mode.  If either bb1 or bb2 is None, the other is returned.
            If both are None, None is returned.
        """
        if bb1 is None:
            return bb2
        if bb2 is None:
            return bb1

        if mode == "union":
            comparison_ops = [min, max, max, min]
        if mode == "intersection":
            comparison_ops = [max, min, min, max]

        bb_out = [op(x, y) for op, x, y in zip(comparison_ops, bb1, bb2)]
        return bb_out

    def _merge_local_bounding_boxes(arg, bb_intersection=None, bb_union=None):
        """Traverse nested dictionary to merge bounding boxes of GIS types.

        Args:
            arg (dict): contains string keys and pairs that might be files to
                gis types.  They can be any other type, including dictionaries.
            bb_intersection (list or None): if list, has the form
                [xmin, ymin, xmax, ymax], where coordinates are in lng, lat
            bb_union (list or None): if list, has the form
                [xmin, ymin, xmax, ymax], where coordinates are in lng, lat

        Returns:
            (intersection, union) bounding box tuples of all filepaths to GIS
            data types found in the dictionary and bb_intersection and bb_union
            inputs.  None, None if no arguments were GIS data types and input
            bounding boxes are None.
        """
        def _is_gdal(arg):
            """Test if input argument is a path to a gdal raster."""
            if (isinstance(arg, str) or
                    isinstance(arg, str)) and os.path.exists(arg):
                with utils.capture_gdal_logging():
                    raster = gdal.Open(arg)
                    if raster is not None:
                        return True
            return False

        def _is_ogr(arg):
            """Test if input argument is a path to an ogr vector."""
            if (isinstance(arg, str) or
                    isinstance(arg, str)) and os.path.exists(arg):
                with utils.capture_gdal_logging():
                    vector = ogr.Open(arg)
                    if vector is not None:
                        # OGR opens CSV files.  For now, we should not
                        # consider these to be vectors.
                        driver_name = vector.GetDriver().GetName()
                        if driver_name == 'CSV':
                            return False
                        return True
            return False

        if isinstance(arg, dict):
            # if dict, grab the bb's for all the members in it
            for value in list(arg.values()):
                bb_intersection, bb_union = _merge_local_bounding_boxes(
                    value, bb_intersection, bb_union)
        elif isinstance(arg, list):
            # if list, grab the bb's for all the members in it
            for value in arg:
                bb_intersection, bb_union = _merge_local_bounding_boxes(
                    value, bb_intersection, bb_union)
        else:
            # singular value, test if GIS type, if not, don't update bb's
            # this is an undefined bounding box that gets returned when ogr
            # opens a table only
            local_bb = [0., 0., 0., 0.]
            if _is_gdal(arg):
                raster_info = pygeoprocessing3.get_raster_info(arg)
                local_bb = raster_info['bounding_box'][0]
                projection_wkt = raster_info['projection']
                spatial_ref = osr.SpatialReference()
                spatial_ref.ImportFromWkt(projection_wkt)
            elif _is_ogr(arg):
                vector_info = pygeoprocessing3.get_vector_info(arg)
                local_bb = vector_info['bounding_box']
                projection_wkt = vector_info['projection']
                spatial_ref = osr.SpatialReference()
                spatial_ref.ImportFromWkt(projection_wkt)
            try:
                # means there's a GIS type with a well defined bounding box
                # create transform, and reproject local bounding box to lat/lng
                lat_lng_ref = osr.SpatialReference()
                lat_lng_ref.ImportFromEPSG(4326)  # EPSG 4326 is lat/lng
                to_lat_trans = osr.CoordinateTransformation(
                    spatial_ref, lat_lng_ref)
                for point_index in [0, 2]:
                    local_bb[point_index], local_bb[point_index + 1], _ = (
                        to_lat_trans.TransformPoint(
                            local_bb[point_index], local_bb[point_index + 1]))

                bb_intersection = _merge_bounding_boxes(
                    local_bb, bb_intersection, 'intersection')
                bb_union = _merge_bounding_boxes(
                    local_bb, bb_union, 'union')
            except Exception:
                # All kinds of exceptions from bad transforms or CSV files
                # or dbf files could get us to this point, just don't bother
                # with the local_bb at all
                pass

        return bb_intersection, bb_union

    return _merge_local_bounding_boxes(args_dict)


def _log_exit_status(session_id, status):
    """Log the completion of a model with the given status.

    Parameters:
        session_id (string): a unique string that can be used to identify
            the current session between the model initial start and exit.
        status (string): a string describing the exit status of the model,
            'success' would indicate the successful completion while an
            exception string could indicate a failure.

    Returns:
        None
    """
    logger = logging.getLogger('natcap.invest.ui.usage._log_exit_status')

    try:
        payload = {
            'session_id': session_id,
            'status': status,
        }
        log_finish_url = json.loads(urllib.request.urlopen(
            _ENDPOINTS_INDEX_URL).read().strip())['FINISH']

        urllib.request.urlopen(urllib.request.Request(log_finish_url,
                                        urllib.parse.urlencode(payload)))
    except Exception as exception:
        # An exception was thrown, we don't care.
        logger.warn(
            'an exception encountered when _log_exit_status %s',
            str(exception))


def _log_model(model_name, model_args, session_id=None):
    """Log information about a model run to a remote server.

    Parameters:
        model_name (string): a python string of the package version.
        model_args (dict): the traditional InVEST argument dictionary.

    Returns:
        None
    """
    logger = logging.getLogger('natcap.invest.ui.usage._log_model')

    def _node_hash():
        """Return a hash for the current computational node."""
        data = {
            'os': platform.platform(),
            'hostname': platform.node(),
            'userdir': os.path.expanduser('~')
        }
        md5 = hashlib.md5()
        # a json dump will handle non-ascii encodings
        md5.update(json.dumps(data))
        return md5.hexdigest()

    try:
        bounding_box_intersection, bounding_box_union = (
            _calculate_args_bounding_box(model_args))

        payload = {
            'model_name': model_name,
            'invest_release': natcap.invest.__version__,
            'node_hash': _node_hash(),
            'system_full_platform_string': platform.platform(),
            'system_preferred_encoding': locale.getdefaultlocale()[1],
            'system_default_language': locale.getdefaultlocale()[0],
            'bounding_box_intersection': str(bounding_box_intersection),
            'bounding_box_union': str(bounding_box_union),
            'session_id': session_id,
        }
        log_start_url = json.loads(urllib.request.urlopen(
            _ENDPOINTS_INDEX_URL).read().strip())['START']

        urllib.request.urlopen(urllib.request.Request(log_start_url,
                                        urllib.parse.urlencode(payload)))
    except Exception as exception:
        # An exception was thrown, we don't care.
        logger.debug(
            'an exception encountered when logging %s', repr(exception))
