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
from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsMapCanvas

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'terrain_model_dialog_base.ui'))


class TerrainModelDialog(QtWidgets.QDialog, FORM_CLASS):
    """Dialog for the Terrain Model Maker plugin"""
    
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(TerrainModelDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        
        # Initialize UI elements
        self.init_ui()
        
        # Set up standard paper sizes in the combo box
        self.setup_paper_sizes()
    
    def init_ui(self):
        """Initialize UI elements"""
        # Disable groups until they're needed
        self.paper_group.setEnabled(False)
        self.scale_group.setEnabled(False)
        self.contour_group.setEnabled(False)
        self.export_group.setEnabled(False)
        
        # Disable buttons that require previous steps
        self.btn_calculate_scale.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_filter_contours.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        # Set initial status
        self.lbl_status.setText("No region selected. Click 'Select Region' to start.")
        
        # Set up validators for numeric fields
        self.setup_validators()
    
    def setup_validators(self):
        """Set up validators for numeric input fields"""
        # Only allow positive numbers for paper dimensions and thickness
        double_validator = QtGui.QDoubleValidator()
        double_validator.setBottom(0.0)  # Only positive values
        
        self.txt_paper_width.setValidator(double_validator)
        self.txt_paper_height.setValidator(double_validator)
        self.txt_thickness.setValidator(double_validator)
        
        # Only allow positive integers for scale
        int_validator = QtGui.QIntValidator()
        int_validator.setBottom(1)  # Only positive values
        self.txt_scale.setValidator(int_validator)
    
    def setup_paper_sizes(self):
        """Set up standard paper sizes in the combo box"""
        # Clear existing items
        self.cmb_paper_size.clear()
        
        # Add standard paper sizes in mm
        self.cmb_paper_size.addItem("Custom", None)  # Custom size
        self.cmb_paper_size.addItem("A4 (210 × 297 mm)", {"width": 210, "height": 297})
        self.cmb_paper_size.addItem("A3 (297 × 420 mm)", {"width": 297, "height": 420})
        self.cmb_paper_size.addItem("A2 (420 × 594 mm)", {"width": 420, "height": 594})
        self.cmb_paper_size.addItem("A1 (594 × 841 mm)", {"width": 594, "height": 841})
        self.cmb_paper_size.addItem("A0 (841 × 1189 mm)", {"width": 841, "height": 1189})
        
        # Connect the signal for paper size change
        self.cmb_paper_size.currentIndexChanged.connect(self.paper_size_changed)
    
    def paper_size_changed(self, index):
        """Handle paper size change in combo box"""
        # Get the data (paper dimensions) for the selected item
        data = self.cmb_paper_size.currentData()
        
        if data:
            # If a standard size is selected, fill in the dimensions
            self.txt_paper_width.setText(str(data["width"]))
            self.txt_paper_height.setText(str(data["height"]))
            self.txt_paper_width.setEnabled(False)
            self.txt_paper_height.setEnabled(False)
        else:
            # If custom size is selected, enable the input fields
            self.txt_paper_width.setEnabled(True)
            self.txt_paper_height.setEnabled(True)
            if index == 0:  # Only clear if actually selecting "Custom"
                self.txt_paper_width.clear()
                self.txt_paper_height.clear() 