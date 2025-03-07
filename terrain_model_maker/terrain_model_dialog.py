# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TerrainModelDialog
                                 A QGIS plugin
 Create laser-cuttable terrain models from contour data
                             -------------------
        begin                : 2023-03-07
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Terrain Model Team
        email                : info@example.com
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
from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.gui import QgsMapCanvas
from qgis.core import QgsMapLayerProxyModel, QgsVectorLayer, QgsWkbTypes

from .utils import PAPER_SIZES

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'terrain_model_dialog_base.ui'))


class TerrainModelDialog(QtWidgets.QDialog, FORM_CLASS):
    """Dialog for the Terrain Model Maker plugin"""
    
    # Custom signals
    placeRectangleRequested = pyqtSignal()
    clearRectangleRequested = pyqtSignal()
    renderLayoutRequested = pyqtSignal()
    exportPdfRequested = pyqtSignal()
    exportCsvRequested = pyqtSignal()
    exportContoursRequested = pyqtSignal()
    exportLaserRequested = pyqtSignal()
    
    # New signals for settings changes
    paperSizeChanged = pyqtSignal()
    scaleChanged = pyqtSignal()
    
    # Contour-related signals
    contourLayerChanged = pyqtSignal(QgsVectorLayer)
    contourElevFieldChanged = pyqtSignal(str)
    contourColorChanged = pyqtSignal(QColor)
    contourThicknessChanged = pyqtSignal(float)
    
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TerrainModelDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        
        # Initialize UI elements
        self.init_ui()
        
        # Set up button connections
        self.setup_connections()
        
        # Set up paper sizes
        self.setup_paper_sizes()
    
        # Set up validators for numeric input
        self.setup_validators()
        
        # Initialize state
        self.has_rectangle = False
        self.contour_color = QColor(255, 0, 0)  # Default red
        self.update_ui_state()
        
    def init_ui(self):
        """Initialize UI elements"""
        # Set initial status
        self.lbl_status.setText("Ready. Configure settings and place a rectangle on the map.")
        
        # Default values
        self.txt_width.setEnabled(False)
        self.txt_height.setEnabled(False)
        self.txt_scale.setText("10000")
        self.txt_thickness.setText("3.0")
        
        # Hide the refresh button as it's no longer needed
        self.btn_refresh.setVisible(False)
        
        # Set up the contour color button
        self.update_color_button()
        
    def setup_connections(self):
        """Set up signal/slot connections"""
        # Button connections
        self.btn_place_rectangle.clicked.connect(self.on_place_rectangle_clicked)
        self.btn_clear_rectangle.clicked.connect(self.on_clear_rectangle_clicked)
        self.btn_render.clicked.connect(self.on_render_clicked)
        self.btn_export_pdf.clicked.connect(self.on_export_pdf_clicked)
        self.btn_export_csv.clicked.connect(self.on_export_csv_clicked)
        self.btn_export_contours.clicked.connect(self.on_export_contours_clicked)
        self.btn_export_laser.clicked.connect(self.on_export_laser_clicked)
        
        # Paper size and orientation connections
        self.cmb_paper_size.currentIndexChanged.connect(self.on_paper_size_changed)
        self.radio_portrait.toggled.connect(self.on_orientation_changed)
        self.radio_landscape.toggled.connect(self.on_orientation_changed)
        
        # Connect settings change signals
        self.txt_width.textChanged.connect(self.on_settings_changed)
        self.txt_height.textChanged.connect(self.on_settings_changed)
        self.txt_scale.textChanged.connect(self.on_settings_changed)
        
        # Contour connections
        self.cmb_contour_layer.currentIndexChanged.connect(self.on_contour_layer_changed)
        self.cmb_elevation_field.currentIndexChanged.connect(self.on_elev_field_changed)
        self.btn_contour_color.clicked.connect(self.on_contour_color_clicked)
        self.txt_thickness.textChanged.connect(self.on_thickness_changed)
        
        # Manually trigger the thickness changed signal to initialize filtering
        self.on_thickness_changed(self.txt_thickness.text())
    
    def setup_paper_sizes(self):
        """Set up standard paper sizes in the combo box"""
        # Clear existing items
        self.cmb_paper_size.clear()
        
        # Add "Custom" option
        self.cmb_paper_size.addItem("Custom", None)
        
        # Add standard paper sizes
        for name, dimensions in PAPER_SIZES.items():
            if name != "Custom":
                self.cmb_paper_size.addItem(f"{name} ({dimensions[0]} × {dimensions[1]} mm)", 
                                           {"name": name, "width": dimensions[0], "height": dimensions[1]})
        
        # Set default to A4
        for i in range(self.cmb_paper_size.count()):
            data = self.cmb_paper_size.itemData(i)
            if data and data.get("name") == "A4":
                self.cmb_paper_size.setCurrentIndex(i)
                break
    
    def setup_validators(self):
        """Set up validators for numeric input fields"""
        # Only allow positive numbers for dimensions and thickness
        double_validator = QtGui.QDoubleValidator()
        double_validator.setBottom(0.1)  # Only positive values
        
        self.txt_width.setValidator(double_validator)
        self.txt_height.setValidator(double_validator)
        self.txt_thickness.setValidator(double_validator)
        
        # Only allow positive integers for scale
        int_validator = QtGui.QIntValidator()
        int_validator.setBottom(1)  # Only positive values
        self.txt_scale.setValidator(int_validator)
    
    def update_ui_state(self):
        """Update the UI state based on current conditions"""
        # Enable/disable buttons based on whether rectangle is placed
        self.btn_clear_rectangle.setEnabled(self.has_rectangle)
        self.btn_render.setEnabled(self.has_rectangle)
        
        # Export buttons are enabled only after layout is rendered
        # This will be managed by the main plugin class
    
    def on_paper_size_changed(self, index):
        """Handle paper size change in combo box"""
        data = self.cmb_paper_size.itemData(index)
        
        if data:
            # Set width and height from predefined size
            self.txt_width.setText(str(data["width"]))
            self.txt_height.setText(str(data["height"]))
            self.txt_width.setEnabled(False)
            self.txt_height.setEnabled(False)
        else:
            # Enable custom inputs
            self.txt_width.setEnabled(True)
            self.txt_height.setEnabled(True)
            if index == 0:  # Only clear if actually selecting "Custom"
                self.txt_width.clear()
                self.txt_height.clear()
        
        # Emit settings changed signal
        self.paperSizeChanged.emit()
    
    def on_orientation_changed(self, checked):
        """Handle orientation change"""
        if not checked:
            return  # Only respond to the button that was checked
            
        # Swap width and height if necessary
        if self.sender() == self.radio_landscape:
            try:
                width = float(self.txt_width.text())
                height = float(self.txt_height.text())
                if width < height:  # Only swap if width is less than height
                    self.txt_width.setText(str(height))
                    self.txt_height.setText(str(width))
            except (ValueError, TypeError):
                pass  # Do nothing if conversion fails
        
        # Emit settings changed signal
        self.paperSizeChanged.emit()
    
    def on_settings_changed(self):
        """Handle any settings change that would affect rectangle size"""
        # Avoid emitting signals during initialization or validation errors
        try:
            # Validate inputs
            width = float(self.txt_width.text())
            height = float(self.txt_height.text())
            scale = int(self.txt_scale.text())
            
            # Only emit if we have valid values
            if width > 0 and height > 0 and scale > 0:
                # Determine which signal to emit based on sender
                sender = self.sender()
                if sender == self.txt_scale:
                    self.scaleChanged.emit()
                else:
                    self.paperSizeChanged.emit()
        except (ValueError, TypeError):
            pass  # Ignore validation errors
    
    def on_place_rectangle_clicked(self):
        """Handle place rectangle button click"""
        self.placeRectangleRequested.emit()
        self.lbl_status.setText("Click and drag on the map to place a rectangle.")
    
    def on_clear_rectangle_clicked(self):
        """Handle clear rectangle button click"""
        self.clearRectangleRequested.emit()
        self.has_rectangle = False
        self.lbl_region_width.setText("-")
        self.lbl_region_height.setText("-")
        self.update_ui_state()
        self.lbl_status.setText("Rectangle cleared. Place a new rectangle.")
    
    def on_render_clicked(self):
        """Handle render button click"""
        self.renderLayoutRequested.emit()
        self.lbl_status.setText("Creating layout...")
    
    def on_export_pdf_clicked(self):
        """Handle export PDF button click"""
        self.exportPdfRequested.emit()
    
    def on_export_csv_clicked(self):
        """Handle export CSV button click"""
        self.exportCsvRequested.emit()
    
    def on_export_contours_clicked(self):
        """Handle export contours button click"""
        self.exportContoursRequested.emit()
    
    def on_export_laser_clicked(self):
        """Handle export laser-cut layout button click"""
        self.exportLaserRequested.emit()
    
    def on_contour_layer_changed(self, index):
        """Handle contour layer selection change"""
        if index < 0:
            return
            
        # Get the selected layer
        layer_data = self.cmb_contour_layer.itemData(index)
        if not layer_data:
            return
            
        layer = layer_data[0]  # Unpack the layer from the data tuple
        
        # Update the elevation field dropdown
        self.populate_elevation_fields(layer)
        
        # Emit signal with the selected layer
        self.contourLayerChanged.emit(layer)
        
        self.lbl_status.setText(f"Contour layer changed to: {layer.name()}")
    
    def on_elev_field_changed(self, index):
        """Handle elevation field selection change"""
        if index < 0:
            return
            
        field_name = self.cmb_elevation_field.itemText(index)
        if not field_name:
            return
            
        # Emit signal with the selected field
        self.contourElevFieldChanged.emit(field_name)
        
        self.lbl_status.setText(f"Elevation field changed to: {field_name}")
    
    def on_contour_color_clicked(self):
        """Handle contour color button click"""
        color = QtWidgets.QColorDialog.getColor(self.contour_color, self, "Select Contour Color")
        if color.isValid():
            self.contour_color = color
            self.update_color_button()
            self.contourColorChanged.emit(color)
            self.lbl_status.setText(f"Contour color changed.")
    
    def on_thickness_changed(self, thickness_text):
        """Handle sheet thickness value change"""
        try:
            thickness = float(thickness_text)
            if thickness > 0:
                self.contourThicknessChanged.emit(thickness)
        except (ValueError, TypeError):
            pass  # Invalid input, ignore
    
    def update_color_button(self):
        """Update the contour color button appearance"""
        if not hasattr(self, 'contour_color'):
            self.contour_color = QColor(255, 0, 0)  # Default red
            
        # Set background color of button
        self.btn_contour_color.setStyleSheet(
            f"background-color: {self.contour_color.name()}; color: {'black' if self.contour_color.lightness() > 128 else 'white'};"
        )
        
        # Update button text to show color
        self.btn_contour_color.setText(self.contour_color.name())
    
    def populate_contour_layers(self, contour_layers):
        """Populate the contour layer dropdown with detected layers.
        
        :param contour_layers: List of (layer, granularity_score, elevation_field) tuples
        """
        self.cmb_contour_layer.clear()
        
        if not contour_layers:
            self.cmb_contour_layer.addItem("No contour layers found", None)
            self.cmb_contour_layer.setEnabled(False)
            self.cmb_elevation_field.setEnabled(False)
            return
            
        # Add each layer to the dropdown
        for i, (layer, score, elev_field) in enumerate(contour_layers):
            # Store layer and other info as item data
            self.cmb_contour_layer.addItem(f"{layer.name()} ({layer.featureCount()} features)", 
                                          (layer, score, elev_field))
        
        # Enable the dropdowns
        self.cmb_contour_layer.setEnabled(True)
        self.cmb_elevation_field.setEnabled(True)
        
        # Select the first layer (highest granularity)
        if contour_layers:
            self.cmb_contour_layer.setCurrentIndex(0)
            
            # Also populate elevation fields for the selected layer
            self.populate_elevation_fields(contour_layers[0][0])
    
    def populate_elevation_fields(self, layer):
        """Populate the elevation field dropdown for the selected layer.
        
        :param layer: QgsVectorLayer to get fields from
        """
        self.cmb_elevation_field.clear()
        
        if not layer:
            self.cmb_elevation_field.setEnabled(False)
            return
            
        # Get all fields from the layer
        fields = layer.fields()
        
        # Filter for numeric fields
        numeric_fields = []
        for field in fields:
            if field.isNumeric():
                numeric_fields.append(field.name())
        
        # Add fields to the dropdown
        for field_name in numeric_fields:
            self.cmb_elevation_field.addItem(field_name)
        
        # If no numeric fields found
        if not numeric_fields:
            self.cmb_elevation_field.addItem("No numeric fields found")
            self.cmb_elevation_field.setEnabled(False)
            return
        
        # Enable the field selection
        self.cmb_elevation_field.setEnabled(True)
        
        # Try to select the detected elevation field
        selected_layer_idx = self.cmb_contour_layer.currentIndex()
        if selected_layer_idx >= 0:
            layer_data = self.cmb_contour_layer.itemData(selected_layer_idx)
            if layer_data and layer_data[2]:  # Check if elevation field is available
                elev_field = layer_data[2]
                # Find and select the detected elevation field
                for i in range(self.cmb_elevation_field.count()):
                    if self.cmb_elevation_field.itemText(i) == elev_field:
                        self.cmb_elevation_field.setCurrentIndex(i)
                        break
    
    def get_selected_contour_layer(self):
        """Get the currently selected contour layer.
        
        :return: Selected contour layer or None
        """
        index = self.cmb_contour_layer.currentIndex()
        if index < 0:
            return None
            
        layer_data = self.cmb_contour_layer.itemData(index)
        if not layer_data:
            return None
            
        return layer_data[0]  # Return the layer
    
    def get_selected_elevation_field(self):
        """Get the currently selected elevation field.
        
        :return: Selected elevation field name or None
        """
        index = self.cmb_elevation_field.currentIndex()
        if index < 0:
            return None
            
        return self.cmb_elevation_field.itemText(index)
    
    def set_rectangle_info(self, width, height):
        """Update the rectangle information labels"""
        # Round to 2 decimal places for display
        width_str = f"{width:.2f} m"
        height_str = f"{height:.2f} m"
        
        self.lbl_region_width.setText(width_str)
        self.lbl_region_height.setText(height_str)
        self.has_rectangle = True
        self.update_ui_state()
        
    def get_settings(self):
        """Get all the current settings as a dictionary"""
        try:
            settings = {
                "paper_width": float(self.txt_width.text()),
                "paper_height": float(self.txt_height.text()),
                "scale": int(self.txt_scale.text()),
                "thickness": float(self.txt_thickness.text()),
                "orientation": "portrait" if self.radio_portrait.isChecked() else "landscape",
                "contour_color": self.contour_color
            }
            return settings
        except (ValueError, TypeError):
            # Handle case where inputs are invalid
            return None
        
    def set_status(self, message):
        """Update the status label"""
        self.lbl_status.setText(message)
    
    def closeEvent(self, event):
        """Handle the dialog being closed with the X button"""
        # Emit the finished signal to trigger cleanup in the main plugin
        self.finished.emit(0)  # 0 = rejected
        super().closeEvent(event) 