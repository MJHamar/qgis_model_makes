#!/usr/bin/env python3
# This script should be run with QGIS's Python interpreter
# Example: /Applications/QGIS.app/Contents/MacOS/bin/python3 qgis_parser.py

from qgis.core import QgsFeatureRequest, QgsVectorLayer, QgsVectorFileWriter
import sys
import os

# Initialize QGIS application
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/Applications/QGIS.app/Contents/MacOS", True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Import other required QGIS modules
from qgis.core import QgsProject
from qgis.core import QgsVectorFileWriter

# For debugging: print QGIS-related paths and environment variables
print(f"QGIS Prefix path: {QgsApplication.prefixPath()}")
print(f"QGIS Plugin path: {QgsApplication.pluginPath()}")
print(f"PROJ_LIB environment variable: {os.environ.get('PROJ_LIB', 'Not set')}")

# Attempt to manually set PROJ_LIB if not set
if 'PROJ_LIB' not in os.environ:
    potential_proj_paths = [
        os.path.join(QgsApplication.prefixPath(), "share/proj"),
        "/Applications/QGIS.app/Contents/Resources/proj"
    ]
    for path in potential_proj_paths:
        if os.path.exists(path):
            print(f"Setting PROJ_LIB to: {path}")
            os.environ['PROJ_LIB'] = path
            break

# Load the QGIS project
project_path = 'data/dem_custom/data.qgs'
print(f"Opening QGIS project: {project_path}")
project = QgsProject.instance()
if not project.read(project_path):
    print(f"Failed to open QGIS project at {project_path}")
    sys.exit(1)
else:
    print("Project opened successfully")
    print(f"Project title: {project.title()}")
    print("Layers in project:")
    for layer_id, layer in project.mapLayers().items():
        print(f"  - {layer.name()} ({layer.type()}) - {layer_id}")

def filter_contours_from_project(project, output_path: str, interval: int):
    """Filter contour lines to keep every nth meter using a layer from the project."""
    # Find the contour layer in the project - be more specific to get the original layer
    contour_layer = None
    
    # First look for the exact name "Elevation contours"
    for layer_id, layer in project.mapLayers().items():
        if layer.name() == "Elevation contours":
            print(f"Found original contour layer: {layer.name()}")
            contour_layer = layer
            break
    
    # If not found, use a more generic search
    if contour_layer is None:
        for layer_id, layer in project.mapLayers().items():
            if layer.name().lower().find('contour') >= 0 or layer.name().lower().find('elevation') >= 0:
                # Skip our newly created contour layers
                if layer.name().startswith("Contours ") or layer.name().startswith("contour_lines_"):
                    continue
                print(f"Found contour layer: {layer.name()}")
                contour_layer = layer
                break
    
    if contour_layer is None:
        print("No original contour layer found in the project. Available layers:")
        for layer_id, layer in project.mapLayers().items():
            print(f"  - {layer.name()} ({layer.type()})")
        raise ValueError("No original contour layer found in project")
    
    print(f"\nProcessing layer: {contour_layer.name()}")
    print(f"Output file: {output_path}")
    
    # Print all available fields for debugging
    print("\nAvailable fields in layer:")
    for field in contour_layer.fields():
        print(f"Field: {field.name()}, Type: {field.typeName()}")

    # Check for elevation field
    field_name = None
    for field in contour_layer.fields():
        if field.name().lower() in ['elevation', 'contour', 'elev', 'level']:
            field_name = field.name()
            break

    if not field_name:
        print("\nWarning: No elevation field found. Available fields are:", 
              [field.name() for field in contour_layer.fields()])
        raise ValueError("No elevation field found in layer")
    
    print(f"\nUsing field '{field_name}' as elevation field")

    # Build filter expression
    expr = f'"{field_name}" % {interval} = 0'
    print(f"Filter expression: {expr}")

    # Check if any features match the filter
    matching_count = 0
    for _ in contour_layer.getFeatures(QgsFeatureRequest().setFilterExpression(expr)):
        matching_count += 1
    
    print(f"Found {matching_count} features matching the filter expression")
    
    if matching_count == 0:
        print("Warning: No features match the filter criteria. Check your interval value.")
        return
        
    # Determine the file format based on file extension
    file_ext = os.path.splitext(output_path)[1].lower()
    
    if file_ext == '.gpkg':
        driver_name = 'GPKG'
    elif file_ext in ['.shp', '.shx', '.dbf']:
        driver_name = 'ESRI Shapefile'
    else:
        print(f"Warning: Unrecognized file extension '{file_ext}'. Defaulting to GeoPackage format.")
        driver_name = 'GPKG'
    
    print(f"Using driver: {driver_name}")
    
    # Create a memory layer with filtered features
    print("Creating temporary memory layer with filtered features...")
    memory_layer = QgsVectorLayer(f"LineString?crs={contour_layer.crs().authid()}", "filtered_contours", "memory")
    memory_layer.setCrs(contour_layer.crs())
    
    # Set up the fields
    memory_layer.startEditing()
    for field in contour_layer.fields():
        memory_layer.addAttribute(field)
    memory_layer.commitChanges()
    
    # Add filtered features
    memory_layer.startEditing()
    for feature in contour_layer.getFeatures(QgsFeatureRequest().setFilterExpression(expr)):
        memory_layer.addFeature(feature)
    memory_layer.commitChanges()
    
    print(f"Created memory layer with {memory_layer.featureCount()} features")
    
    # Save the memory layer to file
    error = QgsVectorFileWriter.writeAsVectorFormat(
        memory_layer,
        output_path,
        "UTF-8",
        memory_layer.crs(),
        driver_name
    )
    
    if error == QgsVectorFileWriter.NoError:
        print(f"Successfully saved filtered contours to {output_path}")
        
        # Add the layer to the project
        print(f"Adding layer to project: {output_path}")
        new_layer = QgsVectorLayer(output_path, f"Contours {interval}m", "ogr")
        
        if not new_layer.isValid():
            print(f"Error: Failed to load layer from {output_path}")
            return
        
        # Copy style from original contour layer if available
        if contour_layer.styleManager().hasStyleName("default"):
            style_xml = contour_layer.styleManager().style("default")
            new_layer.importNamedStyle(style_xml)
            print("Applied style from original contour layer")
        
        # Add to project
        project.addMapLayer(new_layer)
        
        # Create a group for contour layers if it doesn't exist
        root = project.layerTreeRoot()
        filtered_contours_group = None
        
        for child in root.children():
            if child.name() == "Filtered Contours":
                filtered_contours_group = child
                break
        
        if not filtered_contours_group:
            filtered_contours_group = root.addGroup("Filtered Contours")
        
        # Move layer to the group
        layer_node = root.findLayer(new_layer.id())
        if layer_node:
            clone = layer_node.clone()
            filtered_contours_group.addChildNode(clone)
            root.removeChildNode(layer_node)
            print(f"Added layer to 'Filtered Contours' group")
        
        # Save the project
        project.write()
        print("Project saved with new layer")
        
        return new_layer
    else:
        print(f"Error saving filtered contours: {error}")
        return None


# Usage:
try:
    # Create contour files for 1m through 10m intervals
    added_layers = []
    for interval in range(1, 11):
        output_path = f'contour_lines_{interval}m.gpkg'
        print(f"\n===== Processing {interval}m interval contours =====")
        new_layer = filter_contours_from_project(
            project=project,
            output_path=output_path,
            interval=interval
        )
        if new_layer:
            added_layers.append(new_layer)
    
    print("\nAll filter operations completed successfully")
    print(f"Added {len(added_layers)} layers to the project")
    
    # Save a new version of the project
    new_project_path = 'data/dem_custom/data_with_filtered_contours.qgs'
    if project.write(new_project_path):
        print(f"Project saved as {new_project_path}")
    else:
        print("Failed to save project")
except Exception as e:
    print(f"Error during filtering: {e}")
    import traceback
    traceback.print_exc()

# Clean up
print("Exiting QGIS...")
qgs.exitQgis()
print("Done.")
