# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TerrainModelMaker
                                 A QGIS plugin
 Creates laser cuttable terrain models from contour data
                              -------------------
        begin                : 2023-09-15
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Miklos Hamar
        email                : szad5615@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.core import (
    QgsRectangle, 
    QgsDistanceArea, 
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject
)

# Standard paper sizes in mm (width, height)
PAPER_SIZES = {
    'A0': (841, 1189),
    'A1': (594, 841),
    'A2': (420, 594),
    'A3': (297, 420),
    'A4': (210, 297),
    'A5': (148, 210),
    'Letter': (216, 279),
    'Legal': (216, 356),
    'Tabloid': (279, 432),
    'Custom': (0, 0)
}

def calculate_rectangle_dimensions(rect, crs):
    """
    Calculate the dimensions of a rectangle in meters
    
    :param rect: QgsRectangle to measure
    :param crs: Coordinate reference system of the rectangle
    :return: tuple of (width, height, area) in meters/square meters
    """
    if not rect or not rect.isFinite():
        return 0, 0, 0
        
    # Create a distance calculator
    distance_calc = QgsDistanceArea()
    distance_calc.setSourceCrs(crs, QgsProject.instance().transformContext())
    distance_calc.setEllipsoid(QgsProject.instance().ellipsoid())
    
    # Create a polygon from the rectangle
    points = [
        rect.xMinimum(), rect.yMinimum(),
        rect.xMaximum(), rect.yMinimum(),
        rect.xMaximum(), rect.yMaximum(),
        rect.xMinimum(), rect.yMaximum(),
        rect.xMinimum(), rect.yMinimum()
    ]
    
    geom = QgsGeometry.fromPolygonXY([[QgsPointXY(points[i], points[i+1]) for i in range(0, len(points)-1, 2)]])
    
    # Calculate width, height, and area
    width = distance_calc.measureLine([QgsPointXY(rect.xMinimum(), rect.yMinimum()), 
                                    QgsPointXY(rect.xMaximum(), rect.yMinimum())])
    height = distance_calc.measureLine([QgsPointXY(rect.xMinimum(), rect.yMinimum()), 
                                     QgsPointXY(rect.xMinimum(), rect.yMaximum())])
    area = distance_calc.measureArea(geom)
    
    return width, height, area

def calculate_scale(real_width, real_height, paper_width, paper_height, margin_percent=5):
    """
    Calculate an appropriate scale to fit real-world dimensions onto paper
    
    :param real_width: Real-world width in meters
    :param real_height: Real-world height in meters
    :param paper_width: Paper width in mm
    :param paper_height: Paper height in mm
    :param margin_percent: Percentage of margin to leave around the edges (default: 5%)
    :return: The calculated scale (1:x) as an integer
    """
    if not real_width or not real_height or not paper_width or not paper_height:
        return 0
        
    # Convert margin percentage to a multiplier
    margin_multiplier = 1 - (margin_percent / 100)
    
    # Available paper dimensions after considering margins (mm)
    avail_paper_width = paper_width * margin_multiplier
    avail_paper_height = paper_height * margin_multiplier
    
    # Convert real-world dimensions to mm (1m = 1000mm)
    real_width_mm = real_width * 1000
    real_height_mm = real_height * 1000
    
    # Calculate potential scales
    scale_by_width = real_width_mm / avail_paper_width
    scale_by_height = real_height_mm / avail_paper_height
    
    # Use the more restrictive scale to ensure it fits on paper
    scale = max(scale_by_width, scale_by_height)
    
    # Round to a nice, even number (nearest 100)
    rounded_scale = round(scale / 100) * 100
    
    # Ensure we have a minimum scale
    return max(100, rounded_scale)

def calculate_contour_step(scale, sheet_thickness_mm, min_height_diff_mm=1.0):
    """
    Calculate the required contour step based on the scale and sheet thickness
    
    :param scale: The model scale (1:x)
    :param sheet_thickness_mm: Thickness of the sheet material in mm
    :param min_height_diff_mm: Minimum height difference between model layers in mm (default: 1.0)
    :return: The required contour step in map units
    """
    if not scale or not sheet_thickness_mm:
        return 0
        
    # Calculate actual height difference in real-world units
    # If sheet is 3mm thick and scale is 1:1000, each sheet represents 3m in height
    real_height_diff = sheet_thickness_mm * scale / 1000  # Convert mm to m
    
    # Ensure we meet the minimum height difference
    min_real_height_diff = min_height_diff_mm * scale / 1000  # Convert mm to m
    contour_step = max(real_height_diff, min_real_height_diff)
    
    # Round to a nice number
    if contour_step < 1:
        # Round to nearest 0.1, 0.2, 0.5
        if contour_step < 0.1:
            return 0.1
        elif contour_step < 0.2:
            return 0.2
        elif contour_step < 0.5:
            return 0.5
        else:
            return 0.5
    else:
        # Round to nearest 1, 2, 5, 10, 20, 50, etc.
        if contour_step < 2:
            return 1
        elif contour_step < 5:
            return 2 if contour_step < 3.5 else 5
        elif contour_step < 10:
            return 5
        elif contour_step < 20:
            return 10
        elif contour_step < 50:
            return 20
        else:
            # Round to nearest 50
            return round(contour_step / 50) * 50 