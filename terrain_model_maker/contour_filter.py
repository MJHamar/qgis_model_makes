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

import os
import tempfile
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsGeometry,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsPointXY,
    QgsLineString
)
from PyQt5.QtCore import QVariant

def find_contour_layer(project=None):
    """
    Find a contour layer in the current project.
    
    :param project: QgsProject instance, uses the current project if None
    :return: The contour layer or None if not found
    """
    if project is None:
        project = QgsProject.instance()
    
    # Potential contour layer names
    contour_names = ["contour", "elevation", "isoline"]
    
    # Check for layers with these names
    for layer_id, layer in project.mapLayers().items():
        if isinstance(layer, QgsVectorLayer) and layer.geometryType() == QgsWkbTypes.LineGeometry:
            layer_name = layer.name().lower()
            
            # Direct match with known contour layer names
            if any(name in layer_name for name in contour_names):
                return layer
            
            # Check if layer has elevation or altitude field
            fields = [field.name().lower() for field in layer.fields()]
            if any(name in ' '.join(fields) for name in ["elev", "alt", "height", "z"]):
                return layer
    
    return None

def filter_contours_by_interval(input_layer, interval, region_rect=None, region_crs=None, elevation_field=None):
    """
    Filter contour lines to keep only those at the specified elevation interval.
    
    :param input_layer: Input contour QgsVectorLayer
    :param interval: Elevation interval to filter by (e.g., 5 for every 5 meter contour)
    :param region_rect: Optional QgsRectangle to filter by region
    :param region_crs: The CRS of the rectangle (if different from contour layer)
    :param elevation_field: Name of the field containing elevation values, will try to detect if None
    :return: A new in-memory layer with filtered contours
    """
    if not input_layer or not input_layer.isValid():
        return None
    
    # Detect elevation field if not specified
    if elevation_field is None:
        possible_names = ["elev", "elevation", "alt", "altitude", "height", "z", "level"]
        for field in input_layer.fields():
            field_name = field.name().lower()
            if any(name in field_name for name in possible_names):
                elevation_field = field.name()
                break
        
        # If still not found, try to use the first numeric field
        if elevation_field is None:
            for field in input_layer.fields():
                if field.type() in [QVariant.Int, QVariant.Double, QVariant.LongLong]:
                    elevation_field = field.name()
                    break
    
    if elevation_field is None:
        raise ValueError("Could not detect elevation field in contour layer")
    
    # Create a spatial filter request if region is specified
    request = QgsFeatureRequest()
    if region_rect:
        # Ensure rectangle is in the layer's CRS
        if region_crs and region_crs.authid() != input_layer.crs().authid():
            transform = QgsCoordinateTransform(
                region_crs,
                input_layer.crs(),
                QgsProject.instance()
            )
            region_rect_transformed = transform.transformBoundingBox(region_rect)
            request.setFilterRect(region_rect_transformed)
        else:
            request.setFilterRect(region_rect)
    
    # Find the minimum elevation value in the layer (or within the region if specified)
    min_elevation = None
    for feature in input_layer.getFeatures(request):
        if feature[elevation_field] is not None:  # Check for null values
            elev_value = float(feature[elevation_field])  # Convert to float for consistent comparison
            if min_elevation is None or elev_value < min_elevation:
                min_elevation = elev_value
    
    if min_elevation is None:
        raise ValueError("Could not determine minimum elevation in contour layer")
    
    # Create an expression to filter by elevation interval relative to the minimum elevation
    # This selects contours that are min_elevation, min_elevation + interval, min_elevation + 2*interval, etc.
    expression = f"({elevation_field} - {min_elevation}) % {interval} = 0"
    
    # Add expression filter to the request
    request.setFilterExpression(expression)
    
    # Create a new memory layer to store filtered contours
    filtered_layer = QgsVectorLayer(
        f"LineString?crs={input_layer.crs().authid()}",
        f"Filtered Contours ({interval}m from {min_elevation}m)",
        "memory"
    )
    
    # Copy fields from input layer
    filtered_layer.dataProvider().addAttributes(input_layer.fields())
    filtered_layer.updateFields()
    
    # Extract filtered features
    filtered_layer.startEditing()
    for feature in input_layer.getFeatures(request):
        filtered_layer.addFeature(feature)
    filtered_layer.commitChanges()
    
    return filtered_layer

def export_contours_to_file(layer, output_path, format="CSV", rect=None, rect_crs=None):
    """
    Export contour lines to a file for laser cutting.
    
    :param layer: QgsVectorLayer containing contour lines
    :param output_path: Path to save the output file
    :param format: Output format ("CSV", "DXF", or "SVG")
    :param rect: Optional QgsRectangle for spatial filtering
    :param rect_crs: CRS of the rectangle (if different from layer CRS)
    :return: True if successful, False otherwise
    """
    if not layer or not layer.isValid():
        return False
    
    # Create the output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # If rect is provided, remap contours properly using our new function
    remapped_contours = None
    if rect:
        try:
            remapped_contours = remap_contours_to_rect(layer, rect, rect_crs)
        except Exception as e:
            print(f"Error remapping contours: {e}")
            # Continue with normal export if remapping fails
    
    if format.upper() == "CSV":
        # For CSV, we'll create a text file with coordinates
        try:
            with open(output_path, 'w') as f:
                # Write header
                f.write("elevation,part,x,y\n")
                
                # Process features - either remapped or directly from layer
                if remapped_contours:
                    # Use the remapped contours
                    for elevation, geom in remapped_contours:
                        part_idx = 0
                        
                        if geom.wkbType() == QgsWkbTypes.MultiLineString:
                            for part_idx, part in enumerate(geom.asMultiPolyline()):
                                for point in part:
                                    f.write(f"{elevation},{part_idx},{point.x()},{point.y()}\n")
                        else:
                            points = geom.asPolyline()
                            for point in points:
                                f.write(f"{elevation},0,{point.x()},{point.y()}\n")
                else:
                    # Process features directly from layer
                    for feature in layer.getFeatures():
                        # Verify we have an elevation attribute
                        elevation = None
                        if 'elevation' in feature.fields().names():
                            elevation = feature['elevation']
                        elif 'elev' in feature.fields().names():
                            elevation = feature['elev']
                        else:
                            # Try to find any field that might contain elevation
                            for field_name in feature.fields().names():
                                if any(substr in field_name.lower() for substr in ['elev', 'alt', 'height', 'z']):
                                    elevation = feature[field_name]
                                    break
                            
                        if elevation is None:
                            # If still no elevation found, use a default or skip
                            elevation = 0
                        
                        geom = feature.geometry()
                        if not geom or not geom.isGeosValid():
                            continue
                            
                        if geom.isMultipart():
                            # Handle multipart geometries (multiple lines per feature)
                            multiparts = geom.asMultiPolyline()
                            if not multiparts:
                                continue
                                
                            for part_idx, part in enumerate(multiparts):
                                if not part:
                                    continue
                                    
                                for point in part:
                                    f.write(f"{elevation},{part_idx},{point.x()},{point.y()}\n")
                        else:
                            # Handle single part geometries
                            points = geom.asPolyline()
                            if not points:
                                continue
                                
                            for point in points:
                                f.write(f"{elevation},0,{point.x()},{point.y()}\n")
            return True
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error exporting to CSV: {e}\n{error_trace}")
            return False
            
    elif format.upper() == "DXF":
        # For DXF, use our custom DXF writer
        try:
            # Create DXF file directly
            with open(output_path, 'w') as f:
                # Write DXF header
                f.write("0\nSECTION\n")
                f.write("2\nHEADER\n")
                f.write("9\n$ACADVER\n1\nAC1009\n")  # AutoCAD R12 format
                f.write("0\nENDSEC\n")
                
                # Write entities section
                f.write("0\nSECTION\n")
                f.write("2\nENTITIES\n")
                
                # Process contours - either remapped or directly from layer
                if remapped_contours:
                    # Use the remapped contours
                    for elevation, geom in remapped_contours:
                        # Get polylines to export
                        polylines = []
                        
                        if geom.wkbType() == QgsWkbTypes.MultiLineString:
                            for part in geom.asMultiPolyline():
                                if part and len(part) >= 2:
                                    polylines.append(part)
                        else:
                            line = geom.asPolyline()
                            if line and len(line) >= 2:
                                polylines.append(line)
                        
                        # Write each polyline as a DXF POLYLINE
                        for i, polyline in enumerate(polylines):
                            # Write POLYLINE entity
                            f.write("0\nPOLYLINE\n")
                            # Common polyline attributes
                            f.write("8\nCONTOUR\n")  # Layer name
                            f.write("66\n1\n")  # Vertices follow flag
                            f.write("70\n0\n")  # Open polyline
                            
                            # Add elevation as attribute
                            f.write("38\n{:.3f}\n".format(float(elevation)))
                            
                            # Write vertices
                            for point in polyline:
                                f.write("0\nVERTEX\n")
                                f.write("8\nCONTOUR\n")
                                f.write("10\n{:.6f}\n".format(point.x()))
                                f.write("20\n{:.6f}\n".format(point.y()))
                                f.write("30\n{:.6f}\n".format(float(elevation)))
                            
                            # End polyline
                            f.write("0\nSEQEND\n")
                else:
                    # Process features directly from layer
                    for feature in layer.getFeatures():
                        # Check for elevation field
                        elevation = None
                        if 'elevation' in feature.fields().names():
                            elevation = feature['elevation']
                        elif 'elev' in feature.fields().names():
                            elevation = feature['elev']
                        else:
                            # Try to find any field with elevation info
                            for field_name in feature.fields().names():
                                if any(substr in field_name.lower() for substr in ['elev', 'alt', 'height', 'z']):
                                    elevation = feature[field_name]
                                    break
                        
                        if elevation is None:
                            elevation = 0  # Default if no elevation found
                        
                        geom = feature.geometry()
                        
                        # Skip invalid geometries
                        if not geom or not geom.isGeosValid():
                            continue
                        
                        # Get polylines to export
                        polylines = []
                        
                        if geom.isMultipart():
                            # Handle multipart geometries
                            for part in geom.asMultiPolyline():
                                if part and len(part) >= 2:
                                    polylines.append(part)
                        else:
                            # Handle single part geometries
                            line = geom.asPolyline()
                            if line and len(line) >= 2:
                                polylines.append(line)
                        
                        # Write each polyline as a DXF POLYLINE
                        for i, polyline in enumerate(polylines):
                            # Write POLYLINE entity
                            f.write("0\nPOLYLINE\n")
                            # Common polyline attributes
                            f.write("8\nCONTOUR\n")  # Layer name
                            f.write("66\n1\n")  # Vertices follow flag
                            f.write("70\n0\n")  # Open polyline
                            
                            # Add elevation as attribute
                            f.write("38\n{:.3f}\n".format(float(elevation)))
                            
                            # Write vertices
                            for point in polyline:
                                f.write("0\nVERTEX\n")
                                f.write("8\nCONTOUR\n")
                                f.write("10\n{:.6f}\n".format(point.x()))
                                f.write("20\n{:.6f}\n".format(point.y()))
                                f.write("30\n{:.6f}\n".format(float(elevation)))
                            
                            # End polyline
                            f.write("0\nSEQEND\n")
                
                # End entities section
                f.write("0\nENDSEC\n")
                
                # End of file
                f.write("0\nEOF\n")
            
            return True
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error exporting to DXF: {e}\n{error_trace}")
            return False
            
    elif format.upper() == "SVG":
        # For SVG, we'll create a simple SVG file with contour lines
        try:
            # Determine dimensions - either from remapped contours or from layer
            if remapped_contours and remapped_contours:
                # Get extent from remapped contours
                extent = QgsRectangle()
                for _, geom in remapped_contours:
                    if not extent.isEmpty():
                        extent.combineExtentWith(geom.boundingBox())
                    else:
                        extent = geom.boundingBox()
                
                # If empty, fallback to layer extent
                if extent.isEmpty():
                    extent = layer.extent()
            else:
                # Use layer extent
                extent = layer.extent()
                
            width = extent.width()
            height = extent.height()
            
            # Compute scaling to fit SVG canvas (assumed 800x600)
            svg_width = 800
            svg_height = 600
            scale_x = svg_width / width if width > 0 else 1
            scale_y = svg_height / height if height > 0 else 1
            scale = min(scale_x, scale_y) * 0.9  # 90% to leave margin
            
            # Compute translation to center in SVG canvas
            translate_x = svg_width / 2 - scale * (extent.xMinimum() + width / 2)
            translate_y = svg_height / 2 + scale * (extent.yMinimum() + height / 2)
            
            # Start SVG file
            with open(output_path, 'w') as f:
                f.write(f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}">\n')
                
                # Group with transform to adjust coordinates
                f.write(f'<g transform="translate({translate_x},{translate_y}) scale({scale},-{scale})">\n')
                
                # Process contours - either remapped or directly from layer
                if remapped_contours:
                    # Use the remapped contours
                    for elevation, geom in remapped_contours:
                        # Get path data for SVG
                        path_data = ""
                        
                        if geom.wkbType() == QgsWkbTypes.MultiLineString:
                            for part in geom.asMultiPolyline():
                                if not part or len(part) < 2:
                                    continue
                                    
                                path_data += f"M {part[0].x()},{part[0].y()} "
                                for point in part[1:]:
                                    path_data += f"L {point.x()},{point.y()} "
                        else:
                            line = geom.asPolyline()
                            if not line or len(line) < 2:
                                continue
                                
                            path_data += f"M {line[0].x()},{line[0].y()} "
                            for point in line[1:]:
                                path_data += f"L {point.x()},{point.y()} "
                        
                        # Only add path if we have data
                        if path_data:
                            # Use elevation for styling (eg. as color or class)
                            elev_color = f"#{int(elevation) % 256:02x}8080"  # Simple color based on elevation
                            f.write(f'<path d="{path_data}" fill="none" stroke="{elev_color}" stroke-width="0.5" data-elevation="{elevation}" />\n')
                else:
                    # Process features directly from layer
                    for feature in layer.getFeatures():
                        # Check for elevation field
                        elevation = None
                        if 'elevation' in feature.fields().names():
                            elevation = feature['elevation']
                        elif 'elev' in feature.fields().names():
                            elevation = feature['elev']
                        else:
                            # Try to find any field with elevation info
                            for field_name in feature.fields().names():
                                if any(substr in field_name.lower() for substr in ['elev', 'alt', 'height', 'z']):
                                    elevation = feature[field_name]
                                    break
                        
                        if elevation is None:
                            elevation = 0  # Default if no elevation found
                        
                        geom = feature.geometry()
                        
                        # Skip invalid geometries
                        if not geom or not geom.isGeosValid():
                            continue
                        
                        # Get path data for SVG
                        path_data = ""
                        
                        try:
                            if geom.isMultipart():
                                # Handle multipart geometries
                                multi_line = geom.asMultiPolyline()
                                if not multi_line:
                                    continue
                                    
                                for part in multi_line:
                                    if not part or len(part) < 2:
                                        continue
                                        
                                    path_data += f"M {part[0].x()},{part[0].y()} "
                                    for point in part[1:]:
                                        path_data += f"L {point.x()},{point.y()} "
                            else:
                                # Handle single part geometries
                                line = geom.asPolyline()
                                if not line or len(line) < 2:
                                    continue
                                    
                                path_data += f"M {line[0].x()},{line[0].y()} "
                                for point in line[1:]:
                                    path_data += f"L {point.x()},{point.y()} "
                            
                            # Only add path if we have data
                            if path_data:
                                # Use elevation for styling (eg. as color or class)
                                elev_color = f"#{int(elevation) % 256:02x}8080"  # Simple color based on elevation
                                f.write(f'<path d="{path_data}" fill="none" stroke="{elev_color}" stroke-width="0.5" data-elevation="{elevation}" />\n')
                        
                        except Exception as path_error:
                            print(f"Error creating path for feature: {path_error}")
                            continue
                
                # Close group and SVG
                f.write('</g>\n')
                f.write('</svg>\n')
            
            return True
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error exporting to SVG: {e}\n{error_trace}")
            return False
    
    else:
        print(f"Unsupported export format: {format}")
        return False

def remap_contours_to_rect_sequential(contour_layer, rect, region_crs=None):
    """
    Improved implementation that follows contours sequentially.
    This function follows contours sequentially, creating connections along
    the rectangle boundary when contours exit and re-enter the rectangle.
    
    :param contour_layer: QgsVectorLayer containing contour lines
    :param rect: QgsRectangle defining the boundary
    :param region_crs: CRS of the rectangle (if different from contour layer)
    :return: List of tuples (elevation, geometry) with remapped geometries
    """
    results = []
    
    # Ensure rectangle and layer have same CRS
    if region_crs and region_crs.authid() != contour_layer.crs().authid():
        transform = QgsCoordinateTransform(
            region_crs,
            contour_layer.crs(),
            QgsProject.instance()
        )
        transformed_rect = transform.transformBoundingBox(rect)
    else:
        transformed_rect = rect
    
    # Create rectangle geometry for intersection tests
    rect_geom = QgsGeometry.fromRect(transformed_rect)
    
    # Create spatial filter to get features that intersect the rectangle
    request = QgsFeatureRequest()
    request.setFilterRect(transformed_rect)
    
    # Process each contour feature
    for feature in contour_layer.getFeatures(request):
        # Get elevation
        elevation = None
        if 'elevation' in feature.fields().names():
            elevation = feature['elevation']
        elif 'elev' in feature.fields().names():
            elevation = feature['elev']
        else:
            # Try to find any field with elevation info
            for field_name in feature.fields().names():
                if any(substr in field_name.lower() for substr in ['elev', 'alt', 'height', 'z', 'level']):
                    elevation = feature[field_name]
                    break
        
        if elevation is None:
            elevation = 0  # Default if no elevation found
        
        # Process geometry based on type
        geom = feature.geometry()
        if not geom or not geom.isGeosValid():
            continue
            
        # If geometry is entirely within the rectangle, just add it as is
        if geom.within(rect_geom):
            results.append((elevation, geom))
            continue
            
        # If geometry doesn't intersect the rectangle at all, skip it
        if not geom.intersects(rect_geom):
            continue
        
        # Process different geometry types
        if geom.wkbType() == QgsWkbTypes.LineString:
            # Process single linestring
            process_contour_sequential(geom, elevation, transformed_rect, results)
            
        elif geom.wkbType() == QgsWkbTypes.MultiLineString:
            # Process each part of the multilinestring separately
            parts = geom.asMultiPolyline()
            for part in parts:
                if len(part) >= 2:
                    line_geom = QgsGeometry.fromPolylineXY(part)
                    process_contour_sequential(line_geom, elevation, transformed_rect, results)
    
    return results

def process_contour_sequential(line_geom, elevation, rect, results):
    """
    Process a single contour linestring, following it and creating proper
    boundary connections where it exits and re-enters the rectangle.
    
    :param line_geom: QgsGeometry of type LineString
    :param elevation: Elevation value for this contour
    :param rect: QgsRectangle defining the boundary
    :param results: List to append results to
    """
    # Skip invalid geometries
    if not line_geom or not line_geom.isGeosValid():
        return
        
    # Create rectangle geometry for intersection tests
    rect_geom = QgsGeometry.fromRect(rect)
    
    # Get line vertices
    vertices = line_geom.asPolyline()
    if len(vertices) < 2:
        return
    
    # Initialize processing variables
    current_contour = []      # Current contour being built
    last_boundary_point = None  # Last point where contour exited boundary
    inside_boundary = False   # Whether we're currently inside the boundary
    
    # Check if the starting point is inside the rectangle
    inside_boundary = rect.contains(vertices[0].x(), vertices[0].y())
    
    # Process each line segment in the contour
    for i in range(len(vertices) - 1):
        start_point = vertices[i]
        end_point = vertices[i + 1]
        
        start_inside = rect.contains(start_point.x(), start_point.y())
        end_inside = rect.contains(end_point.x(), end_point.y())
        
        # Create line segment geometry for intersection testing
        segment_geom = QgsGeometry.fromPolylineXY([start_point, end_point])
        
        # Case 1: Both points inside - add segment normally
        if start_inside and end_inside:
            if not inside_boundary:
                # We've just entered the boundary
                inside_boundary = True
                
                # If we have a last_boundary_point, we need to connect it
                if last_boundary_point:
                    # Find exact intersection point with boundary
                    intersection = segment_geom.intersection(rect_geom)
                    if intersection.type() == QgsGeometry.Point:
                        # Add a connection along the boundary
                        entry_point = intersection.asPoint()
                        boundary_connection = create_boundary_connection(last_boundary_point, entry_point, rect)
                        
                        # Add the boundary connection and the entry point to the current contour
                        current_contour.extend(boundary_connection)
                        current_contour.append(entry_point)
                        
                        # Reset last_boundary_point
                        last_boundary_point = None
                    else:
                        # Start a new contour if we can't find a clean intersection
                        if current_contour:
                            if len(current_contour) >= 2:
                                results.append((elevation, QgsGeometry.fromPolylineXY(current_contour)))
                            current_contour = []
                        
                        # Add the start point to begin a new contour
                        current_contour.append(start_point)
                else:
                    # Just starting a new contour inside the boundary
                    if not current_contour:
                        current_contour.append(start_point)
            
            # Always add the end point if we're inside
            current_contour.append(end_point)
            
        # Case 2: Start inside, end outside - exiting the boundary
        elif start_inside and not end_inside:
            inside_boundary = False
            
            # Find exact intersection point with boundary
            intersection = segment_geom.intersection(rect_geom)
            if intersection.type() == QgsGeometry.Point:
                exit_point = intersection.asPoint()
                current_contour.append(exit_point)
                
                # Save the exit point for later if we re-enter
                last_boundary_point = exit_point
            else:
                # If we can't find a clean intersection, just use the start point
                # (should rarely happen)
                if start_point not in current_contour:
                    current_contour.append(start_point)
            
            # Save the current contour if it has enough points
            if len(current_contour) >= 2:
                results.append((elevation, QgsGeometry.fromPolylineXY(current_contour)))
            
            # Reset the current contour
            current_contour = []
            
        # Case 3: Start outside, end inside - entering the boundary
        elif not start_inside and end_inside:
            inside_boundary = True
            
            # Find exact intersection point with boundary
            intersection = segment_geom.intersection(rect_geom)
            if intersection.type() == QgsGeometry.Point:
                entry_point = intersection.asPoint()
                
                # If we have a last_boundary_point, we need to connect it
                if last_boundary_point:
                    # Create a new contour with the boundary connection
                    boundary_connection = create_boundary_connection(last_boundary_point, entry_point, rect)
                    
                    # Ensure we have at least 2 points
                    if boundary_connection and len(boundary_connection) >= 2:
                        # Start a new contour with the boundary connection
                        current_contour = boundary_connection.copy()
                        
                    else:
                        # If no valid boundary connection, just start a new contour
                        current_contour = [entry_point]
                else:
                    # No previous exit point, just start a new contour
                    current_contour = [entry_point]
                
                # Always add the end point
                current_contour.append(end_point)
                
                # Reset last_boundary_point
                last_boundary_point = None
            else:
                # If we can't find a clean intersection, just start a new contour with the end point
                current_contour = [end_point]
                
        # Case 4: Both points outside - skip this segment entirely
        else:
            # Check if the segment intersects the rectangle (crosses through it)
            if segment_geom.crosses(rect_geom):
                # Find intersection points
                intersection = segment_geom.intersection(rect_geom)
                
                # Handle different intersection types
                if intersection.type() == QgsGeometry.Point:
                    # Just one intersection point - shouldn't happen with a rectangle
                    # but handle it anyway
                    point = intersection.asPoint()
                    
                    # Update last_boundary_point
                    last_boundary_point = point
                    
                elif intersection.wkbType() == QgsWkbTypes.MultiPoint:
                    # Multiple intersection points (entering and exiting)
                    points = intersection.asMultiPoint()
                    
                    if len(points) >= 2:
                        # Sort the points by distance from start_point
                        points.sort(key=lambda p: ((p.x() - start_point.x())**2 + (p.y() - start_point.y())**2)**0.5)
                        
                        # Add a new contour for the section inside the rectangle
                        inside_section = [points[0]] + points[1:2]
                        
                        if len(inside_section) >= 2:
                            results.append((elevation, QgsGeometry.fromPolylineXY(inside_section)))
                        
                        # Update last_boundary_point to the last intersection
                        last_boundary_point = points[-1]
                        
                        # Note: We don't need to update current_contour here because
                        # we're still outside the rectangle
    
    # Save any remaining contour
    if current_contour and len(current_contour) >= 2:
        results.append((elevation, QgsGeometry.fromPolylineXY(current_contour)))

def create_boundary_connection(start_point, end_point, rect):
    """
    Create a path along the rectangle boundary from start_point to end_point.
    
    :param start_point: QgsPointXY starting point (must be on boundary)
    :param end_point: QgsPointXY ending point (must be on boundary)
    :param rect: QgsRectangle
    :return: List of QgsPointXY forming the path along the boundary
    """
    # Extract rectangle coordinates
    x_min = rect.xMinimum()
    y_min = rect.yMinimum()
    x_max = rect.xMaximum()
    y_max = rect.yMaximum()
    
    # Determine which sides the points are on
    start_side = get_boundary_side(start_point, rect)
    end_side = get_boundary_side(end_point, rect)
    
    # If points are on the same side, connect directly
    if start_side == end_side:
        return [start_point, end_point]
    
    # Define rectangle corners
    corners = {
        "bottom_left": QgsPointXY(x_min, y_min),
        "bottom_right": QgsPointXY(x_max, y_min),
        "top_right": QgsPointXY(x_max, y_max),
        "top_left": QgsPointXY(x_min, y_max)
    }
    
    # Determine which corners to visit when going from one side to another
    path_corners = []
    
    # Going counter-clockwise
    if start_side == "left":
        if end_side == "bottom":
            path_corners = [corners["bottom_left"]]
        elif end_side == "right":
            path_corners = [corners["top_left"], corners["top_right"]]
        elif end_side == "top":
            path_corners = [corners["top_left"]]
    
    elif start_side == "bottom":
        if end_side == "right":
            path_corners = [corners["bottom_right"]]
        elif end_side == "top":
            path_corners = [corners["bottom_left"], corners["top_left"]]
        elif end_side == "left":
            path_corners = [corners["bottom_left"]]
    
    elif start_side == "right":
        if end_side == "top":
            path_corners = [corners["top_right"]]
        elif end_side == "left":
            path_corners = [corners["top_right"], corners["top_left"]]
        elif end_side == "bottom":
            path_corners = [corners["bottom_right"]]
    
    elif start_side == "top":
        if end_side == "left":
            path_corners = [corners["top_left"]]
        elif end_side == "bottom":
            path_corners = [corners["top_left"], corners["bottom_left"]]
        elif end_side == "right":
            path_corners = [corners["top_right"]]
    
    # Create the complete path
    path = [start_point] + path_corners + [end_point]
    return path

def get_boundary_side(point, rect):
    """
    Determine which side of the rectangle a point is on.
    
    :param point: QgsPointXY
    :param rect: QgsRectangle
    :return: String "left", "right", "top", or "bottom"
    """
    x, y = point.x(), point.y()
    x_min, y_min = rect.xMinimum(), rect.yMinimum()
    x_max, y_max = rect.xMaximum(), rect.yMaximum()
    
    # Tolerance for floating point comparisons
    epsilon = 1e-6
    
    if abs(x - x_min) < epsilon:
        return "left"
    elif abs(x - x_max) < epsilon:
        return "right"
    elif abs(y - y_min) < epsilon:
        return "bottom"
    elif abs(y - y_max) < epsilon:
        return "top"
    else:
        # The point is not on the boundary - in this case we'll use
        # the closest side as a fallback
        dist_left = abs(x - x_min)
        dist_right = abs(x - x_max)
        dist_bottom = abs(y - y_min)
        dist_top = abs(y - y_max)
        
        min_dist = min(dist_left, dist_right, dist_bottom, dist_top)
        
        if min_dist == dist_left:
            return "left"
        elif min_dist == dist_right:
            return "right"
        elif min_dist == dist_bottom:
            return "bottom"
        else:
            return "top"

def process_linestring(line_geom, elevation, rect, results):
    """
    Legacy function for backwards compatibility.
    Now defers to process_contour_sequential.
    """
    process_contour_sequential(line_geom, elevation, rect, results)

def sort_segments_by_proximity(segments):
    """Legacy function for backwards compatibility."""
    return segments

def point_distance(p1, p2):
    """Calculate Euclidean distance between two points"""
    return ((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2) ** 0.5

def point_on_which_boundary(point, rect):
    """Legacy function for backwards compatibility."""
    side = get_boundary_side(point, rect)
    return True, side

def create_boundary_path(start_point, end_point, rect):
    """Legacy function for backwards compatibility."""
    return create_boundary_connection(start_point, end_point, rect)

# Wrapper function for backwards compatibility
def remap_contours_to_rect(contour_layer, rect, region_crs=None):
    """
    Remap contour lines to properly handle boundaries of a rectangle.
    This function ensures that when contour lines cross the rectangle boundary,
    they are properly connected along the boundary edges.
    
    :param contour_layer: QgsVectorLayer containing contour lines
    :param rect: QgsRectangle defining the boundary
    :param region_crs: CRS of the rectangle (if different from contour layer)
    :return: List of tuples (elevation, geometry) with remapped geometries
    """
    return remap_contours_to_rect_sequential(contour_layer, rect, region_crs) 