# Terrain Model Maker Plugin Development Notes

## Overview
The Terrain Model Maker is a QGIS plugin designed to create laser-cuttable terrain models from contour data. The plugin allows users to select a region, specify paper dimensions, calculate the appropriate scale, filter contour lines based on material thickness, preview the output, and export the results to CSV or other formats for laser cutting.

## Development Status

### Phase 1 - Basic Structure and UI
- [x] Created plugin directory structure
- [x] Created metadata.txt with plugin information
- [x] Created SVG icon for the plugin
- [x] Set up resources.qrc file
- [x] Implemented __init__.py for plugin entry point
- [x] Implemented main plugin class (TerrainModelMaker)
- [x] Implemented dialog UI class (TerrainModelDialog)
- [x] Created UI file (terrain_model_dialog_base.ui)
- [x] Created utilities module with helper functions

### Phase 2 - Core Functionality
- [x] Implement region selection on map (included in TerrainModelMaker class)
- [x] Calculate region dimensions accurately (implemented in utils.py)
- [x] Implement scale calculation (implemented in utils.py)
- [x] Implement contour filtering based on material thickness (implemented in contour_filter.py)
- [x] Implement preview functionality (implemented in preview.py)
- [x] Implement export to CSV/DXF/SVG (implemented in contour_filter.py)

### Phase 3 - Polish and Extra Features (To Do)
- [ ] Add help documentation
- [ ] Implement error handling and validation
- [ ] Add progress indicators for long operations
- [ ] Support for multiple export formats
- [ ] Testing with various contour datasets

## Key Design Decisions

1. **Plugin Structure**:
   - Following standard QGIS plugin structure with main plugin class, dialog, and UI components
   - Utilities module for helper functions to keep code modular
   - Contour filtering functionality separated into its own module for better organization
   - Preview functionality in a dedicated module with its own dialog

2. **User Interface Flow**:
   - Step-by-step workflow with region selection, paper dimensions, scale, material settings, and export
   - GroupBoxes used to visually separate each step in the process

3. **Calculations**:
   - Scale calculated based on region size and paper dimensions with margins
   - Contour step calculation based on material thickness and scale
   - All distance measurements performed using QgsDistanceArea to ensure proper handling of different coordinate systems

4. **Region Selection**:
   - Custom map tool (RegionSelectTool) for rectangular region selection
   - Real-time feedback on selected area dimensions

5. **Paper Handling**:
   - Predefined paper sizes with option for custom dimensions
   - Support for both portrait and landscape orientations

6. **Contour Filtering**:
   - Automatic detection of contour/elevation layers in the project
   - Smart filtering of contour lines based on calculated interval
   - Support for filtering by both elevation field and spatial extent

7. **Export Formats**:
   - CSV format with elevation, part index, x, and y coordinates
   - SVG format with paths grouped by elevation for easy editing
   - DXF format using QGIS's built-in vector writer for CAD compatibility

8. **Preview Functionality**:
   - Interactive preview dialog showing how the model will look on paper
   - Displays contours in different colors based on elevation
   - Includes scale indicator and north arrow
   - Option to export the preview as an image file

## Notes on Specific Implementation Details

### Region Selection Tool
The custom RegionSelectTool class extends QgsMapTool to allow users to draw a rectangle on the map. The selection creates a rubber band visualization and captures the rectangle coordinates for further processing.

### Scale Calculation
The scale calculation ensures that the selected region fits on the paper with appropriate margins, rounding to a sensible value (nearest 100). This makes it easier to communicate and understand the scale.

### Contour Step Calculation
The contour step calculation is crucial for creating a physically viable 3D model. Based on the material thickness and the model scale, it determines what contour interval will result in appropriate layer spacing in the physical model. The function rounds to nice values (0.1, 0.2, 0.5, 1, 2, 5, 10, etc.) for practical use with existing contour data.

### Contour Layer Detection
The plugin includes automatic detection of contour layers in the QGIS project. It looks for layers with:
1. Names containing "contour", "elevation", or "isoline"
2. Fields containing "elev", "alt", "height", or "z"
3. Vector layers with line geometry

### Preview Visualization
The preview functionality uses Qt's graphics framework to show a visual representation of the final model:
1. Paper dimensions are shown to scale
2. Contour lines are drawn with colors based on elevation
3. Scale and north arrow are included for reference
4. The preview can be exported as a PNG image

### Testing Framework
A test script (test_plugin.py) has been created to validate the core functionality:
- Tests utility functions for dimension calculation, scale determination, and contour step calculation
- Tests contour filtering with sample data
- Tests export to various formats
- Can load a test project if available

The test script must be run using QGIS's Python interpreter:
```
./run_qgis.sh terrain_model_maker/test_plugin.py
```

# QGIS Import Notes

## Problem Description
Attempting to import QGIS in Python but encountering module conflicts and environment issues.

## Initial Analysis
- User has QGIS installed at `/Applications/QGIS.app/Contents/Resources/python`
- Attempted to set PYTHONPATH in `.env` file
- Getting "SRE module mismatch" error when trying to import QGIS
- Appears to be a conflict between the system Python and the QGIS-bundled Python

## Python Version Information
- User's Python: 3.11.5 (Anaconda)
- QGIS Python: 3.9 (as indicated by the symbolic link in QGIS.app)
- The version mismatch is likely causing the import issues

## Error Details
When running:
```
PYTHONPATH="/Applications/QGIS.app/Contents/Resources/python" python -c "from qgis.core import QgsProject; print('PyQGIS working!')"
```

The error shows:
- Conflicts with matplotlib package
- "Fatal Python error: init_import_site: Failed to import the site module"
- "SRE module mismatch" assertion error 

## Approaches to Try
1. Create a Python 3.9 virtual environment that matches QGIS's Python version
2. Use QGIS's Python executable directly instead of setting PYTHONPATH
3. Create a startup script that properly configures the environment

## VSCode Configuration
VSCode doesn't automatically pick up the Python interpreter from the `.env` file. You need to configure it in settings.json:

```json
{
    "python.envFile": "${workspaceFolder}/.env",
    "python.defaultInterpreterPath": "/Applications/QGIS.app/Contents/MacOS/bin/python3",
    "python.analysis.extraPaths": [
        "/Applications/QGIS.app/Contents/Resources/python",
        "/Applications/QGIS.app/Contents/Resources/python/plugins"
    ],
    "terminal.integrated.env.osx": {
        "PYTHONPATH": "/Applications/QGIS.app/Contents/Resources/python"
    }
}
```

This configuration:
1. Points VSCode to the QGIS Python interpreter
2. Adds QGIS Python paths to the IntelliSense engine
3. Sets the PYTHONPATH for the integrated terminal 

## DEM Custom Data Directory Analysis

### Directory Structure
- `data/dem_custom/` - Main directory
  - `data/` - Contains GIS data files
    - `contour_lines.gpkg` - Elevation contour lines (GeoPackage)
    - `dem.tif` - Digital Elevation Model (GeoTIFF)
    - `hillshade.tif` - Hillshade visualization (GeoTIFF)
    - `order_boundary.gpkg` - Boundary area (GeoPackage)
    - Various style files (`.qml`) for QGIS visualization
  - `data.qgs` - QGIS project file
  - `order_boundary.geojson` - Boundary in GeoJSON format
  - `readme.txt` - Information about the data source

### Data Source
- Data is from Copernicus WorldDEM-30 (Digital Surface Model)
- Licensed with specific terms as detailed in readme.txt
- Processed by NextGIS (data.nextgis.com)

### Contour Processing
- The qgis_parser.py script is designed to filter contour lines at different intervals
- It extracts contours from contour_lines.gpkg at intervals of 1-9 meters
- Output files would be named contour_lines_1m.gpkg through contour_lines_9m.gpkg
- The script uses QGIS Python API to perform the filtering 

## Testing Progress

### 2023-09-30 Test Results
- Running test_plugin.py with QGIS Python interpreter
- Initial import issues resolved by using direct imports
- Added QgsPointXY to utils.py imports
- PROJ database issues appeared (PROJ: proj_create_from_database: Cannot find proj.db)
- This is likely a configuration issue with the QGIS Python environment
- Despite PROJ issues, basic tests of utility functions run successfully
- Further testing needed for contour filtering with real data 

## Control Flow Analysis (2023-10-01)

### Desired Control Flow
1. User selects a region on the map
2. User specifies paper size on which the selected region should fit
3. Once ready, they can press the calculate scale button
4. As soon as the scale is set, the preview button should appear, which shows a preview of the selected region on a paper of the specified size (like a Print Layout)
5. The user can go back and forth between preview and scale adjustments
6. Once the scale is accepted, the user specifies 'sheet thickness', which will be used to calculate the number of contours to select
7. The preview is updated, showing the selected contours
8. When everything is in order, the user can export the contours to a specified location
9. During export the plugin should fit each individual contour on a minimal number of sheets of the same size as it was specified before. No shapes should be overlapping with the edges of these sheets

### Current Implementation Analysis

#### Working Functionality
- Region selection (Steps 1): Implemented via `start_region_selection()` and `handle_region_selection()` methods
- Paper dimensions (Step 2): User can specify paper dimensions in the UI
- Scale calculation (Step 3): Implemented in `calculate_scale()` method
- Preview functionality (Step 4): Implemented in `preview_layout()` method, which calls `create_preview()` function
- Sheet thickness and contour step (Step 6): Implemented in `update_contour_step()` method
- Contour filtering (Step 7): Implemented in `filter_contours()` method
- Exporting contours (Step 8): Implemented in `export_contours()` method

#### Issues/Missing Functionality
- UI flow control may have issues preventing the user from selecting dimensions
- Need to verify if the preview is correctly updated after contour filtering (Step 7)
- Export functionality (Step 9) may not properly handle fitting contours on minimal sheets without overlapping edges

### Next Steps
1. Debug the issue with paper dimension selection
2. Verify the UI flow control is working correctly
3. Check if preview updates after contour filtering
4. Validate the export functionality handles the sheet arrangement requirements 