# Terrain Model Maker QGIS Plugin

A QGIS plugin for creating laser-cuttable terrain models from contour data.

## Features

- Select a region on the map to model
- Choose paper sizes or specify custom dimensions
- Automatically calculate appropriate scale
- Preview the terrain model layout
- Filter contour lines based on material thickness
- Export to CSV, DXF or SVG formats for laser cutting

## Installation

### From QGIS Plugin Repository (Recommended)

1. Open QGIS
2. Go to Plugins → Manage and Install Plugins
3. Search for "Terrain Model Maker"
4. Click "Install Plugin"

### Manual Installation

1. Download the ZIP file from the [releases page](https://github.com/yourusername/terrain_model_maker/releases)
2. Open QGIS
3. Go to Plugins → Manage and Install Plugins → Install from ZIP
4. Navigate to the downloaded ZIP file and select it
5. Click "Install Plugin"

Alternatively, you can manually extract the ZIP file to your QGIS plugins directory:

- Windows: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`
- Mac: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins`

## Usage

1. **Open QGIS** with a project containing contour data
2. **Click the Terrain Model Maker icon** in the toolbar (or find it in the Plugins menu)
3. **Select a region** on the map using the "Select Region" button
4. **Choose paper dimensions** from predefined sizes or enter custom values
5. **Calculate scale** based on the region and paper size
6. **Preview** how the model will look
7. **Enter material thickness** to calculate appropriate contour filtering
8. **Export** to your preferred format for laser cutting

## Creating a Physical Model

After exporting the contour data, you can use a laser cutter to cut each layer from sheet material (cardboard, wood, acrylic, etc.). The exported files will be ready for laser cutting with each contour as a separate cutting path.

### Assembly Tips

1. Start with the base (lowest elevation) layer
2. Stack each contour on top of the previous one
3. Use small dabs of glue to secure layers
4. Consider adding reference holes through all layers for proper alignment
5. Sand edges if necessary after assembly

## Requirements

- QGIS 3.16 or newer
- A vector layer with contour data

## License

This plugin is licensed under the GNU General Public License v2.0 or later.

## Support

If you encounter any issues or have suggestions, please submit them on the [GitHub issue tracker](https://github.com/yourusername/terrain_model_maker/issues). 