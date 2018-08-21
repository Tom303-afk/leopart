# -*- coding: utf-8 -*-
import pygmsh

geom = pygmsh.built_in.Geometry()

geom.add_circle(
    [0.0, 0.0, 0.0],
    0.5,
    lcar=0.1,
    num_sections=4,
    # If compound==False, the section borders have to be points of the
    # discretization. If using a compound circle, they don't; gmsh can
    # choose by itself where to point the circle points.
    compound=True,
)


points, cells, _, _, _ = pygmsh.generate_mesh(geom)

import meshio
# Prune topology and save 2D
cells = {'triangle':cells['triangle']}
# points = points[:,:2]

meshio.write_points_cells("circle.xml", points, cells)
