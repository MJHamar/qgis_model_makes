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
from qgis.gui import QgsMapCanvas

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
    refreshLayoutRequested = pyqtSignal()
    exportPdfRequested = pyqtSignal()
    exportCsvRequested = pyqtSignal()
    exportContoursRequested = pyqtSignal()
    exportLaserRequested = pyqtSignal()
    
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
        
    def setup_connections(self):
        """Set up signal/slot connections"""
        # Button connections
        self.btn_place_rectangle.clicked.connect(self.on_place_rectangle_clicked)
        self.btn_clear_rectangle.clicked.connect(self.on_clear_rectangle_clicked)
        self.btn_render.clicked.connect(self.on_render_clicked)
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        self.btn_export_pdf.clicked.connect(self.on_export_pdf_clicked)
        self.btn_export_csv.clicked.connect(self.on_export_csv_clicked)
        self.btn_export_contours.clicked.connect(self.on_export_contours_clicked)
        self.btn_export_laser.clicked.connect(self.on_export_laser_clicked)
        
        # Paper size and orientation connections
        self.cmb_paper_size.currentIndexChanged.connect(self.on_paper_size_changed)
        self.radio_portrait.toggled.connect(self.on_orientation_changed)
        self.radio_landscape.toggled.connect(self.on_orientation_changed)
        
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
        self.btn_refresh.setEnabled(self.has_rectangle)
        
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
    
    def on_refresh_clicked(self):
        """Handle refresh button click"""
        self.refreshLayoutRequested.emit()
        self.lbl_status.setText("Refreshing layout...")
    
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
                "orientation": "portrait" if self.radio_portrait.isChecked() else "landscape"
            }
            return settings
        except (ValueError, TypeError):
            # Handle case where inputs are invalid
            return None
        
    def set_status(self, message):
        """Update the status label"""
        self.lbl_status.setText(message) 