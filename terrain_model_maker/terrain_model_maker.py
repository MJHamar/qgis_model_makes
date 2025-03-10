# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TerrainModelMaker
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
import os.path
import math
import time

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QSize, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QToolButton, QMenu, QFileDialog

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsRectangle,
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsExpressionContextUtils,
    QgsMessageLog
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsMapToolEmitPoint, QgsMapToolPan
from qgis.core import Qgis

# Initialize Qt resources from file resources.py
# This is autogenerated by the QGIS plugin builder
try:
    from .resources import *
except ImportError:
    import resources

# Import the dialog
from .terrain_model_dialog import TerrainModelDialog
from .utils import calculate_rectangle_dimensions, calculate_scale, calculate_contour_step, PAPER_SIZES
from .contour_filter import find_contour_layer, filter_contours_by_interval, export_contours_to_file
from .preview import create_preview


class TerrainModelMaker:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'TerrainModelMaker_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&Terrain Model Maker')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        
        # Region selection variables
        self.rubber_band = None
        self.map_tool = None
        self.selection_points = []
        self.selected_region = None
        self.contour_step = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('TerrainModelMaker', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/terrain_model_maker/resources/icon.svg'
        self.add_action(
            icon_path,
            text=self.tr('Terrain Model Maker'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr('&Terrain Model Maker'),
                action)
            self.iface.removeToolBarIcon(action)
        
        # Clean up map tools if active
        if self.map_tool and self.iface.mapCanvas().mapTool() == self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
        if self.rubber_band:
            self.iface.mapCanvas().scene().removeItem(self.rubber_band)
            self.rubber_band = None

    def run(self):
        """Run method that performs all the real work"""
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = TerrainModelDialog(self.iface)
        
        # Set up event connections for the dialog
        self.connect_dialog_signals()
        
        # Show the dialog
        self.dlg.show()
    
    def connect_dialog_signals(self):
        """Connect signals from the dialog to methods"""
        # Connect buttons
        self.dlg.btn_select_region.clicked.connect(self.start_region_selection)
        self.dlg.btn_clear_selection.clicked.connect(self.clear_selection)
        self.dlg.btn_calculate_scale.clicked.connect(self.calculate_scale)
        self.dlg.btn_preview.clicked.connect(self.preview_layout)
        self.dlg.btn_filter_contours.clicked.connect(self.filter_contours)
        self.dlg.btn_browse_output.clicked.connect(self.browse_output_dir)
        self.dlg.btn_export.clicked.connect(self.export_contours)
        
        # Connect thickness field to update contour step
        self.dlg.txt_thickness.textChanged.connect(self.update_contour_step)
        
        # Connect paper dimension fields to check if scale button should be enabled
        self.dlg.txt_paper_width.textChanged.connect(self.check_enable_scale_button)
        self.dlg.txt_paper_height.textChanged.connect(self.check_enable_scale_button)
        
        # Connect to paper size change to check if scale button should be enabled
        # This connection is made after the dialog's own connection, so it will run after
        self.dlg.cmb_paper_size.currentIndexChanged.connect(self.check_enable_scale_button)
    
    def start_region_selection(self):
        """Start the process of selecting a region on the map"""
        # Clear previous selection
        self.clear_selection()
        
        # Create a new rubber band for selection
        self.rubber_band = QgsRubberBand(self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        
        # Reset points list
        self.selection_points = []
        
        # Create and set the map tool
        self.map_tool = RegionSelectTool(self.iface.mapCanvas(), self)
        self.iface.mapCanvas().setMapTool(self.map_tool)
        
        # Update status
        self.dlg.lbl_status.setText("Click on the map to define the region corners (rectangle)")
    
    def handle_region_selection(self, start_point, end_point):
        """Handle the selection of a region from two points"""
        try:
            # Get min/max coordinates to create a proper rectangle
            x_min = min(start_point.x(), end_point.x())
            y_min = min(start_point.y(), end_point.y())
            x_max = max(start_point.x(), end_point.x())
            y_max = max(start_point.y(), end_point.y())
            
            # Create a rectangle and store it
            rect = QgsRectangle(x_min, y_min, x_max, y_max)
            self.selected_region = rect
            
            # Add the rectangle to the rubber band
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self.rubber_band.addPoint(QgsPointXY(x_min, y_min), False)
            self.rubber_band.addPoint(QgsPointXY(x_max, y_min), False)
            self.rubber_band.addPoint(QgsPointXY(x_max, y_max), False)
            self.rubber_band.addPoint(QgsPointXY(x_min, y_max), False)
            self.rubber_band.addPoint(QgsPointXY(x_min, y_min), True)  # True = update canvas
            
            # Switch back to pan tool
            pan_tool = QgsMapToolPan(self.iface.mapCanvas())
            self.iface.mapCanvas().setMapTool(pan_tool)
            
            # Update status and enable next step
            self.dlg.lbl_status.setText("Region selected. You can now specify paper dimensions.")
            self.dlg.paper_group.setEnabled(True)
            
            # Update region information in the dialog
            self.update_region_info()
            
        except Exception as e:
            self.dlg.lbl_status.setText(f"Error during region selection: {str(e)}")
            # Reset selection
            self.clear_selection()
    
    def update_region_info(self):
        """Update the region information displayed in the dialog"""
        if self.selected_region:
            # Calculate area in square meters
            area = self.selected_region.area()
            width = self.selected_region.width()
            height = self.selected_region.height()
            
            # Update labels
            self.dlg.lbl_region_width.setText(f"{width:.2f} map units")
            self.dlg.lbl_region_height.setText(f"{height:.2f} map units")
            self.dlg.lbl_region_area.setText(f"{area:.2f} square map units")
            
            # Check if we should enable the calculate scale button
            self.check_enable_scale_button()
    
    def clear_selection(self):
        """Clear the current region selection"""
        # Clear rubber band
        if self.rubber_band:
            self.iface.mapCanvas().scene().removeItem(self.rubber_band)
            self.rubber_band = None
        
        # Reset variables
        self.selection_points = []
        self.selected_region = None
        
        # Update dialog
        self.dlg.lbl_status.setText("No region selected. Click 'Select Region' to start.")
        self.dlg.paper_group.setEnabled(False)
        self.dlg.scale_group.setEnabled(False)
        self.dlg.btn_calculate_scale.setEnabled(False)
        
        # Clear region info
        self.dlg.lbl_region_width.setText("-")
        self.dlg.lbl_region_height.setText("-")
        self.dlg.lbl_region_area.setText("-")
    
    def calculate_scale(self):
        """Calculate the required scale based on region and paper dimensions"""
        try:
            # Get paper dimensions in mm
            paper_width = float(self.dlg.txt_paper_width.text())
            paper_height = float(self.dlg.txt_paper_height.text())
            
            # Check for valid values
            if paper_width <= 0 or paper_height <= 0:
                self.dlg.lbl_status.setText("Paper dimensions must be positive numbers.")
                return
            
            # Get region dimensions
            region_width = self.selected_region.width()
            region_height = self.selected_region.height()
            
            # Calculate required scale for width and height
            width_scale = region_width / (paper_width / 1000)  # Convert mm to m
            height_scale = region_height / (paper_height / 1000)
            
            # Use the larger scale to ensure the entire region fits
            required_scale = max(width_scale, height_scale)
            
            # Round up to nearest 1000
            rounded_scale = math.ceil(required_scale / 1000) * 1000
            
            # Update the UI
            self.dlg.txt_scale.setText(str(int(rounded_scale)))
            self.dlg.lbl_status.setText(f"Scale calculated: 1:{rounded_scale}")
            
            # Enable scale group and buttons
            self.dlg.scale_group.setEnabled(True)
            self.dlg.btn_preview.setEnabled(True)
            
            # Enable contour group for next step
            self.dlg.contour_group.setEnabled(True)
            
        except ValueError:
            self.dlg.lbl_status.setText("Please enter valid paper dimensions (numbers only).")

    def preview_layout(self):
        """Preview the terrain model layout"""
        try:
            # Get the scale and paper dimensions
            scale = int(self.dlg.txt_scale.text())
            paper_width = float(self.dlg.txt_paper_width.text())
            paper_height = float(self.dlg.txt_paper_height.text())
            
            # Find contour layer in the project
            contour_layer = find_contour_layer()
            
            if not contour_layer:
                self.dlg.lbl_status.setText("No contour layer found in the project")
                return
                
            # Create and show the preview dialog
            # Pass the map canvas CRS along with the selected region
            create_preview(
                self.dlg, 
                contour_layer, 
                self.selected_region, 
                self.iface.mapCanvas().mapSettings().destinationCrs(),
                scale, 
                paper_width, 
                paper_height
            )
            
            # Update status
            self.dlg.lbl_status.setText("Preview created")
            
        except Exception as e:
            self.dlg.lbl_status.setText(f"Error creating preview: {str(e)}")

    def update_contour_step(self):
        """Update the contour step based on the thickness and scale"""
        try:
            # Get the scale and thickness values
            scale = int(self.dlg.txt_scale.text())
            thickness_mm = float(self.dlg.txt_thickness.text())
            
            # Calculate the contour step
            contour_step = calculate_contour_step(scale, thickness_mm)
            
            # Update the UI
            self.dlg.lbl_contour_step.setText(f"{contour_step} m")
            
            # Enable the filter button
            self.dlg.btn_filter_contours.setEnabled(True)
            
        except (ValueError, TypeError):
            self.dlg.lbl_contour_step.setText("-")
            self.dlg.btn_filter_contours.setEnabled(False)
    
    def filter_contours(self):
        """Filter contours based on the specified parameters"""
        try:
            # Get the contour step
            scale = int(self.dlg.txt_scale.text())
            thickness_mm = float(self.dlg.txt_thickness.text())
            
            contour_step = calculate_contour_step(scale, thickness_mm)
            
            # Find the contour layer
            contour_layer = find_contour_layer()
            if not contour_layer:
                self.dlg.lbl_status.setText("No contour layer found in the project")
                return
            
            # Store the contour step for later use
            self.contour_step = contour_step
            
            # Enable the export group
            self.dlg.export_group.setEnabled(True)
            self.dlg.btn_export.setEnabled(True)
            
            # Update status
            self.dlg.lbl_status.setText(f"Contours will be filtered using {contour_step}m step. Ready for export.")
            
        except Exception as e:
            self.dlg.lbl_status.setText(f"Error filtering contours: {str(e)}")
    
    def browse_output_dir(self):
        """Browse for output directory"""
        output_dir = QFileDialog.getExistingDirectory(
            self.dlg, "Select Output Directory", ""
        )
        if output_dir:
            self.dlg.txt_output_dir.setText(output_dir)
    
    def export_contours(self):
        """Export filtered contours for laser cutting"""
        try:
            # Get output directory and format
            output_dir = self.dlg.txt_output_dir.text()
            if not output_dir:
                self.dlg.lbl_status.setText("Please select an output directory")
                return
            
            # Create output directory if it doesn't exist
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Get output format
            format_idx = self.dlg.cmb_output_format.currentIndex()
            formats = ["CSV", "DXF", "SVG"]
            output_format = formats[format_idx]
            
            # Get scale and contour step
            scale = int(self.dlg.txt_scale.text())
            
            # Find contour layer
            contour_layer = find_contour_layer()
            if not contour_layer:
                self.dlg.lbl_status.setText("No contour layer found in the project")
                return
            
            # Filter contours based on step
            try:
                filtered_layer = filter_contours_by_interval(
                    contour_layer, 
                    self.contour_step, 
                    self.selected_region,
                    self.iface.mapCanvas().mapSettings().destinationCrs()
                )
                
                if not filtered_layer:
                    self.dlg.lbl_status.setText("No contours were found in the selected region")
                    return
            except Exception as filter_error:
                import traceback
                error_trace = traceback.format_exc()
                self.dlg.lbl_status.setText(f"Error filtering contours: {str(filter_error)}")
                QgsMessageLog.logMessage(f"Error filtering contours: {str(filter_error)}\n{error_trace}", "TerrainModelMaker", Qgis.Critical)
                return
                
            # Export to file
            output_filename = f"terrain_model_scale_{scale}.{output_format.lower()}"
            output_path = os.path.join(output_dir, output_filename)
            
            try:
                # Pass the selected region and its CRS for proper boundary handling
                success = export_contours_to_file(
                    filtered_layer, 
                    output_path, 
                    output_format,
                    self.selected_region,
                    self.iface.mapCanvas().mapSettings().destinationCrs()
                )
                
                if success:
                    self.dlg.lbl_status.setText(f"Successfully exported to {output_path}")
                else:
                    self.dlg.lbl_status.setText(f"Error exporting to {output_format}")
            except Exception as export_error:
                import traceback
                error_trace = traceback.format_exc()
                self.dlg.lbl_status.setText(f"Error during export: {str(export_error)}")
                QgsMessageLog.logMessage(f"Error during export: {str(export_error)}\n{error_trace}", "TerrainModelMaker", Qgis.Critical)
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            self.dlg.lbl_status.setText(f"Error exporting contours: {str(e)}")
            QgsMessageLog.logMessage(f"Error exporting contours: {str(e)}\n{error_trace}", "TerrainModelMaker", Qgis.Critical)

    def check_enable_scale_button(self):
        """Check if calculate scale button should be enabled"""
        if self.selected_region and self.dlg.txt_paper_width.text() and self.dlg.txt_paper_height.text():
            self.dlg.btn_calculate_scale.setEnabled(True)
        else:
            self.dlg.btn_calculate_scale.setEnabled(False)


class RegionSelectTool(QgsMapToolEmitPoint):
    """Custom map tool for selecting a rectangular region"""
    
    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.canvas = canvas
        self.plugin = plugin
        self.cursor = Qt.CrossCursor
        
        # Create temporary rubber band for showing the rectangle during drawing
        self.temp_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.temp_rubber_band.setColor(QColor(255, 0, 0, 100))
        self.temp_rubber_band.setWidth(2)
        
        self.start_point = None
    
    def canvasPressEvent(self, event):
        """Handle mouse press event"""
        if event.button() == Qt.LeftButton:
            self.start_point = self.toMapCoordinates(event.pos())
    
    def canvasMoveEvent(self, event):
        """Handle mouse move event to update the temporary rubber band"""
        if not self.start_point:
            return
        
        # Get current mouse position
        current_point = self.toMapCoordinates(event.pos())
        
        # Create a rectangle from the two points
        x_min = min(self.start_point.x(), current_point.x())
        y_min = min(self.start_point.y(), current_point.y())
        x_max = max(self.start_point.x(), current_point.x())
        y_max = max(self.start_point.y(), current_point.y())
        
        # Update the temporary rubber band
        self.temp_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.temp_rubber_band.addPoint(QgsPointXY(x_min, y_min), False)
        self.temp_rubber_band.addPoint(QgsPointXY(x_max, y_min), False)
        self.temp_rubber_band.addPoint(QgsPointXY(x_max, y_max), False)
        self.temp_rubber_band.addPoint(QgsPointXY(x_min, y_max), False)
        self.temp_rubber_band.addPoint(QgsPointXY(x_min, y_min), True)  # True = update canvas
    
    def canvasReleaseEvent(self, event):
        """Handle mouse release event to complete the rectangle"""
        if event.button() == Qt.LeftButton and self.start_point:
            # Get release point
            end_point = self.toMapCoordinates(event.pos())
            
            # Pass the rectangle to the plugin
            self.plugin.handle_region_selection(self.start_point, end_point)
            
            # Reset the temporary rubber band
            self.temp_rubber_band.reset()
            self.start_point = None
    
    def deactivate(self):
        """Clean up when tool is deactivated"""
        self.temp_rubber_band.reset()
        QgsMapTool.deactivate(self) 