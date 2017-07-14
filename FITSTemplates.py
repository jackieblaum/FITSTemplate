#!/opt/local/bin/python

import sys
import os
from astropy.io import fits
from astropy import units as u
from astropy.coordinates import SkyCoord
import numpy as np
import scipy.ndimage.interpolation as spr
from astropy import wcs
import ConfigParser

# Global dictionary of fits header types
headers = {}
headers['TAN'] = ["RA---TAN","DEC--TAN"]
headers['AIT'] = ["RA---AIT","DEC--AIT"]
headers['GTAN'] = ["GLAT---TAN","GLON--TAN"]
headers['GAIT'] = ["GLAT---AIT","GLON--AIT"]

class FITSCore (object):

    def __init__ (self,\
                 paramfile="template.cfg",\
                 xsize=None,\
                 ysize=None,\
                 RA=None,\
                 dec=None,\
                 px_size=None,\
                 projection="TAN"):
        """
        Class to hold basic data on creating a FITS template. This class must
        be instantiated before any templates are generated.

        Constructor Arguments:
        ---------------------
        paramfile: Name of the parameter file holding information on the FITS file.

        If paramfile is not specified, other arguments may be given explicitly.
        
        xsize: Size of the FITS file, in pixels.
        ysize: Size of the FITS file in pixels.
        RA: Decimal representation of the target right ascension.
        dec: Decimal representation of the target declination.
        px_size: Angular size of the FITS pixels in degrees.
        projection: Projection on to the sky plane to be used:
           "TAN": Tangential projection, used for small areas
                "RA---TAN", "DEC--TAN"
           "AIT": Aitoff projection, used by Fermi-LAT
                "RA---AIT", "DEC--AIT"
           "GTAN": Tangential projection with galactic coordinates
                "GLAT---TAN", "GLON--TAN"
           "GAIT": Aitoff projection with galactic coordinates
                "GLAT---AIT", "GLON--AIT"

        Note that if both paramfile *and* the explicit arguments are given,
        the values in paramfile take priority.

        Methods:
        --------
        DiskTemplate: Generate a circular source with constant intensity.
        GaussianTemplate: Generate a circular source with a Gaussian intensity.
        EllipticalGaussianTemplate: Generate an elliptical source with a Gaussian
             intensity.
        """
        self._key = 0
        self.config_dict = dict()
        self.ts_dict = dict()
        if (os.path.isfile(paramfile)):
            config=ConfigParser.RawConfigParser()
            config.read(paramfile)
            self.xsize = config.getint("FOV","xsize")
            self.ysize = config.getint("FOV","ysize")
            self.RA_val = config.getfloat("FOV","RA_val")
            self.dec_val = config.getfloat("FOV","dec_val")
            self.px_size = config.getfloat("FOV","px_size")
            self.projection = ""
        else:
            self.xsize = int(xsize)
            self.ysize = int(ysize)
            self.RA_val = float(RA)
            self.dec_val = float(dec)
            self.px_size = float(px_size)
            self.projection = str(projection)
        try:
            self.header = headers[self.projection]
        except KeyError:
            print "Header type {0} not recognized. Defaulting to TAN projection."
            self.header = headers['TAN']
            
        # This should be a dictionary, shouldn't it?
        self.field=np.zeros((self.xsize,self.ysize))

        
    def _SaveToFITS (self, outname, overwrite):
        w = wcs.WCS(naxis=2)
        xvals = np.arange(0,self.xsize)
        yvals = np.arange(0,self.ysize)
        w.wcs.crval = [self.RA_val,self.dec_val]
        w.wcs.cdelt = np.array([self.px_size*-1.0,self.px_size])
        w.wcs.crpix = [0.5+self.xsize/2.0,0.5+self.ysize/2.0]
        w.wcs.ctype = self.header
        header = w.to_header()
        hdu = fits.PrimaryHDU(self.field,header=header)
        try:
            hdu.writeto(outname,clobber=overwrite)
        except IOError:
            print "Could not create file! {0} already exists. Try again with overwrite set to True.".format(outname)

            
    def DiskTemplate (self, radius, intensity, outname, overwrite=False):
        """
        Generate a circular source with constant intensity.

        Function Call:
        -------------
        FITSCore.DiskTemplate(radius,intensity,outname)

        Arguments:
        ---------
        radius: Radius of the disk, in pixels.
        intensity: Intensity of the source, in arbitrary units.
        outname: Name of the output file.
        overwrite(optional): If the output file exists, should it be overwritten?
             Defaults to False.
        """
        x_c = self.xsize/2.0-0.5
        y_c = self.ysize/2.0-0.5
        for x in range(0,self.xsize):
            for y in range(0,self.ysize):
                if ((x-x_c)**2 + (y-y_c) **2 <= radius**2):
                    self.field[x][y] = intensity
        if outname:
            self._SaveToFITS(outname,overwrite)

        
    def SplitDiskTemplate(self, radius, intensity_a, intensity_b, split_angle, outname, overwrite=False):
        """
        Generate a disk split between two different intensities.

        Function Call:
        -------------
        FITSCore.DiskTemplate(radius,intensity_a,intensity_b,split_angle,outname)

        Arguments:
        ---------
        radius: Radius of the disk, in pixels.
        intensity_a: Intensity of one half of the disk, in arbitrary units.
        intensity_b: Intensity of the other half of the disk, in arbitrary units.
        split_angle: Angle at which the dividing line between the two halves of the
         disk will be, in degrees clockwise from straight north-south.
        outname: File output name.
        overwite: If the output file exists, should it be overwritten? Defaults to False.
        """
        x_c = self.xsize/2.0-0.5
        y_c = self.ysize/2.0-0.5
        temp_field = np.zeros
        for x in range(0,self.xsize):
            for y in range(0,self.ysize):
                if (x-x_c)**2 + (y-y_c)**2 <= radius**2:
                    if y >= y_c:
                        self.field[x][y] = intensity_a
                    elif y < y_c:
                        self.field[x][y] = intensity_b
        # Now rotate
        spr.rotate(input = self.field,\
                                        angle = split_angle,\
                                        reshape = False,\
                                        output = self.field)
        # Kill any junk outside the intended radius
        for x in range(0,self.xsize):
            for y in range(0,self.ysize):
                if (x-x_c)**2 + (y-y_c)**2 > radius**2:
                    self.field[x][y] = 0
        if outname:
            self._SaveToFITS(outname,overwrite)

            
    def EllipticalGaussianTemplate(self, FWHM, peak, epsilon, theta, outname, overwrite=False):
        """
        Generate an elliptical source with a Gaussian intensity.

        Function Call:
        -------------
        FITSCore.EllipticalGaussianTemplate(FWHM,peak,epsilon,theta,outname)

        Arguments:
        ---------
        FWHM: Full-width half-maximum of the source, in pixels.
        peak: Peak value of the source brightness.
        epsilon: Eccentricity of the source. Throws ValueError if out of bounds
             (>1 or <0).
        theta: Source rotation angle, in degrees.
        outname: Name of the output file.
        overwrite(optional): If the output file exists, should it be overwritten?
             Defaults to False.        
        """
        # Throw ValueError if we're out of bounds for the eccentricity.
        if (epsilon > 1 or epsilon < 0):
            raise ValueError('Epsilon must be a value between 0 and 1.')
            
        # As defined on the CXC Sherpa website.
        x_c = self.xsize/2.0-0.5
        y_c = self.ysize/2.0-0.5
        FWHM=float(FWHM)
        peak=float(peak)
        theta=np.radians(theta)
        gauss_c = 2.7725887 # 4 log 2; relationship between FWHM and sigma
        ellip = float(1-epsilon)
        for x in range(0,self.xsize):
            for y in range(0,self.ysize):
                x_o = (x-x_c)*np.cos(theta) + (y-y_c)*np.sin(theta)
                y_o = (y-y_c)*np.cos(theta) - (x-x_c)*np.sin(theta)
                r = np.sqrt(((x_o**2 * ellip**2) + y_o**2)/ellip)
                self.field[x][y]=peak*np.e**(-gauss_c*(r/FWHM)**2)
        self._SaveToFITS(outname, overwrite)

        
    def GaussianTemplate (self, FWHM, peak, outname,overwrite=False):
        """
        Generate a circular source with a Gaussian intensity.

        Function Call:
        -------------
        FITSCore.GaussianTemplate(FWHM,peak,outname)

        Arguments:
        ---------
        FWHM: Full-width half-maximum of the source, in pixels.
        peak: Peak value of the source brightness.
        outname: Name of the output file.
        overwrite(optional): If the output file exists, should it be overwritten?
             Defaults to False.
        """
        self.EllipticalGaussianTemplate(FWHM,peak,0,0,outname,overwrite)

    def AnnularTemplate(self,r_in,r_out,intensity,outname,overwrite=False):
        """
        Generate an annular source.

        Function Call:
        -------------
        FITSCore.AnnularTemplate(r_in,r_out,intensity,outname,[outname=False])
        
        Arguments:
        ---------
        r_in: annulus inner radius
        r_out: annulus outer radius
        intensity: value to set template pixels to
        outname: Name of the outputfile
        overwite(optional): If the output file exists, should it be overwritten?
        
        """
        x_c = self.xsize/2.0-0.5
        y_c = self.ysize/2.0/0.5
        for x in range(0,self.xsize):
            for y in range(0,self.ysize):
                r = ((x-x_c)**2) + ((y-y_c)**2)
                if (r <= r_out and r >= r_in):                    
                    self.field[x][y] = intensity
        if outname:
            self._SaveToFITS(outname,overwrite)

    def AddArray(self,Array1,Array2,Startx,Starty):
        """
        Transforms an Array into an Template

        Function Call:
        -------------
        FITSCore.ArrayTemplate(Array1,Array2,Startx,Starty)
        
        Arguments:
        ---------
        Array1: The main(bigger) being added to array
        Array2: The Array(smaller) being added inside the first
        Startx: where the Array will start adding from x axis
        Starty: where the Array will start adding from the y axis(from the top)
        """
        def change(arr,x,y,val):
            arr[y][x] = val
            return arr
        Temp1 = Array1
        Temp2 = Array2
        Com =np.zeros((len(Array1),len(Array1[1])))
        x1 = Startx
        y1 = Starty
        x2 = 0
        y2 = 0
        row = 0
        point1 = Array1[y1][x1]
        point2 = Array2[y2][x2]
        for i in range(len(Array2[1])-1):
            for i in range(len(Array2)-row):
                if Array1[y1][x1] != Array2[y2][x2]:
                    change(Array1,x1,y1,Array2[y2][x2])
                y1 += 1
                y2 += 1
            y1 -= 1
            y2 -= 1
            for i in range(len(Array2[1])-row):
                if Array1[y1][x1] != Array2[y2][x2]:
                    change(Array1,x1,y1,Array2[y2][x2])
                x1 += 1
                x2 += 1
            x1 -= 1
            x2 -= 1
            row += 1
        return(Array1)
    
    def Swaz(self,Array):
        """
        Checks around an Array starting from the middle.

        Function Call:
        -------------
        FITSCore.Swaz(Array)"""
        self.config_dict[self._key] = Array
        def Centerpoint(arr):
            y = len(arr)/2
            x = len(arr[1])/2
            return(x,y)
        def change(arr,x,y,val):
            arr[y][x] = val
            return arr
        def point(x,y):
            x = x
            y = y
            return(x,y)
        def ReadFile(filename,compare):
            with open(filename) as F:
                for lines in F:
                    if lines.strip('\n') == compare:
                        return(True)
                    else:
                        return(False)
        x,y = Centerpoint(Array)
        Center = Array[y][x]
        def check(x,y):
            self.config_dict[self._key] = Array
            point = Array[y][x]
            #if ReadFile(filename,compare) == True
            change(Array,x,y,1)
            y-=1
            change(Array,x,y,1)
            x-=1
            change(Array,x,y,1)
            y+=1
            change(Array,x,y,1)
            x+=1
            self._key+=1
        check(x,y)
        RD = 0
        DL = 0
        LU = 0
        UR = 0
        #checks to the right and down from the middle
        while RD <= len(Array)*len(Array[1]):
            RD+=1
            try:
                x+=1
                check(x,y)
                x+=1
                check(x,y)
                while RD <= len(Array)*len(Array[1]):
                    y+=1
                    check(x,y)
            except IndexError:
                y = len(Array)/2
                try:
                    continue
                except IndexError:
                    break
        #checks down and to the left (and bottom right 4 rows.
        x,y = Centerpoint(Array)
        while DL <= len(Array)*len(Array[1]):
            DL+=1
            try:
                if y > 0:
                    y+=1
                    check(x,y)
            except IndexError:
                break
            while DL <= len(Array)*len(Array[1]):
                try:
                    if x > 1:
                        x-=1
                        check(x,y)
                    else:
                        x = len(Array[1])/2
                        break
                except IndexError:                   
                    break
        #checks to the left and up
        x,y = Centerpoint(Array)
        while LU <= len(Array)*len(Array[1]):
            LU+=1
            if x > 1:
                x-=1
                check(x,y)
            else:
                break
            while LU <= len(Array)*len(Array[1]):
                if y > 1:
                    y -= 1
                    check(x,y)
                else:
                    y = len(Array)/2
                    break
        #checks up and to the right
        x,y = Centerpoint(Array)
        while UR <= len(Array)*len(Array[1]):
            UR +=1
            try:
                if y > 1:
                    y-=1
                    check(x,y)
                while UR <= len(Array)*len(Array[1]):
                    if x <= len(Array[1]):
                        x+=1
                        check(x,y)
            except IndexError:
                x = len(Array[1])/2
                continue
        print(self.ts_dict)
        return(Array)
# FITSTemplate.py ends here