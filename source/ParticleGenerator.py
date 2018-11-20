# __author__ = 'Jakob Maljaars <j.m.maljaars@tudelft.nl>'
# __date__   = '2018-08'
# __copyright__ = 'Copyright (C) 2011' + __author__
# __license__  = 'GNU Lesser GPL version 3 or any later version'

import numpy as np
from math import sqrt
from itertools import product
from mpi4py import MPI as pyMPI
from dolfin import cells, vertices

__all__ = ['RandomRectangle', 'RandomCircle', 'RandomBox', 'RandomSphere',
           'RegularRectangle', 'RegularBox']

comm = pyMPI.COMM_WORLD


'''
Classes for particle generation, either on regular lattice (RegularRectangle),
or randomly placed (RandomRectangle/RandomCircle)
'''


class RandomGenerator(object):

    '''
    Fill object by random points.
    '''

    def __init__(self, domain, rule):
        '''
        Domain specifies bounding box for the shape and is used to generate
        points. The rule filter points of inside the bounding box that are
        axctually inside the shape.
        '''
        assert isinstance(domain, list)
        self.domain = domain
        self.rule = rule
        self.dim = len(domain)
        self.rank = comm.Get_rank()

    def generate(self, N, method='full'):
        'Genererate points.'
        assert len(N) == self.dim
        assert method in ['full', 'tensor']
        np.random.seed(10)
        if self.rank == 0:
            # Generate random points for all coordinates
            if method == 'full':
                n_points = np.product(N)
                points = np.random.rand(n_points, self.dim)
                for i, (a, b) in enumerate(self.domain):
                    points[:, i] = a + points[:, i]*(b-a)
            # Create points by tensor product of intervals
            else:
                # Values from [0, 1) used to create points between
                # a, b - boundary
                # points in each of the directiosn
                shifts_i = np.array([np.random.rand(n) for n in N])
                # Create candidates for each directions
                points_i = (a+shifts_i[i]*(b-a)
                            for i, (a, b) in enumerate(self.domain))
                # Cartesian product of directions yield n-d points
                points = (np.array(point) for point in product(*points_i))

            # Use rule to see which points are inside
            points_inside = np.array(list(filter(self.rule, points)))
        else:
            points_inside = None

        return points_inside


class RandomRectangle(RandomGenerator):
    def __init__(self, ll, ur):
        # a is lower left, b is upper right
        ax, ay = ll.x(), ll.y()
        bx, by = ur.x(), ur.y()
        assert ax < bx and ay < by
        RandomGenerator.__init__(self, [[ax, bx], [ay, by]], lambda x: True)


class RandomCircle(RandomGenerator):
    def __init__(self, center, radius):
        assert radius > 0
        domain = [[center[0]-radius, center[0]+radius],
                  [center[1]-radius, center[1]+radius]]
        RandomGenerator.__init__(self, domain,
                                 lambda x: sqrt((x[0]-center[0])**2 +
                                                (x[1]-center[1])**2) < radius
                                 )


class RandomBox(RandomGenerator):
    def __init__(self, ll, ur):
        # a is lower left, b is upper right
        ax, ay, az = ll.x(), ll.y(), ll.z()
        bx, by, bz = ur.x(), ur.y(), ur.z()
        assert ax < bx and ay < by and az < bz
        domain = [[ax, bx], [ay, by], [az, bz]]
        RandomGenerator.__init__(self, domain, lambda x: True)


class RandomSphere(RandomGenerator):
    def __init__(self, center, radius):
        assert len(center) == 3
        assert radius > 0
        domain = [[center[0]-radius, center[0]+radius],
                  [center[1]-radius, center[1]+radius],
                  [center[2]-radius, center[2]+radius]]
        RandomGenerator.__init__(self, domain,
                                 lambda x: sqrt((x[0]-center[0])**2 +
                                                (x[1]-center[1])**2 +
                                                (x[2]-center[1])**2) < radius
                                 )


class RegularRectangle(RandomGenerator):
    def __init__(self, ll, ur):
        # ll is Point(lower left coordinate), ur is Point(upper right coordinate)
        ax, ay = ll.x(), ll.y()
        bx, by = ur.x(), ur.y()
        assert ax < bx and ay < by
        RandomGenerator.__init__(self, [[ax, bx], [ay, by]], lambda x: True)

    def generate(self, N, method='open'):
        'Genererate points.'
        assert len(N) == self.dim

        if self.rank == 0:
            if method == 'closed':
                endpoint = True
            elif method == 'half open':
                endpoint = False
            elif method == 'open':
                endpoint = True
                new_domain = []
                for i, (a, b) in enumerate(self.domain):
                    delta = 0.5 * (b-a)/float(N[i])
                    a += delta
                    b -= delta
                    new_domain.append([a, b])
                self.domain = new_domain
            else:
                raise Exception('Unknown particle placement method')
            coords = []
            for i, (a, b) in enumerate(self.domain):
                coords.append(np.linspace(a, b, N[i], endpoint=endpoint))

            X, Y = np.meshgrid(coords[0], coords[1])
            points = np.vstack((np.hstack(X), np.hstack(Y))).T
            assert np.product(N) == len(points)
            points_inside = np.array(list(filter(self.rule, points)))
        else:
            points_inside = None

        return points_inside


class RegularBox(RandomGenerator):
    def __init__(self, ll, ur):
        # a is lower left, b is upper right
        ax, ay, az = ll.x(), ll.y(), ll.z()
        bx, by, bz = ur.x(), ur.y(), ur.z()
        assert ax < bx and ay < by and az < bz
        domain = [[ax, bx], [ay, by], [az, bz]]
        RandomGenerator.__init__(self, domain, lambda x: True)

    def generate(self, N, method='open'):
        'Genererate points.'
        assert len(N) == self.dim
        if self.rank == 0:
            if method == 'closed':
                endpoint = True
            elif method == 'half open':
                endpoint = False
            elif method == 'open':
                endpoint = True
                new_domain = []
                for i, (a, b) in enumerate(self.domain):
                    delta = 0.5 * (b-a)/float(N[i])
                    a += delta
                    b -= delta
                    new_domain.append([a, b])
                self.domain = new_domain
            else:
                raise Exception('Unknown particle placement method')
            coords = []
            for i, (a, b) in enumerate(self.domain):
                coords.append(np.linspace(a, b, N[i], endpoint=endpoint))

            X, Y, Z = np.meshgrid(coords[0], coords[1], coords[2])
            # Unfold lists
            X_unf = np.hstack(np.hstack(X))
            Y_unf = np.hstack(np.hstack(Y))
            Z_unf = np.hstack(np.hstack(Z))
            points = np.vstack((X_unf, Y_unf, Z_unf)).T
            assert np.product(N) == len(points)
            points_inside = np.array(list(filter(self.rule, points)))
        else:
            points_inside = None

        return points_inside


class MeshGenerator(object):
    """Generate particles in an existing Mesh."""
    def __init__(self, mesh):
        self.mesh = mesh

    def _random_bary(self, n):
        """Generate random barycentric coordinates between n points."""
        if (n == 3):
            x = np.random.random()
            y = np.random.random()
            if (x + y) > 1.0:
                x, y = 1.0 - x, 1.0 - y
            z = 1.0 - x - y
            return (x, y, z)

        assert n == 4, "Only support triangle and tetrahedron"
        s = np.random.random()
        t = np.random.random()
        u = np.random.random()

        # Fold space in cube into tetrahedron
        if (s + t > 1.0):
            s, t = 1.0 - s, 1.0 - t
        if (t + u > 1.0):
            t, u = 1.0 - s - u,  1.0 - t
        elif (s + t + u > 1.0):
            u += s + t - 1.0
            s -= u

        v = 1 - s - t - u
        return (s, t, u, v)

    def generate(self, N):
        """Generate a random set of N points per cell."""

        # TODO - number of points per cell could be random too, with a minimum
        # value, and should be related to the cell volume.

        points_inside = []

        for c in cells(self.mesh):
            pts = [v.point().array() for v in vertices(c)]

            for i in range(N):
                x = self._random_bary(len(pts))
                points_inside += [a * b for (a, b) in zip(x, pts)]

        points_inside = np.array(points_inside)

        if (self.mesh.geometry().dim() == 2):
            points_inside = points_inside[:, :2]

        return points_inside
