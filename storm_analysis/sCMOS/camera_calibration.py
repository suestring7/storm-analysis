#!/usr/bin/env python
"""
Calculates offset, variance and gain for each pixel of
a sCMOS camera. The input files are in the form that
is generated by calibrate.py program in the folder
hal4000/hamamatsu/ of the STORM-Control project which
is available here:

http://zhuang.harvard.edu/software.html

The units of the results are:
offset - adu
gain - adu / e-
variance - adu ^ 2
rqe - AU

Hazen 05/18
"""

import matplotlib
import matplotlib.pyplot as pyplot
import numpy
import os
import pickle
import scipy
import scipy.ndimage
import sys


def cameraCalibration(scmos_files, show_fit_plots = True, show_mean_plots = True):
    """
    Calculate camera calibration.

    scmos_files - A list of calibration files [dark, light1, light2, ..]
    show_fit_plots - Show (a few) plots of the fits for the pixel gain.
    show_mean_plots - Show mean of intensity versus frame for the calibration files (if available).
    """
    n_frames = None
    n_points = len(scmos_files)

    all_means = None
    all_vars = None
    offset = None
    variance = None
    
    assert(len(scmos_files) > 1), "Need at least two calibration files."

    # Load the data files.
    #
    for i, a_file in enumerate(scmos_files):
        print(i, "loading", a_file)

        [n_frames, pixel_mean, pixel_var] = loadCalibrationData(a_file,
                                                                is_dark = (i == 0),
                                                                print_roi_info = (i == 0),
                                                                show_mean_plots = show_mean_plots)

        if all_means is None:
            all_means = numpy.zeros((pixel_mean.shape[0], pixel_mean.shape[1], n_points))
            all_vars = numpy.zeros_like(all_means)

        # Other files have the dark calibration offset and variance subtracted.
        if (i > 0):
            all_means[:,:,i] = pixel_mean - offset
            all_vars[:,:,i] = pixel_var - variance

            print("  average pixel variance {0:.3f}".format(numpy.mean(pixel_var - variance)))

        # The first file is assumed to be the dark calibration file.
        else:
            offset = pixel_mean
            variance = pixel_var

    # Fit for gain.
    gain = numpy.zeros((all_means.shape[0], all_means.shape[1]))
    nx = all_means.shape[0]
    ny = all_means.shape[1]
    for i in range(nx):
        for j in range(ny):
            if (numpy.count_nonzero(all_means[i,j,:]) > 0):
                gain[i,j] = numpy.polyfit(all_means[i,j,:], all_vars[i,j,:], 1)[0]
            else:
                print("Bad pixel detected at", i, j, "using gain = 1.0")
                gain[i,j] = 1.0

            if (((i*ny+j) % 1000) == 0):
                print("pixel", i, j,
                      "offset {0:.3f} variance {1:.3f} gain {2:.3f}".format(offset[i,j,],
                                                                            variance[i,j],
                                                                            gain[i,j]))

    if show_fit_plots:
        print("")
        for i in range(5):
            pyplot.figure()

            data_x = all_means[i,0,:]
            data_y = all_vars[i,0,:]
            fit = numpy.polyfit(data_x, data_y, 1)

            print(i, "gain {0:.3f}".format(fit[0]))
            pyplot.scatter(data_x,
                           data_y,
                           marker = 'o',
                           s = 2)

            xf = numpy.array([0, data_x[-1]])
            yf = xf * fit[0] + fit[1]
            
            pyplot.plot(xf, yf, color = 'blue')
            pyplot.xlabel("Mean Intensity (ADU).")
            pyplot.ylabel("Mean Variance (ADU).")
            
            pyplot.show()

    # Fit for relative QE.
    #
    # This uses the last of the files, which is assumed to be the brightest.
    #
    [n_frames, pixel_mean, pixel_var] = loadCalibrationData(scmos_files[-1])
    corrected_image = (pixel_mean - offset)/gain
    smoothed_image = scipy.ndimage.uniform_filter(corrected_image, size = 10, mode = 'nearest')
    relative_qe = corrected_image/smoothed_image
    
    return [offset, variance, gain, relative_qe]


def loadCalibrationData(filename, is_dark = False, print_roi_info = False, show_mean_plots = False):
    """
    Load data.
    
    Originally this was a list of length 3. Later we added a 4th element
    which is a dictionary containing some information about the camera ROI.
    """
    all_data = numpy.load(filename, allow_pickle = True)
    if (len(all_data) == 3):
        [data, x, xx] = all_data
    else:
        [data, x, xx, roi_dict] = all_data
        if print_roi_info:
            print("Calibration ROI info:")
            for key in sorted(roi_dict):
                print(key, roi_dict[key])
            print()

    # Originally data was just the number of frames, later it was changed to
    # an array containing the mean intensity in each frame.
    #
    if (data.size == 1):
        n_frames = data[0]
        mean_var = 0.0

    else:
        n_frames = data.size
        if not is_dark:
            mean_var = numpy.var(data)
        else:
            mean_var = 0.0
                
        print(filename, "mean intensity variance {0:.3f}".format(mean_var))
            
        if show_mean_plots:
            xv = numpy.arange(n_frames)
            pyplot.figure()
            pyplot.plot(xv, data)
            pyplot.xlabel("Frame")
            pyplot.ylabel("Mean Intensity (ADU)")
            pyplot.show()

    x = x.astype(numpy.float64)
    xx = xx.astype(numpy.float64)
    pixel_mean = x/float(n_frames)
    pixel_var = xx/float(n_frames) - pixel_mean * pixel_mean - mean_var

    return [n_frames, pixel_mean, pixel_var]


if (__name__ == "__main__"):

    import argparse

    parser = argparse.ArgumentParser(description = 'sCMOS camera calibration.')

    parser.add_argument('--results', dest='results', type=str, required=True,
                        help = "The name of the numpy format file to save the results in.")
    parser.add_argument('--cal', nargs = "*", dest='cal', type=str, required=True,
                        help = "Storm-control format calibration files, in order dark, light1, light2, ...")

    args = parser.parse_args()

    if os.path.exists(args.results):
        print("Calibration file already exists, please delete before proceeding.")
        exit()
    
    [offset, variance, gain, rqe] = cameraCalibration(args.cal)

    with open(args.results, "wb") as fp:
        pickle.dump([offset, variance, gain, rqe, 2], fp)

#
# The MIT License
#
# Copyright (c) 2017 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
