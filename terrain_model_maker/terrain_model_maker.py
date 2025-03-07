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
from datetime import datetime

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QSizeF, QRectF
from qgis.PyQt.QtGui import QIcon, QColor, QFont
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox

from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsLayoutItemMap,
    QgsLayoutItemScaleBar,
    QgsLayoutItemLabel,
    QgsLayoutExporter,
    QgsUnitTypes,
    QgsPrintLayout,
    Qgis
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsMapToolEmitPoint, QgsMapToolPan

# Initialize Qt resources from file resources.py
try:
    from .resources import *
except ImportError:
    import resources

# Import the dialog
from .terrain_model_dialog import TerrainModelDialog
from .utils import calculate_rectangle_dimensions, calculate_scale, calculate_contour_step


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
        self.first_start = None
        
        # Initialize rectangle selection tool
        self.rectangle_tool = None
        self.rubber_band = None
        self.rectangle = None
        
        # Initialize layout
        self.layout = None
        self.layout_name = "TerrainModel"
        
        # Save state
        self.last_directory = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
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

        icon_path = ':/plugins/terrain_model_maker/icon.png'
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
            
        # Clean up resources
        if self.rubber_band:
            self.rubber_band.reset()
            self.rubber_band = None
            
        if self.rectangle_tool:
            self.iface.mapCanvas().unsetMapTool(self.rectangle_tool)
            self.rectangle_tool = None

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog and keep reference
        self.dlg = TerrainModelDialog(self.iface)
        
        # Connect signals
        self.connect_signals()
        
        # Initialize rubber band
        if not self.rubber_band:
            self.rubber_band = QgsRubberBand(self.iface.mapCanvas(), Qgis.GeometryType.Polygon)
            self.rubber_band.setColor(QColor(255, 0, 0, 100))
            self.rubber_band.setWidth(2)

        # Show the dialog
        self.dlg.show()

    def connect_signals(self):
        """Connect dialog signals to slots"""
        self.dlg.placeRectangleRequested.connect(self.activate_rectangle_tool)
        self.dlg.clearRectangleRequested.connect(self.clear_rectangle)
        self.dlg.renderLayoutRequested.connect(self.create_layout)
        self.dlg.refreshLayoutRequested.connect(self.refresh_layout)
        self.dlg.exportPdfRequested.connect(self.export_pdf)
        self.dlg.exportCsvRequested.connect(self.export_csv)
        self.dlg.exportContoursRequested.connect(self.export_contours)
        self.dlg.exportLaserRequested.connect(self.export_laser_cut)
        
    def activate_rectangle_tool(self):
        """Activate the rectangle selection tool"""
        # Get settings from dialog
        settings = self.dlg.get_settings()
        if not settings:
            self.dlg.set_status("Invalid settings. Please check your inputs.")
            return
            
        # Calculate the real-world dimensions based on scale and paper size
        paper_width_mm = settings['paper_width']
        paper_height_mm = settings['paper_height']
        scale = settings['scale']
        
        # Convert mm to meters and apply scale
        rect_width_m = (paper_width_mm / 1000.0) * scale  # Real-world width in meters
        rect_height_m = (paper_height_mm / 1000.0) * scale  # Real-world height in meters
        
        # Ensure rubber band exists
        if not self.rubber_band:
            self.rubber_band = QgsRubberBand(self.iface.mapCanvas(), Qgis.GeometryType.Polygon)
            self.rubber_band.setColor(QColor(255, 0, 0, 100))
            self.rubber_band.setWidth(2)
            
        # Create the rectangle tool with fixed dimensions
        self.rectangle_tool = FixedSizeRectangleTool(
            self.iface.mapCanvas(), 
            self, 
            self.rubber_band,
            rect_width_m,
            rect_height_m
        )
            
        # Set the map tool
        self.iface.mapCanvas().setMapTool(self.rectangle_tool)
        self.dlg.set_status(f"Click on the map to place a {rect_width_m:.1f}m × {rect_height_m:.1f}m rectangle (based on scale 1:{scale})")
        
    def set_rectangle(self, rectangle):
        """Set the selected rectangle
        
        :param rectangle: QgsRectangle representing the selection
        """
        self.rectangle = rectangle
        
        # Calculate dimensions
        canvas = self.iface.mapCanvas()
        crs = canvas.mapSettings().destinationCrs()
        width, height, area = calculate_rectangle_dimensions(rectangle, crs)  # Unpack all three values
        
        # Update dialog
        self.dlg.set_rectangle_info(width, height)
        self.dlg.set_status(f"Rectangle placed. Width: {width:.2f}m, Height: {height:.2f}m, Area: {area:.2f}m²")
        
    def clear_rectangle(self):
        """Clear the selected rectangle"""
        if self.rubber_band:
            self.rubber_band.reset()
            
        self.rectangle = None
        
        # Stop rectangle tool
        if self.rectangle_tool:
            self.iface.mapCanvas().unsetMapTool(self.rectangle_tool)
            self.iface.mapCanvas().setMapTool(QgsMapToolPan(self.iface.mapCanvas()))
            
    def create_layout(self):
        """Create a new print layout with the map and settings"""
        if not self.rectangle:
            self.dlg.set_status("No rectangle selected. Please place a rectangle first.")
            return
            
        # Get settings from dialog
        settings = self.dlg.get_settings()
        if not settings:
            self.dlg.set_status("Invalid settings. Please check your inputs.")
            return
            
        # Create timestamp for unique layout name
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.layout_name = f"TerrainModel_{timestamp}"
        
        # Create the layout
        project = QgsProject.instance()
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(self.layout_name)
        
        # Set the page size (convert mm to layout units)
        page_size = QgsLayoutSize(
            settings['paper_width'],
            settings['paper_height'],
            QgsUnitTypes.LayoutMillimeters
        )
        layout.pageCollection().pages()[0].setPageSize(page_size)
        
        # Add a map item
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptSetSceneRect(QRectF(20, 20, settings['paper_width'] - 40, settings['paper_height'] - 40))
        map_item.setFrameEnabled(True)
        
        # Set the map extent to our rectangle
        map_item.setExtent(self.rectangle)
        
        # Add the map to the layout
        layout.addLayoutItem(map_item)
        
        # Add scale bar
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setStyle('Single Box')
        scale_bar.setUnits(QgsUnitTypes.DistanceMeters)
        scale_bar.setNumberOfSegments(5)
        scale_bar.setNumberOfSegmentsLeft(0)
        scale_bar.setUnitsPerSegment(100)
        scale_bar.setLinkedMap(map_item)
        scale_bar.setUnitLabel('m')
        scale_bar.setFrameEnabled(True)
        scale_bar.attemptSetSceneRect(QRectF(20, settings['paper_height'] - 30, 80, 20))
        layout.addLayoutItem(scale_bar)
        
        # Add title
        title = QgsLayoutItemLabel(layout)
        title.setText(f"Terrain Model - Scale 1:{settings['scale']}")
        title.setFont(QFont('Arial', 14))
        title.adjustSizeToText()
        title.attemptSetSceneRect(QRectF(0, 5, settings['paper_width'], 20))
        title.setHAlign(Qt.AlignHCenter)
        layout.addLayoutItem(title)
        
        # Add to project
        project.layoutManager().addLayout(layout)
        self.layout = layout
        
        # Show the layout
        self.iface.openLayoutDesigner(layout)
        
        # Enable export buttons
        self.dlg.btn_export_pdf.setEnabled(True)
        self.dlg.btn_export_csv.setEnabled(True)
        self.dlg.btn_export_contours.setEnabled(True)
        self.dlg.btn_export_laser.setEnabled(True)
        
        self.dlg.set_status("Layout created. You can now export in various formats.")
        
    def refresh_layout(self):
        """Refresh the existing layout with current layers"""
        if not self.layout:
            self.dlg.set_status("No layout created yet. Please render a layout first.")
            return
            
        # Find the map item
        map_items = [item for item in self.layout.items() if isinstance(item, QgsLayoutItemMap)]
        if not map_items:
            self.dlg.set_status("Error: No map found in layout.")
            return
            
        # Refresh the map
        for map_item in map_items:
            map_item.refresh()
            
        self.dlg.set_status("Layout refreshed with current layers.")
        
    def export_pdf(self):
        """Export the layout as PDF"""
        if not self.layout:
            self.dlg.set_status("No layout created yet. Please render a layout first.")
            return
            
        # Ask for file path
        file_path, _ = QFileDialog.getSaveFileName(
            self.dlg,
            "Save PDF",
            self.get_last_directory(),
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
            
        self.set_last_directory(os.path.dirname(file_path))
        
        # Add extension if not present
        if not file_path.lower().endswith('.pdf'):
            file_path += '.pdf'
            
        # Export as PDF
        exporter = QgsLayoutExporter(self.layout)
        result = exporter.exportToPdf(file_path, QgsLayoutExporter.PdfExportSettings())
        
        if result == QgsLayoutExporter.Success:
            self.dlg.set_status(f"PDF exported successfully to {file_path}")
        else:
            self.dlg.set_status("Error exporting PDF.")
            
    def export_csv(self):
        """Export the terrain data as CSV"""
        # This will be implemented in future versions
        self.dlg.set_status("CSV export not yet implemented.")
        
    def export_contours(self):
        """Export contours as CSV"""
        # This will be implemented in future versions
        self.dlg.set_status("Contour export not yet implemented.")
        
    def export_laser_cut(self):
        """Export laser-cut layout"""
        # This will be implemented in future versions
        self.dlg.set_status("Laser-cut export not yet implemented.")
        
    def get_last_directory(self):
        """Get the last used directory"""
        if not self.last_directory:
            self.last_directory = os.path.expanduser("~")
        return self.last_directory
        
    def set_last_directory(self, directory):
        """Set the last used directory"""
        self.last_directory = directory


class FixedSizeRectangleTool(QgsMapToolEmitPoint):
    """Map tool for placing a fixed-size rectangle"""
    
    def __init__(self, canvas, plugin, rubber_band=None, width_m=1000, height_m=1000):
        self.canvas = canvas
        self.plugin = plugin
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        
        # Initialize rubber band
        self.rubber_band = rubber_band
        if not self.rubber_band:
            self.rubber_band = QgsRubberBand(self.canvas, Qgis.GeometryType.Polygon)
            self.rubber_band.setColor(QColor(255, 0, 0, 100))
            self.rubber_band.setWidth(2)
            
        # Store rectangle dimensions in meters
        self.width_m = width_m
        self.height_m = height_m
        
        # State variables
        self.center_point = None
        self.is_moving = False
        self.start_drag_point = None
        self.rectangle = None
        
        # Set cursor
        self.setCursor(Qt.CrossCursor)
        
    def canvasPressEvent(self, e):
        """Handle canvas press event"""
        self.center_point = self.toMapCoordinates(e.pos())
        
        if not self.rectangle:
            # Initial placement - create rectangle
            self.create_rectangle_at_point(self.center_point)
        else:
            # Check if clicked inside rectangle
            point = QgsPointXY(self.center_point)
            geom = QgsGeometry.fromRect(self.rectangle)
            if geom.contains(point):
                # Start dragging
                self.is_moving = True
                self.start_drag_point = self.center_point
            else:
                # Clicked outside existing rectangle - create a new one
                self.rubber_band.reset()
                self.create_rectangle_at_point(self.center_point)
        
    def canvasMoveEvent(self, e):
        """Handle canvas move event"""
        if not self.is_moving:
            return
            
        # Calculate offset from start drag point
        current_point = self.toMapCoordinates(e.pos())
        dx = current_point.x() - self.start_drag_point.x()
        dy = current_point.y() - self.start_drag_point.y()
        
        # Move the rectangle by this offset
        self.create_rectangle_at_point(QgsPointXY(
            self.center_point.x() + dx,
            self.center_point.y() + dy
        ))
        
        # Update start drag point for next move
        self.start_drag_point = current_point
        
    def canvasReleaseEvent(self, e):
        """Handle canvas release event"""
        if self.is_moving:
            # End dragging - set new center point
            current_point = self.toMapCoordinates(e.pos())
            dx = current_point.x() - self.start_drag_point.x()
            dy = current_point.y() - self.start_drag_point.y()
            self.center_point = QgsPointXY(
                self.center_point.x() + dx,
                self.center_point.y() + dy
            )
            self.is_moving = False
        
        # Set the rectangle in the plugin
        if self.rectangle:
            self.plugin.set_rectangle(self.rectangle)
        
    def create_rectangle_at_point(self, point):
        """Create a rectangle centered at the given point"""
        # Get the map CRS
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        
        # Calculate distance per degree (approximate)
        # We need to convert meters to map units
        distance_calc = QgsDistanceArea()
        distance_calc.setSourceCrs(canvas_crs, QgsProject.instance().transformContext())
        distance_calc.setEllipsoid(QgsProject.instance().ellipsoid())
        
        # Calculate half-width and half-height in map units
        # First, get the points for a "unit square" in the current CRS
        center_point = QgsPointXY(point.x(), point.y())
        east_point = QgsPointXY(point.x() + 0.00001, point.y())  # Small offset east
        north_point = QgsPointXY(point.x(), point.y() + 0.00001)  # Small offset north
        
        # Calculate real-world distance of these small offsets
        dx_meters = distance_calc.measureLine([center_point, east_point])
        dy_meters = distance_calc.measureLine([center_point, north_point])
        
        # Calculate conversion factors (map units per meter)
        x_factor = 0.00001 / dx_meters if dx_meters > 0 else 0
        y_factor = 0.00001 / dy_meters if dy_meters > 0 else 0
        
        # Calculate half dimensions in map units
        half_width = (self.width_m / 2) * x_factor
        half_height = (self.height_m / 2) * y_factor
        
        # Create the rectangle
        self.rectangle = QgsRectangle(
            point.x() - half_width,
            point.y() - half_height,
            point.x() + half_width,
            point.y() + half_height
        )
        
        # Update the rubber band
        self.update_rubber_band()
        
    def update_rubber_band(self):
        """Update the rubber band to show current selection"""
        if not self.rectangle:
            return
            
        self.rubber_band.reset()
        
        # Create rectangle points (clockwise)
        points = [
            QgsPointXY(self.rectangle.xMinimum(), self.rectangle.yMinimum()),
            QgsPointXY(self.rectangle.xMaximum(), self.rectangle.yMinimum()),
            QgsPointXY(self.rectangle.xMaximum(), self.rectangle.yMaximum()),
            QgsPointXY(self.rectangle.xMinimum(), self.rectangle.yMaximum()),
            QgsPointXY(self.rectangle.xMinimum(), self.rectangle.yMinimum())  # Close the polygon
        ]
        
        for point in points:
            self.rubber_band.addPoint(point) 