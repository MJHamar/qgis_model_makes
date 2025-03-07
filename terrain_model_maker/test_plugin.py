#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the Terrain Model Maker plugin.
This script should be run using QGIS's Python interpreter:
./run_qgis.sh terrain_model_maker/test_plugin.py
"""

import os
import sys
import tempfile

# Add the parent directory to the path so we can import our plugin modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Initialize QGIS Application
from qgis.core import QgsApplication
qgs = QgsApplication([], False)
qgs.initQgis()

# Now import the rest of the QGIS modules
from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY
)

# Import our utility functions directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import utils
from utils import (
    calculate_rectangle_dimensions,
    calculate_scale,
    calculate_contour_step,
    PAPER_SIZES
)

# Import contour filter functions
import contour_filter
from contour_filter import (
    find_contour_layer,
    filter_contours_by_interval,
    export_contours_to_file
)

def test_utils():
    """Test the utility functions."""
    print("Testing utility functions...")
    
    # Create a test rectangle
    rect = QgsRectangle(0, 0, 1000, 500)
    crs = QgsCoordinateReferenceSystem("EPSG:3857")  # Web Mercator
    
    # Test rectangle dimensions calculation
    width, height, area = calculate_rectangle_dimensions(rect, crs)
    print(f"Rectangle dimensions: width={width:.2f}m, height={height:.2f}m, area={area:.2f}m²")
    
    # Test scale calculation
    paper_width, paper_height = PAPER_SIZES['A4']
    scale = calculate_scale(width, height, paper_width, paper_height)
    print(f"Scale for A4 paper: 1:{scale}")
    
    # Test contour step calculation
    thickness = 3.0  # 3mm sheet thickness
    contour_step = calculate_contour_step(scale, thickness)
    print(f"Contour step for 3mm sheets at 1:{scale} scale: {contour_step}m")
    
    return width, height, scale, contour_step

def create_sample_contours():
    """Create a sample contour layer for testing."""
    print("Creating sample contour layer...")
    
    # Create a memory layer
    layer = QgsVectorLayer(
        "LineString?crs=EPSG:3857&field=elevation:double",
        "Sample Contours",
        "memory"
    )
    
    # Create some sample contour features
    features = []
    for i in range(10):  # Create contours from 0 to 90m at 10m intervals
        elev = i * 10
        # Create line geometry
        line = [QgsPointXY(0, i*100), QgsPointXY(100, i*100+50), QgsPointXY(200, i*100)]
        geom = QgsGeometry.fromPolylineXY(line)
        
        feature = QgsFeature()
        feature.setGeometry(geom)
        feature.setAttributes([elev])
        features.append(feature)
    
    # Add the features to the layer
    layer.dataProvider().addFeatures(features)
    
    return layer

def test_contour_filtering(contour_layer):
    """Test the contour filtering functions."""
    print("\nTesting contour filtering...")
    
    if not contour_layer:
        print("No contour layer provided, creating sample layer")
        contour_layer = create_sample_contours()
    
    # Count original features
    feature_count = contour_layer.featureCount()
    print(f"Original contour layer has {feature_count} features")
    
    # Filter contours at 20m interval
    interval = 20
    filtered_layer = filter_contours_by_interval(contour_layer, interval, elevation_field="elevation")
    
    if filtered_layer:
        filtered_count = filtered_layer.featureCount()
        print(f"Filtered layer with {interval}m interval has {filtered_count} features")
        
        # Export to temporary files
        temp_dir = tempfile.gettempdir()
        
        # CSV export
        csv_path = os.path.join(temp_dir, "test_contours.csv")
        csv_result = export_contours_to_file(filtered_layer, csv_path, "CSV")
        print(f"CSV export to {csv_path}: {'Success' if csv_result else 'Failed'}")
        
        # SVG export
        svg_path = os.path.join(temp_dir, "test_contours.svg")
        svg_result = export_contours_to_file(filtered_layer, svg_path, "SVG")
        print(f"SVG export to {svg_path}: {'Success' if svg_result else 'Failed'}")
        
        return filtered_layer, csv_path, svg_path
    else:
        print("Failed to filter contours")
        return None, None, None

def load_test_project():
    """Try to load a test QGIS project if available."""
    print("\nAttempting to load test project...")
    
    # Check for the test project in known locations
    potential_paths = [
        'data/dem_custom/data.qgs',
        '../data/dem_custom/data.qgs',
        os.path.join(parent_dir, 'data/dem_custom/data.qgs')
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            print(f"Found project at {path}")
            project = QgsProject.instance()
            if project.read(path):
                print("Project loaded successfully")
                print("Layers in project:")
                for layer_id, layer in project.mapLayers().items():
                    print(f"  - {layer.name()} ({layer.type()}) - {layer_id}")
                return project
            else:
                print("Failed to load project")
    
    print("Test project not found")
    return None

def main():
    """Main test function."""
    print("Starting Terrain Model Maker plugin test...")
    
    # Run the tests
    try:
        # Test utility functions
        width, height, scale, contour_step = test_utils()
        
        # Try to load the test project
        project = load_test_project()
        
        # Find contour layer
        contour_layer = None
        if project:
            contour_layer = find_contour_layer(project)
            if contour_layer:
                print(f"Found contour layer: {contour_layer.name()}")
            else:
                print("No contour layer found in project")
        
        # Test contour filtering
        filtered_layer, csv_path, svg_path = test_contour_filtering(contour_layer)
        
        print("\nAll tests completed!")
        print("\nSummary:")
        print(f"- Model dimensions: {width:.2f}m × {height:.2f}m")
        print(f"- Calculated scale: 1:{scale}")
        print(f"- Contour step: {contour_step}m")
        if csv_path:
            print(f"- Test CSV output: {csv_path}")
        if svg_path:
            print(f"- Test SVG output: {svg_path}")
    except Exception as e:
        print(f"Error during tests: {e}")
        import traceback
        traceback.print_exc()
    
    # Exit QGIS
    qgs.exitQgis()

if __name__ == "__main__":
    main() 