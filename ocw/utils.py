# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

''''''

import sys
import datetime as dt
import numpy as np
import numpy.ma as ma

from mpl_toolkits.basemap import shiftgrid
from dateutil.relativedelta import relativedelta
from netCDF4 import num2date


def decode_time_values(dataset, time_var_name):
    ''' Decode NetCDF time values into Python datetime objects.

    :param dataset: The dataset from which time values should be extracted.
    :type dataset: netCDF4.Dataset
    :param time_var_name: The name of the time variable in dataset.
    :type time_var_name: :mod:`string`

    :returns: The list of converted datetime values.

    :raises ValueError: If the time units value couldn't be parsed, if the
        base time value couldn't be parsed, or if the time_var_name could not
        be found in the dataset.
    '''
    time_data = dataset.variables[time_var_name]
    time_format = time_data.units
    if time_format[-1].lower() == 'z':
        time_format = time_format[:-1]
    if time_format[-3:].lower() == 'utc':
        time_format = time_format[:-3]

    time_units = parse_time_units(time_format)
    time_base = parse_time_base(time_format)

    times = []
    if time_units == 'months':
        # datetime.timedelta doesn't support a 'months' option. To remedy
        # this, a month == 30 days for our purposes.
        for time_val in time_data:
            times.append(time_base + relativedelta(months=int(time_val)))
    else:
        try:
            times_calendar = time_data.calendar
        except:
            times_calendar = 'standard'

        times = num2date(
            time_data[:], units=time_format, calendar=times_calendar)
    return times


def parse_time_units(time_format):
    ''' Parse units value from time units string.

    The only units that are supported are: seconds, minutes, hours, days,
        months, or years.

    :param time_format: The time data units string from the dataset
        being processed. The string should be of the format
        '<units> since <base time date>'
    :type time_format: :mod:`string`

    :returns: The unit substring from the time units string

    :raises ValueError: If the units present in the time units string doesn't
        match one of the supported unit value.
    '''
    for unit in ['seconds', 'minutes', 'hours', 'days', 'months', 'years']:
        if unit in time_format:
            return unit
    else:
        cur_frame = sys._getframe().f_code
        err = "{}.{}: Unable to parse valid units from {}".format(
            cur_frame.co_filename,
            cur_frame.co_name,
            time_format
        )
        raise ValueError(err)


def parse_time_base(time_format):
    ''' Parse time base object from the time units string.

    :param time_format: The time data units string from the dataset
        being processed. The string should be of the format
        '<units> since <base time date>'
    :type time_format: :mod:`string`

    :returns: The base time as a datetime object.

    :raises ValueError: When the base time string couldn't be parsed from the
        units time_format string or if the date string didn't match any of the
        expected formats.
    '''
    base_time_string = parse_base_time_string(time_format)

    time_format = time_format.strip()

    possible_time_formats = [
        '%Y:%m:%d %H:%M:%S', '%Y-%m-%d %H-%M-%S', '%Y/%m/%d %H/%M/%S',
        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y%m%d %H:%M:%S',
        '%Y%m%d%H%M%S', '%Y-%m-%d-%H-%M-%S', '%Y/%m/%d/%H/%M/%S',
        '%Y:%m:%d:%H:%M:%S', '%Y-%m-%d-%H:%M:%S', '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d%H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M',
        '%Y:%m:%d %H:%M', '%Y%m%d %H:%M', '%Y-%m-%d', '%Y/%m/%d',
        '%Y:%m:%d', '%Y%m%d', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H',
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'
    ]

    # Attempt to match the base time string with a possible format parsing
    # string.
    for time_format in possible_time_formats:
        try:
            stripped_time = dt.datetime.strptime(base_time_string, time_format)
            break
        except ValueError:
            # This exception means that the time format attempted was
            # incorrect. No need to report or raise this,
            # simply try the next one!
            pass
    # If we got through the entire loop without a break, we couldn't parse the
    # date string with our known formats.
    else:
        cur_frame = sys._getframe().f_code
        err = "{}.{}: Unable to parse valid date from {}".format(
            cur_frame.co_filename,
            cur_frame.co_name,
            base_time_string
        )

        raise ValueError(err)

    return stripped_time


def parse_base_time_string(time_format):
    ''' Retrieve base time string from time data units information.

    :param time_format: The time data units string from the dataset
        being processed. The string should be of the format
        '<units> since <base time date>'
    :type time_format: :mod:`string`

    :returns: The base time string split out of the time units information.

    :raises ValueError: When the time_format parameter is malformed.
    '''
    if 'since' not in time_format:
        cur_frame = sys._getframe().f_code
        err = "{}.{}: Invalid time_format value {} given".format(
            cur_frame.co_filename,
            cur_frame.co_name,
            time_format
        )

        raise ValueError(err)

    return time_format.split('since')[1].strip()


def normalize_lat_lon_values(lats, lons, values):
    ''' Normalize lat/lon values

    Ensure that lat/lon values are within [-180, 180)/[-90, 90) as well
    as sorted. If the values are off the grid they are shifted into the
    expected range.

    :param lats: A 1D numpy array of sorted lat values.
    :type lats: :class:`numpy.ndarray`
    :param lons: A 1D numpy array of sorted lon values.
    :type lons: :class:`numpy.ndarray`
    :param values: A 3D array of data values.

    :returns: A :func:`tuple` of the form (adjust_lats, adjusted_lons,
                       adjusted_values)

    :raises ValueError: If the lat/lon values are not sorted.
    '''
    if lats.ndim == 1 and lons.ndim == 1:
        # Avoid unnecessary shifting if all lons are higher than 180
        if lons.min() > 180:
            lons -= 360

        # Make sure lats and lons are monotonically increasing
        lats_decreasing = np.diff(lats) < 0
        lons_decreasing = np.diff(lons) < 0

        # If all values are decreasing then they just need to be reversed
        lats_reversed, lons_reversed = (lats_decreasing.all(),
                                        lons_decreasing.all())

        # If the lat values are unsorted then raise an exception
        if not lats_reversed and lats_decreasing.any():
            raise ValueError('Latitudes must be sorted.')

        # Perform same checks now for lons
        if not lons_reversed and lons_decreasing.any():
            raise ValueError('Longitudes must be sorted.')

        # Also check if lons go from [0, 360), and convert to [-180, 180)
        # if necessary
        lons_shifted = lons.max() > 180
        lats_out, lons_out, data_out = lats[:], lons[:], values[:]
        # Now correct data if latlon grid needs to be shifted
        if lats_reversed:
            lats_out = lats_out[::-1]
            data_out = data_out[..., ::-1, :]

        if lons_reversed:
            lons_out = lons_out[::-1]
            data_out = data_out[..., :, ::-1]

        if lons_shifted:
            data_out, lons_out = shiftgrid(
                180, data_out, lons_out, start=False)

        return lats_out, lons_out, data_out
    else:
        lons[lons > 180] = lons[lons > 180] - 360.

        return lats, lons, values


def reshape_monthly_to_annually(dataset):
    ''' Reshape monthly binned dataset to annual bins.

    Reshape a monthly binned dataset's 3D value array with shape
    (num_months, num_lats, num_lons) to a 4D array with shape
    (num_years, 12, num_lats, num_lons). This causes the data to be binned
    annually while retaining its original shape.

    It is assumed that the number of months in the dataset is evenly
    divisible by 12. If it is not you will receive error due to
    an invalid shape.

    Example change of a dataset's shape:
    (24, 90, 180) -> (2, 12, 90, 180)

    :param dataset: Dataset object with full-year format
    :type dataset: :class:`dataset.Dataset`

    :returns: Dataset values array with shape (num_year, 12, num_lat, num_lon)
    '''

    values = dataset.values[:]
    data_shape = values.shape
    num_total_month = data_shape[0]
    num_year = num_total_month / 12
    num_month = 12
    year_month_shape = num_year, num_month
    lat_lon_shape = data_shape[1:]
    # Make new shape (num_year, 12, num_lats, num_lons)
    new_shape = tuple(year_month_shape + lat_lon_shape)
    # Reshape data with new shape
    values.shape = new_shape

    return values


def calc_temporal_mean(dataset):
    ''' Calculate temporal mean of dataset's values

    :param dataset: OCW Dataset whose first dimension is time
    :type dataset: :class:`dataset.Dataset`

    :returns: Mean values averaged for the first dimension (time)
    '''
    return ma.mean(dataset.values, axis=0)


def calc_climatology_year(dataset):
    ''' Calculate climatology of dataset's values for each year

    :param dataset: Monthly binned Dataset object with an evenly divisible
        number of months.
    :type dataset: :class:`dataset.Dataset`

    :returns: Mean values for each year (annual_mean) and mean values for all
        years (total_mean)

    :raise ValueError: If the number of monthly bins is not evenly divisible
        by 12.
    '''

    values_shape = dataset.values.shape
    time_shape = values_shape[0]
    if time_shape % 12:
        raise ValueError('The dataset should be in full-time format.')
    else:
        # Get values reshaped to (num_year, 12, num_lats, num_lons)
        values = reshape_monthly_to_annually(dataset)
        # Calculate mean values over year (num_year, num_lats, num_lons)
        annually_mean = values.mean(axis=1)
        # Calculate mean values over all years (num_lats, num_lons)
        total_mean = annually_mean.mean(axis=0)

    return annually_mean, total_mean


def calc_climatology_monthly(dataset):
    ''' Calculate monthly mean values for a dataset.
    Follow COARDS climo stats calculation, the year can be given as 0
    but the min year allowed in Python is 1
    http://www.cgd.ucar.edu/cms/eaton/netcdf/CF-20010629.htm#climatology

    :param dataset: Monthly binned Dataset object with the number of months
        divisible by 12
    :type dataset: :class:`dataset.Dataset`

    :returns: Mean values for each month of the year of shape
              (12, num_lats, num_lons) and times array of datetime objects
              of length 12

    :raise ValueError: If the number of monthly bins is not divisible by 12
    '''

    if dataset.values.shape[0] % 12:
        error = (
            "The length of the time axis in the values array should be "
            "divisible by 12."
        )
        raise ValueError(error)
    else:
        values = reshape_monthly_to_annually(dataset).mean(axis=0)

        # A year can commence from any month
        first_month = dataset.times[0].month
        times = np.array([dt.datetime(1, first_month, 1) +
                          relativedelta(months=x)
                          for x in range(12)])
        return values, times


def calc_time_series(dataset):
    ''' Calculate time series mean values for a dataset

    :param dataset: Dataset object
    :type dataset: :class:`dataset.Dataset`

    :returns: time series for the dataset of shape (nT)
    '''

    t_series = []
    for t in xrange(dataset.values.shape[0]):
        t_series.append(dataset.values[t, :, :].mean())

    return t_series


def get_temporal_overlap(dataset_array):
    ''' Find the maximum temporal overlap across the observation and model datasets

    :param dataset_array: an array of OCW datasets
    '''
    start_time = []
    end_time = []
    for dataset in dataset_array:
        start_time.append(dataset.temporal_boundaries()[0])
        end_time.append(dataset.temporal_boundaries()[1])

    return np.max(start_time), np.min(end_time)


def calc_subregion_area_mean_and_std(dataset_array, subregions):
    ''' Calculate area mean and standard deviation values for a given
        subregions using datasets on common grid points
    :param dataset_array: An array of OCW Dataset Objects
    :type list:
    :param subregions: list of subregions
    :type subregions: :class:`numpy.ma.array`
    :returns: area averaged time series for the dataset of shape
              (ntime, nsubregion)
    '''

    ndata = len(dataset_array)
    dataset0 = dataset_array[0]
    if dataset0.lons.ndim == 1:
        lons, lats = np.meshgrid(dataset0.lons, dataset0.lats)
    else:
        lons = dataset0.lons
        lats = dataset0.lats
    subregion_array = np.zeros(lons.shape)
    mask_array = dataset_array[0].values[0, :].mask
    # dataset0.values.shsape[0]: length of the time dimension
    # spatial average
    t_series = ma.zeros([ndata, dataset0.values.shape[0], len(subregions)])
    # spatial standard deviation
    spatial_std = ma.zeros([ndata, dataset0.values.shape[0], len(subregions)])

    for iregion, subregion in enumerate(subregions):
        lat_min, lat_max, lon_min, lon_max = subregion[1]
        y_index, x_index = np.where((lats >= lat_min) & (
            lats <= lat_max) & (lons >= lon_min) & (lons <= lon_max))
        subregion_array[y_index, x_index] = iregion + 1
        for idata in np.arange(ndata):
            t_series[idata, :, iregion] = ma.mean(dataset_array[idata].values[
                                                  :, y_index, x_index], axis=1)
            spatial_std[idata, :, iregion] = ma.std(
                dataset_array[idata].values[:, y_index, x_index], axis=1)
    subregion_array = ma.array(subregion_array, mask=mask_array)
    return t_series, spatial_std, subregion_array


def calc_area_weighted_spatial_average(dataset, area_weight=False):
    '''Calculate area weighted average of the values in OCW dataset

    :param dataset: Dataset object
    :type dataset: :class:`dataset.Dataset`

    :returns: time series for the dataset of shape (nT)
    '''

    if dataset.lats.ndim == 1:
        lons, lats = np.meshgrid(dataset.lons, dataset.lats)
    else:
        lats = dataset.lats
    weights = np.cos(lats * np.pi / 180.)

    nt, ny, nx = dataset.values.shape
    spatial_average = ma.zeros(nt)
    for it in np.arange(nt):
        if area_weight:
            spatial_average[it] = ma.average(
                dataset.values[it, :], weights=weights)
        else:
            spatial_average[it] = ma.average(dataset.values[it, :])

    return spatial_average
