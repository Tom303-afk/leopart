// Author: Jakob Maljaars
// Contact: j.m.maljaars _at_ tudelft.nl/jakobmaljaars _at_ gmail.com
// Copyright: (c) 2018
// License: GNU Lesser GPL version 3 or any later version

#ifndef PARTICLES_H
#define PARTICLES_H

#include "utils.h"
#include "particle.h"
#include <iostream>
#include <vector>
#include <limits>
#include <dolfin/mesh/Mesh.h>
#include <dolfin/mesh/Cell.h>
#include <dolfin/geometry/BoundingBoxTree.h>
#include <dolfin/function/Function.h>
#include <dolfin/function/FunctionSpace.h>

#include <dolfin/fem/FiniteElement.h>
#include <Eigen/Dense>

namespace dolfin
{
  class particles
  {

  public:
    particles(Eigen::Ref<const Eigen::Array<double,
              Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor>> p_array,
              const std::vector<unsigned int>& p_template,
              const Mesh& mesh);

    ~particles();

    // Get the particle object in this cell
    particle get_particle(int cell_index, int particle_index) const
    { return _cell2part[cell_index][particle_index]; }

    // Get the position of a particle in a cell
    // Just a shorthand for "property(cidx, pidx, 0)"
    const Point& x(int cell_index, int particle_index) const
    { return _cell2part[cell_index][particle_index][0]; }

    // Return property i of particle in cell
    const Point& property(int cell_index, int particle_index,
                          int i) const
    { return _cell2part[cell_index][particle_index][i]; }

    unsigned int expand_template(int dim)
    {
      // Add new template item and initialise all particles with extra
      // empty slot
      _ptemplate.push_back(dim);
      _plen += dim;
      Point p(0.0, 0.0, 0.0);
      for (unsigned int cidx = 0; cidx < _mesh->num_cells(); ++cidx)
        for (unsigned int pidx = 0; pidx < num_cell_particles(cidx); ++pidx)
          _cell2part[cidx][pidx].push_back(p);
      return _ptemplate.size() - 1;
    }

    void set_property(int cell_index, int particle_index, int i, Point v)
    { _cell2part[cell_index][particle_index][i] = v; }

    // Pointer to the mesh
    const Mesh* mesh() const
    { return _mesh; }

    // Get size of property i
    unsigned int ptemplate(int i) const
    { return _ptemplate[i]; }

    // Number of properties
    unsigned int num_properties() const
    { return _ptemplate.size(); }

    // Number of particles in Cell c
    unsigned int num_cell_particles(int c) const
    { return _cell2part[c].size(); }

    // Add particle to cell
    void add_particle(int c, particle p)
    { _cell2part[c].push_back(p); }

    // Remove ith particle from cell c
    void delete_particle(int c, int i)
    {
      _cell2part[c].erase(_cell2part[c].begin() + i);
    }

    // Interpolate function to particles
    void interpolate(const Function& phih, const std::size_t property_idx);

    // Increment
    void increment(const Function& phih_new, const Function& phih_old, const std::size_t property_idx);

    // Increment using theta --> Consider replacing property_idcs
    void increment(const Function& phih_new, const Function& phih_old,
                       Eigen::Ref<const Eigen::Array<std::size_t, Eigen::Dynamic, 1>> property_idcs,
                       const double theta, const std::size_t step);

    Eigen::Array<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor>
      positions();
    std::vector<double> get_property(const std::size_t idx);

    void get_particle_contributions(Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor>& q,
                                    Eigen::Matrix<double, Eigen::Dynamic, 1>& f,
                                    const Cell& dolfin_cell, std::shared_ptr<const FiniteElement> element,
                                    const std::size_t space_dimension, const std::size_t value_size_loc,
                                    const std::size_t property_idx);

    // Push particle to new position
    void push_particle(const double dt, const Point& up, const std::size_t cidx, const std::size_t pidx);

    // Particle collector, required in parallel
    void particle_communicator_collect(const std::size_t cidx, const std::size_t pidx);

    // Particle pusher, required in parallel
    void particle_communicator_push();

  private:

      std::vector<std::vector<particle>> _comm_snd;

      // Initialize bounding boxes
      void make_bounding_boxes();

      // Update bounding boxes (on moving mesh)
      void update_bounding_boxes();

      // Check if point in bounding box
      static bool in_bounding_box(const std::vector<double>& point,
                                  const std::vector<double>& bounding_box,
                                  const double tol);

      std::vector<double> unpack_particle(const particle part);

      // TODO: locate/relocate funcionality

      // Attributes
      const Mesh* _mesh;
      std::size_t _Ndim;
      std::vector<std::vector<particle> >  _cell2part;

      // Particle properties
      std::vector<unsigned int> _ptemplate;
      std::size_t _plen;

      // Needed for parallel
      const MPI_Comm _mpi_comm;
      std::vector<std::vector<double>> _bounding_boxes;

  };
}

#endif // PARTICLES_H
