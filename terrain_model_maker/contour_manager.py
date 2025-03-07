# -*- coding: utf-8 -*-
"""
Contour management for the Terrain Model Maker plugin.
Handles contour layer detection, filtering, and visualization.
"""

from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsLineSymbol,
    QgsSimpleLineSymbolLayer,
    QgsSymbolLayerUtils,
    Qgis,
    QgsMessageLog
)
from qgis.PyQt.QtCore import QVariant, QTemporaryDir
from qgis.PyQt.QtGui import QColor
import os
import re

class ContourManager:
    """Class for managing contour layers in QGIS."""
    
    # Common attribute names for elevation in contour layers
    ELEVATION_FIELD_PATTERNS = [
        r'^elev.*$',       # elevation, elev, etc.
        r'^alt.*$',        # altitude, alt, etc.
        r'^height.*$',     # height, etc.
        r'^z.*$',          # z-value, z, etc.
        r'^level.*$',      # level, etc.
        r'^contour.*$',    # contour, contourvalue, etc.
        r'^value.*$',      # value, etc.
        r'^h$',            # Just 'h'
        r'^ele$',          # Just 'ele'
    ]
    
    # Common keywords in contour layer names
    CONTOUR_LAYER_KEYWORDS = [
        'contour', 'isoline', 'isohypse', 'height', 
        'elevation', 'level', 'dem', 'dtm', 'relief'
    ]
    
    def __init__(self, iface):
        """Initialize the contour manager.
        
        :param iface: QGIS interface
        """
        self.iface = iface
        self.project = QgsProject.instance()
        
        # List of detected contour layers
        self.contour_layers = []
        
        # The currently active filtered layer
        self.filtered_layer = None
        
        # Current elevation field
        self.elevation_field = None
        
        # Temporary directory for layer storage
        self.temp_dir = QTemporaryDir()
        if not self.temp_dir.isValid():
            self.temp_dir = None
    
    def detect_contour_layers(self):
        """Find potential contour layers in the current project.
        
        :return: List of detected contour layer ids
        """
        self.contour_layers = []
        
        # Get all vector layers from the project
        layers = self.project.mapLayers().values()
        vector_layers = [layer for layer in layers if isinstance(layer, QgsVectorLayer)]
        
        # Filter for line layers (contours are typically lines)
        line_layers = [layer for layer in vector_layers 
                      if layer.geometryType() == QgsWkbTypes.LineGeometry]
        
        # Now inspect each layer for potential elevation attributes
        for layer in line_layers:
            if self._is_contour_layer(layer):
                # Store the layer and its granularity score
                features_count = layer.featureCount()
                granularity_score = features_count
                
                # Store as (layer, score, elevation_field)
                elev_field = self._detect_elevation_field(layer)
                self.contour_layers.append((layer, granularity_score, elev_field))
        
        # Sort by granularity score (descending)
        self.contour_layers.sort(key=lambda x: x[1], reverse=True)
        
        return [layer.id() for layer, _, _ in self.contour_layers]
    
    def _is_contour_layer(self, layer):
        """Determine if a layer is likely a contour layer.
        
        The method uses multiple heuristics to identify contour layers:
        1. Checks if the layer is a line geometry type
        2. Looks for elevation-related fields in the attribute table
        3. Examines the layer name for contour-related keywords
        
        :param layer: QgsVectorLayer to check
        :return: Boolean indicating if the layer is likely contours
        """
        # First check: Must be a line geometry layer
        if layer.geometryType() != QgsWkbTypes.LineGeometry:
            return False
            
        # Second check: Look for elevation fields
        elev_field = self._detect_elevation_field(layer)
        if elev_field:
            return True
            
        # Third check: Check if layer name contains contour-related keywords
        layer_name = layer.name().lower()
        if any(keyword in layer_name for keyword in self.CONTOUR_LAYER_KEYWORDS):
            return True
            
        return False
    
    def _detect_elevation_field(self, layer):
        """Try to automatically detect the field containing elevation values.
        
        :param layer: QgsVectorLayer to check
        :return: Field name or None if not found
        """
        field_names = [field.name() for field in layer.fields()]
        
        # First check exact matches with common elevation field names
        common_names = ['elevation', 'elev', 'altitude', 'alt', 'height', 'z', 'level']
        for name in common_names:
            if name in field_names:
                return name
        
        # Then try regex patterns
        for pattern in self.ELEVATION_FIELD_PATTERNS:
            for field_name in field_names:
                if re.match(pattern, field_name.lower()):
                    return field_name
        
        # If no match found, return the first numeric field
        for field in layer.fields():
            if field.isNumeric():
                return field.name()
                
        return None
    
    def get_contour_layers(self):
        """Get the list of detected contour layers.
        
        :return: List of (layer, granularity_score, elevation_field) tuples
        """
        return self.contour_layers
    
    def get_default_contour_layer(self):
        """Get the default contour layer (highest granularity).
        
        :return: Default contour layer or None
        """
        if self.contour_layers:
            return self.contour_layers[0][0]
        return None
    
    def filter_contours(self, source_layer, thickness, elevation_field=None):
        """Filter contours based on sheet thickness.
        
        :param source_layer: Source contour layer
        :param thickness: Sheet thickness value
        :param elevation_field: Field containing elevation data (auto-detected if None)
        :return: The filtered layer
        """
        QgsMessageLog.logMessage(f"Filtering contours: layer={source_layer.name()}, thickness={thickness}mm", 
                                "Terrain Model", Qgis.Info)
        
        # Clean up previous filtered layer if it exists
        if self.filtered_layer:
            # Remove from project
            if self.project.mapLayer(self.filtered_layer.id()):
                self.project.removeMapLayer(self.filtered_layer.id())
            self.filtered_layer = None
        
        # If no source layer, return
        if not source_layer:
            QgsMessageLog.logMessage("No source layer provided", "Terrain Model", Qgis.Warning)
            return None
            
        # Detect elevation field if not provided
        if not elevation_field:
            elevation_field = self._detect_elevation_field(source_layer)
            QgsMessageLog.logMessage(f"Auto-detected elevation field: {elevation_field}", "Terrain Model", Qgis.Info)
        
        # If still no elevation field found, return
        if not elevation_field:
            QgsMessageLog.logMessage("No elevation field found", "Terrain Model", Qgis.Warning)
            return None
            
        # Check if the field exists in the layer
        field_names = [field.name() for field in source_layer.fields()]
        if elevation_field not in field_names:
            QgsMessageLog.logMessage(f"Field '{elevation_field}' not found in layer. Available fields: {field_names}", 
                                    "Terrain Model", Qgis.Warning)
            return None
            
        # Store current elevation field
        self.elevation_field = elevation_field
        
        # Get the elevation range to help with debugging
        min_elev, max_elev = self.get_elevation_range(source_layer, elevation_field)
        QgsMessageLog.logMessage(f"Elevation range: {min_elev} to {max_elev}", "Terrain Model", Qgis.Info)
        
        # Create a temporary layer with the same CRS and fields as the source
        temp_path = self._get_temp_path('filtered_contours.gpkg')
        QgsMessageLog.logMessage(f"Creating temp file at: {temp_path}", "Terrain Model", Qgis.Info)
        
        # Copy the fields from the source layer
        fields = QgsFields(source_layer.fields())
        
        # Create writer for the temporary layer
        crs = source_layer.crs()
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = "filtered_contours"
        
        writer = None
        try:
            # First attempt using the newer API (QGIS 3.x)
            QgsMessageLog.logMessage("Attempting to create writer with new API...", "Terrain Model", Qgis.Info)
            writer = QgsVectorFileWriter.create(
                temp_path, 
                fields, 
                QgsWkbTypes.LineString, 
                crs, 
                QgsProject.instance().transformContext(),
                options
            )
            QgsMessageLog.logMessage("Writer created with new API", "Terrain Model", Qgis.Info)
        except TypeError as e:
            QgsMessageLog.logMessage(f"TypeError with new API: {str(e)}", "Terrain Model", Qgis.Warning)
            try:
                # Fallback for other QGIS versions
                QgsMessageLog.logMessage("Falling back to old API...", "Terrain Model", Qgis.Info)
                writer = QgsVectorFileWriter(
                    temp_path,
                    "UTF-8",
                    fields,
                    QgsWkbTypes.LineString,
                    crs,
                    "GPKG"
                )
                QgsMessageLog.logMessage("Writer created with old API", "Terrain Model", Qgis.Info)
            except Exception as e:
                QgsMessageLog.logMessage(f"Error creating vector file writer: {str(e)}", "Terrain Model", Qgis.Critical)
                return None
        
        if not writer:
            QgsMessageLog.logMessage("Failed to create writer", "Terrain Model", Qgis.Critical)
            return None
            
        if hasattr(writer, 'hasError') and writer.hasError() != QgsVectorFileWriter.NoError:
            QgsMessageLog.logMessage(f"Writer has error: {writer.errorMessage()}", "Terrain Model", Qgis.Critical)
            return None
        
        # Filter contours where elevation % thickness = 0
        request = QgsFeatureRequest()
        
        features_added = 0
        elevation_values = []
        try:
            QgsMessageLog.logMessage(f"Beginning filtering with elevation field: {elevation_field}", "Terrain Model", Qgis.Info)
            
            # Take a sample of elevation values to help debug
            sample_size = min(5, source_layer.featureCount())
            sample_features = list(source_layer.getFeatures(QgsFeatureRequest().setLimit(sample_size)))
            
            for feature in sample_features:
                if elevation_field in feature.fields().names():
                    elevation_values.append(feature[elevation_field])
                else:
                    QgsMessageLog.logMessage(f"Field {elevation_field} not found in feature", "Terrain Model", Qgis.Warning)
            
            QgsMessageLog.logMessage(f"Sample elevation values: {elevation_values}", "Terrain Model", Qgis.Info)
            
            # Now filter the contours
            total_features = source_layer.featureCount()
            QgsMessageLog.logMessage(f"Processing {total_features} contour features...", "Terrain Model", Qgis.Info)
            
            for feature in source_layer.getFeatures(request):
                if elevation_field not in feature.fields().names():
                    QgsMessageLog.logMessage(f"Field {elevation_field} not found in feature", "Terrain Model", Qgis.Warning)
                    continue
                    
                elev_value = feature[elevation_field]
                
                # Skip features with null elevation
                if elev_value is None:
                    continue
                    
                # Convert to float if needed
                try:
                    elev_float = float(elev_value)
                except (ValueError, TypeError):
                    continue
                    
                # Apply filter: elevation % thickness = 0
                remainder = elev_float % thickness
                threshold = 0.001  # Small threshold for float comparison
                
                # Check if this elevation is a multiple of the thickness value
                if abs(remainder) < threshold or abs(thickness - remainder) < threshold:
                    writer.addFeature(feature)
                    features_added += 1
                    if features_added <= 5:  # Print the first few matches for debugging
                        QgsMessageLog.logMessage(f"Added feature with elevation {elev_float} (thickness={thickness}, remainder={remainder})", "Terrain Model", Qgis.Info)
            
            QgsMessageLog.logMessage(f"Features added: {features_added} out of {total_features}", "Terrain Model", Qgis.Info)
            
            # If no features were found with the standard method, try alternative approaches
            if features_added == 0 and total_features > 0:
                QgsMessageLog.logMessage("No features matched the standard filtering criteria. Trying alternative approaches...", "Terrain Model", Qgis.Info)
                
                # Get elevation range and estimate suitable threshold
                min_elev, max_elev = self.get_elevation_range(source_layer, elevation_field)
                if min_elev is not None and max_elev is not None:
                    elevation_range = max_elev - min_elev
                    # Try to find existing elevation intervals
                    elevation_values = set()
                    sample_size = min(100, total_features) 
                    for feature in source_layer.getFeatures(QgsFeatureRequest().setLimit(sample_size)):
                        try:
                            elevation_values.add(float(feature[elevation_field]))
                        except (ValueError, TypeError):
                            continue
                    
                    elevation_values = sorted(list(elevation_values))
                    if len(elevation_values) > 1:
                        # Calculate the smallest interval between existing contours
                        intervals = [elevation_values[i+1] - elevation_values[i] for i in range(len(elevation_values)-1)]
                        smallest_interval = min(intervals)
                        QgsMessageLog.logMessage(f"Smallest detected contour interval: {smallest_interval}", "Terrain Model", Qgis.Info)
                        
                        # Try using multiples of the smallest interval that are close to the specified thickness
                        if smallest_interval > 0:
                            # Find the multiple closest to the requested thickness
                            multiple = round(thickness / smallest_interval)
                            if multiple < 1:
                                multiple = 1
                                
                            effective_thickness = smallest_interval * multiple
                            QgsMessageLog.logMessage(f"Using effective thickness of {effective_thickness} (based on contour interval of {smallest_interval})", "Terrain Model", Qgis.Info)
                            
                            # Reset writer
                            del writer
                            writer = QgsVectorFileWriter.create(
                                temp_path, 
                                fields, 
                                QgsWkbTypes.LineString, 
                                crs, 
                                QgsProject.instance().transformContext(),
                                options
                            )
                            
                            features_added = 0
                            # Filter using the effective thickness
                            for feature in source_layer.getFeatures(request):
                                try:
                                    elev_float = float(feature[elevation_field])
                                    remainder = elev_float % effective_thickness
                                    if abs(remainder) < threshold or abs(effective_thickness - remainder) < threshold:
                                        writer.addFeature(feature)
                                        features_added += 1
                                        if features_added <= 5:
                                            QgsMessageLog.logMessage(f"Added feature with elevation {elev_float} using effective thickness {effective_thickness}", "Terrain Model", Qgis.Info)
                                except (ValueError, TypeError):
                                    continue
                                    
                            QgsMessageLog.logMessage(f"Features added with alternative method: {features_added} out of {total_features}", "Terrain Model", Qgis.Info)
        except Exception as e:
            import traceback
            QgsMessageLog.logMessage(f"Error during filtering: {str(e)}", "Terrain Model", Qgis.Critical)
            QgsMessageLog.logMessage(traceback.format_exc(), "Terrain Model", Qgis.Critical)
        
        # Delete the writer to ensure file is properly saved
        del writer
        
        # Check if any features were added
        if features_added == 0:
            QgsMessageLog.logMessage("No features matched the filter criteria", "Terrain Model", Qgis.Warning)
            return None
        
        # Load the filtered layer into the project
        layer_name = f"Filtered Contours (Thickness: {thickness}m)"
        self.filtered_layer = QgsVectorLayer(temp_path, layer_name, "ogr")
        
        # Check if layer is valid
        if not self.filtered_layer.isValid():
            QgsMessageLog.logMessage(f"Error loading filtered contour layer from {temp_path}", "Terrain Model", Qgis.Critical)
            return None
            
        QgsMessageLog.logMessage(f"Filtered layer created with {self.filtered_layer.featureCount()} features", "Terrain Model", Qgis.Info)
        
        # Apply styling
        self._style_filtered_layer()
        
        # Add to project
        self.project.addMapLayer(self.filtered_layer)
        
        # Return the new layer
        return self.filtered_layer
    
    def _style_filtered_layer(self, color=None):
        """Apply styling to the filtered contour layer.
        
        :param color: Optional color to use for the contours
        """
        if not self.filtered_layer:
            return
            
        # Default color if none provided
        if not color:
            color = QColor(255, 0, 0)  # Red
            
        # Create a line symbol
        symbol = QgsLineSymbol.createSimple({
            'line_color': color.name(),
            'line_width': '0.5',
            'line_style': 'solid'
        })
        
        # Apply the symbol to the layer
        renderer = QgsSingleSymbolRenderer(symbol)
        self.filtered_layer.setRenderer(renderer)
        
        # Refresh the layer
        self.filtered_layer.triggerRepaint()
    
    def set_contour_color(self, color):
        """Set the color for the filtered contours.
        
        :param color: QColor to use for contours
        """
        self._style_filtered_layer(color)
    
    def _get_temp_path(self, filename):
        """Get a path in the temporary directory.
        
        :param filename: Name of the file
        :return: Full path to the file
        """
        if self.temp_dir and self.temp_dir.isValid():
            return os.path.join(self.temp_dir.path(), filename)
        else:
            # Fallback to system temp directory
            return os.path.join(os.path.expanduser('~'), '.qgis3', 'tmp', filename)
    
    def get_elevation_range(self, layer, field=None):
        """Get the min and max elevation values from a contour layer.
        
        :param layer: Contour layer
        :param field: Elevation field (auto-detected if None)
        :return: Tuple of (min, max) elevation or (None, None) if not found
        """
        if not layer:
            return (None, None)
            
        # Detect field if not provided
        if not field:
            field = self._detect_elevation_field(layer)
            
        if not field:
            return (None, None)
            
        # Get min and max values
        min_val = None
        max_val = None
        
        for feature in layer.getFeatures():
            val = feature[field]
            if val is None:
                continue
                
            try:
                val_float = float(val)
                if min_val is None or val_float < min_val:
                    min_val = val_float
                if max_val is None or val_float > max_val:
                    max_val = val_float
            except (ValueError, TypeError):
                continue
                
        return (min_val, max_val)
    
    def clean_up(self):
        """Clean up resources."""
        # Remove filtered layer from project
        if self.filtered_layer and self.project.mapLayer(self.filtered_layer.id()):
            self.project.removeMapLayer(self.filtered_layer.id())
            
        # Clean up temporary directory
        if self.temp_dir and self.temp_dir.isValid():
            self.temp_dir = None  # This should trigger cleanup 