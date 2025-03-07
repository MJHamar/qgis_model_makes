# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TerrainModelMaker
                                 A QGIS plugin
 Create laser-cuttable terrain models from contour data
                             -------------------
        begin                : 2023-03-07
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

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load TerrainModelMaker class from file terrain_model_maker.py.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .terrain_model_maker import TerrainModelMaker
    return TerrainModelMaker(iface) 