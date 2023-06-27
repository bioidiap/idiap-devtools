.. Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
..
.. SPDX-License-Identifier: BSD-3-Clause

.. _idiap-devtools.install:

==============
 Installation
==============

First install mamba_ or conda (preferably via mambaforge_, as it is already
setup to use conda-forge_ as its main distribution channel).  Then, create a
new environment, containing this package:


.. tab:: mamba/conda (RECOMMENDED)

   .. code-block:: sh

      # installs the latest release on conda-forge:
      mamba create -n idiap-devtools idiap-devtools

      # OR, installs the latest development code:
      mamba create -n idiap-devtools -c https://www.idiap.ch/software/biosignal/conda/label/beta idiap-devtools


.. tab:: pip

   .. warning::

      While this is possible for testing purposes, it is **not recommended**,
      as this package depends on conda/mamba for some of its functionality.  If
      you decide to do so, create a new conda/mamba environment, and
      pip-install this package on it.

   .. code-block:: sh

      # creates the new environment
      mamba create -n idiap-devtools python=3 pip conda mamba conda-build boa
      conda activate idiap-devtools

      # installs the latest release on PyPI:
      pip install idiap-devtools

      # OR, installs the latest development code:
      pip install git+https://gitlab.idiap.ch/software/idiap-devtools


.. _idiap-devtools.install.running:

Running
-------

This package contains a single command-line executable named ``devtool``, which
in turn contains subcommands with various actions.  To run the main
command-line tool, you must first activate the environment where it is
installed in, and then call it on the command-line:

.. code-block:: sh

   conda activate idiap-devtools
   devtool --help
   conda deactivate  # to go back to the previous state


It is possible to use the command ``conda run`` to, instead, automatically
prefix the execution of ``devtool`` with an environment activation, and follow
it with a deactivation.  This allows to compact the above form into a
"one-liner":

.. code-block:: sh

   mamba --no-banner run -n idiap-devtools --no-capture-output --live-stream devtool --help


.. tip::

   If you use a POSIX shell, such as bash or zsh, you can add a function to your
   environment, so that the above command-line becomes easier to access:

   .. code-block:: sh

      # Runs a command on a prefixed environment, if the environment is not the
      # the current one.  Otherwise, just runs the command itself.
      # argument 1: the conda environment name where the program exists
      # other arguments: program and arguments to be executed at the prefixed
      # conda environment
      function mamba-run-on {
          # if the environment is set, then just run the command
          if [[ "${CONDA_DEFAULT_ENV}" == "${1}" ]]; then
              "${@:2}"
          else
              mamba --no-banner run -n ${1} --no-capture-output --live-stream "${@:2}"
          fi
      }

    You can use it like this:

    .. code-block:: sh

       mamba-run-on idiap-devtools devtool --help
       alias devtool="mamba-run-on idiap-devtools devtool"


.. warning::

   The ``devtool`` application requires that ``mamba``/``conda`` are available
   on the environment it executes.  When using ``mamba``/``conda`` to create
   new environments, ensure you are using the ones from the ``base``
   environment.  Creating new environments as sub-environments of the
   ``idiap-devtools`` environment may have surprising effects.  To this end, we
   advise you create a second alias that ensures ``mamba`` is always executed
   from the ``base`` environment:

    .. code-block:: sh

       alias mamba="mamba-run-on base mamba"


.. _idiap-devtools.install.setup:

Setup
-----

.. _idiap-devtools.install.setup.profile:

Setting up Development Profiles
===============================

Development profiles contain a set of constants that are useful for developing,
and interacting with projects from a particular GitLab group, or groups.  They
may contain webserver addresses, and both Python and conda installation
constraints (package pinnings).  Development profiles are GitLab repositories,
organized in a specific way, and potentially used by various development,
continuous integration, and administrative tools.  Some examples:

* Software's group: https://gitlab.idiap.ch/software/dev-profile
* Biosignal's group: https://gitlab.idiap.ch/biosignal/software/dev-profile
* Bob's group: https://gitlab.idiap.ch/bob/dev-profile

While developing using the command-line utility ``devtool``, one or more
commands may require you pass the base directory of a development profile.

You may set a number of development shortcuts by configuring the section
``[profiles]`` on the file ``~/.config/idiap-devtools.toml``, like so:

.. code-block:: toml

   [profiles]
   default = "software"
   software = "~/dev-profiles/software"
   biosignal = "~/dev-profiles/biosignal"
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


.. _idiap-devtools.install.setup.gitlab:

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
