# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TerrainModelMaker
                                 A QGIS plugin
 Creates laser cuttable terrain models from contour data
                              -------------------
        begin                : 2023-09-15
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Miklos Hamar
        email                : szad5615@gmail.com
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
import tempfile
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QPolygonF
from PyQt5.QtCore import Qt, QRectF, QPointF
from qgis.core import QgsRectangle, QgsGeometry, QgsCoordinateTransform, QgsProject, QgsFeatureRequest, QgsWkbTypes
from .contour_filter import remap_contours_to_rect

class PreviewDialog(QDialog):
    """Dialog for previewing the terrain model layout."""
    
    def __init__(self, parent=None, contour_layer=None, region_rect=None, region_crs=None, scale=None, paper_width=None, paper_height=None):
        """
        Initialize the preview dialog.
        
        :param parent: Parent widget
        :param contour_layer: The contour layer to preview
        :param region_rect: The selected region rectangle
        :param region_crs: The CRS of the region rectangle
        :param scale: The model scale (1:x)
        :param paper_width: Paper width in mm
        :param paper_height: Paper height in mm
        """
        super(PreviewDialog, self).__init__(parent)
        self.setWindowTitle("Terrain Model Preview")
        self.setMinimumSize(800, 600)
        
        self.contour_layer = contour_layer
        self.region_rect = region_rect
        self.region_crs = region_crs
        self.scale = scale
        self.paper_width = paper_width
        self.paper_height = paper_height
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Graphics view for preview
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        layout.addWidget(self.view)
        
        # Info label
        self.info_label = QLabel()
        layout.addWidget(self.info_label)
        
        # Button layout
        button_layout = QVBoxLayout()
        self.export_button = QPushButton("Export Preview Image")
        self.export_button.clicked.connect(self.export_preview)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
        # Generate the preview
        self.generate_preview()
        
    def generate_preview(self):
        """Generate the preview visualization."""
        if not self.contour_layer or not self.region_rect or not self.scale or not self.paper_width or not self.paper_height:
            self.info_label.setText("Error: Missing required parameters for preview")
            return
        
        try:
            # Clear the scene
            self.scene.clear()
            
            # Set scene size based on paper dimensions (scaled for screen)
            # 1 mm = 4 pixels for display
            px_scale = 4
            scene_width = self.paper_width * px_scale
            scene_height = self.paper_height * px_scale
            self.scene.setSceneRect(0, 0, scene_width, scene_height)
            
            # Add paper background
            paper_rect = QRectF(0, 0, scene_width, scene_height)
            self.scene.addRect(paper_rect, QPen(Qt.black), QBrush(Qt.white))
            
            # Add margin indicator (5% of paper)
            margin = min(scene_width, scene_height) * 0.05
            margin_rect = QRectF(margin, margin, scene_width - 2*margin, scene_height - 2*margin)
            self.scene.addRect(margin_rect, QPen(QColor(200, 200, 200, 100)))
            
            # Transform from map coordinates to paper coordinates
            # First ensure we have the region rectangle in the contour layer's CRS
            if self.region_crs.authid() != self.contour_layer.crs().authid():
                transform = QgsCoordinateTransform(
                    self.region_crs,
                    self.contour_layer.crs(),
                    QgsProject.instance()
                )
                region_rect_transformed = transform.transformBoundingBox(self.region_rect)
            else:
                region_rect_transformed = self.region_rect
            
            # Calculate transformation parameters
            map_width = region_rect_transformed.width()
            map_height = region_rect_transformed.height()
            
            # Calculate the scale factor to fit the map to the paper with margins
            available_width = scene_width - 2*margin
            available_height = scene_height - 2*margin
            
            scale_x = available_width / map_width if map_width > 0 else 1
            scale_y = available_height / map_height if map_height > 0 else 1
            
            # Use the minimum scale to ensure the entire map fits
            scale_factor = min(scale_x, scale_y)
            
            # Use our new function to remap contours to the rectangle
            try:
                remapped_contours = remap_contours_to_rect(self.contour_layer, region_rect_transformed, self.region_crs)
                
                # Set up colors for different elevations
                colors = [QColor(50, 205, 50), QColor(222, 184, 135), QColor(160, 160, 160)]
                
                # Draw each remapped contour
                for elevation, geom in remapped_contours:
                    # Determine color based on elevation
                    color_idx = int(elevation / 100) % len(colors)
                    pen = QPen(colors[color_idx])
                    pen.setWidth(1)
                    
                    # Process based on geometry type
                    if geom.wkbType() == QgsWkbTypes.LineString:
                        points = []
                        for point in geom.asPolyline():
                            # Transform map coordinates to scene coordinates
                            scene_x = margin + (point.x() - region_rect_transformed.xMinimum()) * scale_factor
                            scene_y = margin + (point.y() - region_rect_transformed.yMinimum()) * scale_factor
                            points.append(QPointF(scene_x, scene_y))
                        
                        if len(points) >= 2:
                            polygon = QPolygonF(points)
                            self.scene.addPolygon(polygon, pen)
                            
                    elif geom.wkbType() == QgsWkbTypes.MultiLineString:
                        for part in geom.asMultiPolyline():
                            points = []
                            for point in part:
                                # Transform map coordinates to scene coordinates
                                scene_x = margin + (point.x() - region_rect_transformed.xMinimum()) * scale_factor
                                scene_y = margin + (point.y() - region_rect_transformed.yMinimum()) * scale_factor
                                points.append(QPointF(scene_x, scene_y))
                            
                            if len(points) >= 2:
                                polygon = QPolygonF(points)
                                self.scene.addPolygon(polygon, pen)
            
            except Exception as contour_e:
                self.info_label.setText(f"Error processing contours: {str(contour_e)}")
            
            # Add scale text
            scale_text = f"Scale 1:{self.scale}"
            scale_label = self.scene.addText(scale_text)
            scale_label.setPos(margin, scene_height - margin - scale_label.boundingRect().height())
            scale_label.setFont(QFont("Arial", 12))
            
            # Add north arrow
            arrow_size = min(scene_width, scene_height) * 0.1
            arrow_x = scene_width - margin - arrow_size
            arrow_y = margin
            
            # Draw North arrow
            north_arrow = [
                QPointF(arrow_x + arrow_size/2, arrow_y),  # Top
                QPointF(arrow_x, arrow_y + arrow_size),    # Bottom left
                QPointF(arrow_x + arrow_size/2, arrow_y + arrow_size*0.7),  # Middle point
                QPointF(arrow_x + arrow_size, arrow_y + arrow_size)  # Bottom right
            ]
            # Convert list to QPolygonF for the north arrow too
            north_arrow_polygon = QPolygonF(north_arrow)
            self.scene.addPolygon(north_arrow_polygon, QPen(Qt.black), QBrush(Qt.lightGray))
            
            # Add "N" label
            n_label = self.scene.addText("N")
            n_label.setPos(arrow_x + arrow_size/2 - n_label.boundingRect().width()/2, 
                            arrow_y + arrow_size + 5)
            n_label.setFont(QFont("Arial", 12, QFont.Bold))
            
            # Update info label
            self.info_label.setText(
                f"Preview of terrain model at 1:{self.scale} scale | "
                f"Paper: {self.paper_width}mm x {self.paper_height}mm | "
                f"Region: {map_width:.2f}m x {map_height:.2f}m"
            )
            
        except Exception as e:
            import traceback
            self.info_label.setText(f"Error generating preview: {str(e)}\n{traceback.format_exc()}")
    
    def export_preview(self):
        """Export the preview as an image file."""
        # Create a pixmap from the scene
        pixmap = QPixmap(self.scene.sceneRect().size().toSize())
        pixmap.fill(Qt.white)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self.scene.render(painter)
        painter.end()
        
        # Get a temporary file path for the image
        temp_dir = tempfile.gettempdir()
        image_path = os.path.join(temp_dir, "terrain_model_preview.png")
        
        # Save the pixmap
        saved = pixmap.save(image_path, "PNG")
        if saved:
            self.info_label.setText(f"Preview saved to: {image_path}")
        else:
            self.info_label.setText("Failed to save preview image")

def create_preview(parent, contour_layer, region_rect, region_crs, scale, paper_width, paper_height):
    """
    Create and show a preview dialog.
    
    :param parent: Parent widget
    :param contour_layer: The contour layer to preview
    :param region_rect: The selected region rectangle
    :param region_crs: The CRS of the region rectangle
    :param scale: The model scale (1:x)
    :param paper_width: Paper width in mm
    :param paper_height: Paper height in mm
    """
    dialog = PreviewDialog(parent, contour_layer, region_rect, region_crs, scale, paper_width, paper_height)
    dialog.exec_() 