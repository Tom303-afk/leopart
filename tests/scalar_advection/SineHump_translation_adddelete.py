# __author__ = 'Jakob Maljaars <j.m.maljaars@tudelft.nl>'
# __date__   = '2018-08'
# __copyright__ = 'Copyright (C) 2011' + __author__
# __license__  = 'GNU Lesser GPL version 3 or any later version'

"""
    Tests the advection of a sinusoidal pulse
    psi(x,0) = sin{2 pi x} sin{2 pi y}
    on a bi-periodic unit square domain, using the
    simple translational velocity field u = [1,1]^T
    Particles are placed in a regular lattice, and
    an explicit control on the number of particles
    is used.
"""

from dolfin import (RectangleMesh, FunctionSpace, VectorFunctionSpace,
                    Function, SubDomain, Expression, Constant,
                    Point, FiniteElement, CellType,
                    near, assemble, dx, dot, sqrt, assign, File,
                    Timer)
from DolfinParticles import (particles, advect_particles, PDEStaticCondensation,
                             RegularRectangle, FormsPDEMap, SineHump, AddDelete)
from mpi4py import MPI as pyMPI
import numpy as np
import os

comm = pyMPI.COMM_WORLD


# Helper classes
class PeriodicBoundary(SubDomain):
    # Left boundary is "target domain" G
    def __init__(self, bdict):
        SubDomain.__init__(self)
        self.xmin, self.xmax = bdict['xmin'], bdict['xmax']
        self.ymin, self.ymax = bdict['ymin'], bdict['ymax']

    def inside(self, x, on_boundary):
        # return True if on left or bottom boundary AND NOT
        # on one of the two corners (0, 1) and (1, 0)
        return bool((near(x[0], self.xmin) or near(x[1], self.ymin)) and
                    (not ((near(x[0], self.xmin) and near(x[1], self.ymax)) or
                          (near(x[0], self.xmax) and near(x[1], self.ymin))))
                    and on_boundary)

    def map(self, x, y):
        if near(x[0], self.xmax) and near(x[1], self.ymax):
            y[0] = x[0] - (self.xmax - self.xmin)
            y[1] = x[1] - (self.ymax - self.ymin)
        elif near(x[0], self.xmax):
            y[0] = x[0] - (self.xmax - self.xmin)
            y[1] = x[1]
        else:   # near(x[1], 1)
            y[0] = x[0]
            y[1] = x[1] - (self.ymax - self.ymin)


# Mesh properties
xmin, ymin = 0., 0.
xmax, ymax = 1., 1.
nx_list = [8, 16, 32, 64, 128]

lims = np.array([[xmin, xmin, ymin, ymax], [xmax, xmax, ymin, ymax],
                 [xmin, xmax, ymin, ymin], [xmin, xmax, ymax, ymax]])
lim_dict = {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}

# Particle resolution, just 2 particles per cell
pres_list = [15 * pow(2, i) for i in range(len(nx_list))]

# Polynomial orders: k_list --> state variable, l_list --> Lagrange multiplier
k_list = [1, 2, 3]
l_list = [0] * len(k_list)
kbar_list = k_list

# Translatory velocity
ux, vy = '1', '1'

# Timestepping info
Tend = 1.
dt_list = [Constant(0.1/pow(2, i)) for i in range(len(nx_list))]
storestep_list = [5 * pow(2, i) for i in range(len(dt_list))]

# Directory for output
outdir_base = './../../results/PeriodicPulse_Translation_adddelete/'

# Then start the loop over the tests set-ups
for i, (k, l, kbar) in enumerate(zip(k_list, l_list, kbar_list)):
    # Set information for output
    outdir = outdir_base+'k'+str(k)+'l'+str(l)+'kbar'+str(kbar)+'_nprocs'+str(comm.Get_size())+'/'
    output_table = outdir+'output_table.txt'

    if comm.rank == 0:
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        with open(output_table, "w") as write_file:
            write_file.write("%-12s %-15s %-20s %-10s %-20s %-20s \n" %
                             ("Time step", "Number of cells", "Number of particles",
                              "L2 error", "Global mass error", "Wall clock time"))

    for (nx, dt, pres, store_step) in zip(nx_list, dt_list, pres_list, storestep_list):
        if comm.Get_rank() == 0:
            print("Starting computation with grid resolution "+str(nx))

        output_field = File(outdir+'psi_h'+'_nx'+str(nx)+'.pvd')

        # Compute num steps till completion
        num_steps = np.rint(Tend/float(dt))

        # Generate mesh
        mesh = RectangleMesh.create([Point(xmin, ymin), Point(xmax, ymax)], [nx, nx],
                                    CellType.Type.triangle)

        # Velocity and initial condition
        V = VectorFunctionSpace(mesh, 'CG', 1)
        uh = Function(V)
        uh.assign(Expression((ux, vy), degree=1))

        psi0_expression = SineHump(center=[0.5, 0.5], U=[float(ux), float(vy)],
                                   time=0., degree=6)

        # Generate particles
        if comm.Get_rank() == 0:
            x = RegularRectangle(Point(xmin, ymin), Point(xmax, ymax)).generate([pres, pres])
            s = np.zeros(len(x), dtype=np.float_)
        else:
            x = None
            s = None

        x = comm.bcast(x, root=0)
        s = comm.bcast(s, root=0)

        # Initialize particles with position x and scalar property s at the mesh
        p = particles(x, [s], mesh)
        property_idx = 1  # Scalar quantity is stored at slot 1

        # Initialize advection class, simple forward Euler suffices
        ap = advect_particles(p, V, uh, 'periodic', lims.flatten(), 'none')

        # Define the variational (projection problem)
        W_e = FiniteElement("DG", mesh.ufl_cell(), k)
        T_e = FiniteElement("DG", mesh.ufl_cell(), 0)
        Wbar_e = FiniteElement("DGT", mesh.ufl_cell(), k)

        W = FunctionSpace(mesh, W_e)
        T = FunctionSpace(mesh, T_e)
        Wbar = FunctionSpace(mesh, Wbar_e, constrained_domain=PeriodicBoundary(lim_dict))

        psi_h, psi0_h = Function(W), Function(W)
        lambda_h = Function(T)
        psibar_h = Function(Wbar)

        # Initialize forms
        FuncSpace_adv = {'FuncSpace_local': W, 'FuncSpace_lambda': T, 'FuncSpace_bar': Wbar}
        forms_pde = FormsPDEMap(mesh, FuncSpace_adv).forms_theta_linear(psi0_h, uh,
                                                                        dt, Constant(1.0))
        pde_projection = PDEStaticCondensation(mesh, p,
                                               forms_pde['N_a'], forms_pde['G_a'], forms_pde['L_a'],
                                               forms_pde['H_a'],
                                               forms_pde['B_a'],
                                               forms_pde['Q_a'], forms_pde['R_a'], forms_pde['S_a'],
                                               [], property_idx)

        # Set initial condition at mesh and particles
        psi0_h.interpolate(psi0_expression)
        p.interpolate(psi0_h.cpp_object(), property_idx)

        # Add/Delete particles
        AD = AddDelete(p, 10, 20, [psi0_h])

        step = 0
        area_0 = assemble(psi0_h*dx)
        timer = Timer()

        timer.start()
        while step < num_steps:
            step += 1

            # Add/delete particles, must be done before advection!
            AD.do_sweep()
            # Advect particle, assemble and solve pde projection
            ap.do_step(float(dt))

            pde_projection.assemble(True, True)
            pde_projection.solve_problem(psibar_h.cpp_object(), psi_h.cpp_object(),
                                         'gmres', 'hypre_amg')
            # Update old solution
            assign(psi0_h, psi_h)

            # Store
            # if step % store_step is 0 or step is 1:
            output_field << psi_h

        timer.stop()

        # Compute error (we should accurately recover initial condition)
        l2_error = sqrt(abs(assemble(dot(psi_h - psi0_expression, psi_h - psi0_expression)*dx)))

        # The global mass conservation error should be zero
        area_end = assemble(psi_h*dx)

        if comm.Get_rank() == 0:
            print("l2 error "+str(l2_error))

            # Store in error error table
            num_cells_t = mesh.num_entities_global(2)
            num_particles = len(x)
            area_error_end = np.float64((area_end-area_0))
            with open(output_table, "a") as write_file:
                write_file.write("%-12.5g %-15d %-20d %-10.2e %-20.3g %-20.3g \n" %
                                 (float(dt), int(num_cells_t), int(num_particles),
                                  float(l2_error), np.float64(area_error_end),
                                  np.float(timer.elapsed()[0])))
