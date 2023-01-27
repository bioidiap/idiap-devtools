.. Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
..
.. SPDX-License-Identifier: BSD-3-Clause

.. _devtools.install:

==============
 Installation
==============

First install mamba_ (conda).  Then, in its ``base`` environment, install this
package using one of the methods below:


.. tab:: mamba/conda

   .. code-block:: sh

      mamba install -n base -c https://www.idiap.ch/software/bob/conda/label/beta -c conda-forge devtools


.. tab:: pip

   .. warning:

      While this is possible for testing purposes, it is not recommended.
      Pip-installing this package may break your ``base`` conda environment.

   .. code-block:: sh

      conda activate base && pip install git+https://gitlab.idiap.ch/bob/devtools


.. _devtools.install.setup:

Setup
-----

.. _devtools.install.setup.profile:

Setting up Development Profiles
===============================

Development profiles contain a set of constants that are useful for developing,
and interacting with projects from a particular GitLab group, or groups.  They
may contain webserver addresses, and both Python and conda installation
constraints (package pinnings).  Development profiles are GitLab repositories,
organized in a specific way, and potentially used by various development,
continuous integration, and administrative tools.  Some examples:

* Bob's group: https://gitlab.idiap.ch/bob/dev-profile

While developing using the command-line utility ``devtool``, one or more
commands may require you pass the base directory of a development profile.

You may set a number of development shortcuts by configuring the section
``[profiles]`` on the file ``~/.config/devtools.toml``, like so:

.. code-block:: toml

   [profiles]
   default = "bob"
   bob = "~/dev-profiles/bob"
   custom = "~/dev-profiles/custom-profile"

.. note::

   The location of the configuration file respects ``${XDG_CONFIG_HOME}``,
   which defaults to ``~/.config`` in typical UNIX-style operating systems.

The special ``default`` entry refers to one of the other entries in this
section, and determines the default profile to use, if none is passed on the
command-line.  All other entries match name to a local directory where the
profile is available.

Development profiles are typically shared via GitLab as independent
repositories.  In this case, **it is your job to clone and ensure the profile
is kept up-to-date with your group's development requirements.**


.. _devtools.install.setup.gitlab:

Automated GitLab interaction
============================

Some of the commands in the ``devtool`` command-line application require access
to your GitLab private token, which you can pass at every iteration, or setup
at your ``~/.python-gitlab.cfg``.  Please note that in case you don't set it
up, it will request for your API token on-the-fly, what can be cumbersome and
repeatitive.  Your ``~/.python-gitlab.cfg`` should roughly look like this
(there must be an "idiap" section on it, at least):

.. code-block:: ini

   [global]
   default = idiap
   ssl_verify = true
   timeout = 15

   [idiap]
   url = https://gitlab.idiap.ch
   private_token = <obtain token at your settings page in gitlab>
   api_version = 4


We recommend you set ``chmod 600`` to this file to avoid prying eyes to read
out your personal token. Once you have your token set up, communication should
work transparently between the built-in GitLab client and the server.

.. include:: links.rst
