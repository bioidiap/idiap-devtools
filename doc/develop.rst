.. Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
..
.. SPDX-License-Identifier: BSD-3-Clause

.. _idiap-devtools.develop:

===============================
 Local development of packages
===============================

We recommend you create isolated virtual environments using mamba_ (conda_) to
develop existing or new projects, then pip_ install development requirements
over that mamba_ environment.  We offer guidance of two variants for installing
dependencies: one exclusively using Python packages, and a second which
installs most dependencies as conda_ packages (being able to better handle
non-Python dependencies such as Nvidia CUDA-compiled packages).  In both cases,
the top-level package (or packages) is (are) always installed on the
development environment through pip_ (with `the --editable option <pip-e_>`_).

.. note::

   Pip_ may be configured with command-line options as shown below, but equally
   through environment variables, or `configuration files <pip-config_>`_.  We
   leave to the developer's discretion the decision on how to best manage their
   own use of pip_.


.. note::

   You may develop software against different development (c.f.
   :ref:`idiap-devtools.install.setup.profile`).  In the context of these
   instructions, we assume your development profile is located at
   ``../profile``.


.. tip::

   Please refer :ref:`idiap-devtools.install.running` for details on how to
   setup the ``mamba-run-on`` shell function to simplify the various
   commands below. If you decide to skip this, remember to properly activate
   and deactivate the environments everytime.


.. tab:: pip

   In this variant, the latest (beta) versions of internally developed
   dependencies are fetched from our local package registry if applicable.
   Furthermore, external dependencies are fetched from PyPI and respect
   versions used on the continuous integration (CI) server.  It is useful to
   reproduce bugs reported on the CI, during test builds:

   .. code:: sh

      $ git clone <PACKAGE-URL>  # e.g. git clone git@gitlab.idiap.ch/software/clapp
      $ cd <PACKAGE>  # e.g. cd clapp
      $ mamba-run-on base mamba create -n dev python=3.10 pip
      $ mamba-run-on dev pip install --pre --index-url https://token:<YOUR-GITLAB-TOKEN>@gitlab.idiap.ch/api/v4/groups/software/-/packages/pypi/simple --extra-index-url https://pypi.org/simple --constraint ../profile/python/pip-constraints.txt --editable '.[qa,doc,test]'
      $ conda activate dev
      (dev) $ # `dev` environment is now ready, just develop

   .. note::

      If you need to install *private* packages developed through GitLab, you
      must `generate a personal token <gitlab-token_>`_ with at least access to
      the package registry (currently implemented through the ``read_api``
      privilege).

      Otherwise, you may suppress ``token:<YOUR-GITLAB-TOKEN>@`` from the
      index-url option above.

   .. tip::

      Optionally, you may create a standard Python virtual environment (instead of
      a conda_ virtual environment) with either venv_ or virtualenv_, and then
      apply the same instructions above to locally install dependencies and the
      package itself.

      The Python version in this case will match that used to create the virtual
      environment.


.. tab:: conda

   In this variant, the latest (beta) versions of internally developed
   dependencies are fetched from our local conda (beta) package registry, if
   applicable. Furthermore, external dependencies are fetched from conda-forge_
   and respect versions used on the continuous integration (CI) server.  It is
   useful to reproduce bugs reported on the CI, during conda-package test
   builds, or to install further non-Python dependencies required for package
   development (e.g. Nvidia CUDA-enabled packages):

   .. code:: sh

      $ git clone <PACKAGE>
      $ cd <PACKAGE>
      $ mamba-run-on idiap-devtools devtool env -vv .
      $ mamba-run-on base mamba env create -n dev -f environment.yaml
      $ mamba-run-on dev pip install --no-build-isolation --no-dependencies --editable .
      $ conda activate dev
      (dev) $ # `dev` environment is now ready, just develop

   .. note::

       The application ``devtool env`` uses the ``conda`` API to parse your
       package's recipe (typically at ``conda/meta.yaml``) and
       ``pyproject.toml``, and then to search dependencies (including those for
       quality-assurance, documentation and tests, which may be not listed on
       ``conda/meta.yaml``).  The installation respects CI constraints
       established on your chosen profile.


After that step, your package will be installed and ready for use inside the
``dev`` environment.  You must activate the virtual environment everytime you
want to further develop the package, or simply deactivate it when you branch
off to another activity.

With the development environment active, you can optionally test the package
installation by either building its Sphinx documentation, doctests, running its
test suite, or the quality assurance (pre-commit) checks:

.. code:: sh

   $ conda activate dev
   (dev) $ pre-commit run --all-files  # quality assurance
   (dev) $ pytest -sv tests/ # test units
   (dev) $ sphinx-build doc sphinx  # documentation
   (dev) $ sphinx-build doctest doc sphinx  # doctests


Developing multiple existing packages simultaneously
----------------------------------------------------

It may happen that you may want to develop several packages against each other
for your project.  This is the case if you are changing a high-level package
``package-a``, that in turn depends on functionality on ``package-b`` you may
also need to adapt.  While you change ``package-b``, you want to verify how
these changes work on ``package-a``.  The procedure to accomodate this is
similar to the above, except you will git-clone and pip-install more packages:


.. tab:: pip

   In this variant, the latest (beta) versions of internally developed
   dependencies are fetched from our local package registry if applicable.
   Furthermore, external dependencies are fetched from PyPI and respect
   versions used on the continuous integration (CI) server.

   To setup your environment, you must install packages in reverse dependence
   order, with the top-level package (``package-a`` in this example), being
   installed **by last**.

   .. code:: sh

      $ git clone <PACKAGE-A>
      $ cd <PACKAGE-A>
      $ git clone <PACKAGE-B> src/<PACKAGE-B>
      $ mamba-run-on base mamba create -n dev python=3.10 pip
      # get the constraints for the "target" development environment.
      # this is just an example:
      $ curl -O constraints.txt https://gitlab.idiap.ch/software/dev-profile/-/raw/main/python/pip-constraints.txt
      $ conda activate dev
      (dev) $ for pkg in "src/package-b" "."; do pip install --pre --index-url https://token:<YOUR-GITLAB-TOKEN>@gitlab.idiap.ch/api/v4/groups/software/-/packages/pypi/simple --extra-index-url https://pypi.org/simple --constraint constraints.txt --editable "${pkg}[qa,doc,test]"; done
      (dev) $ # `dev` environment is now ready, just develop


.. tab:: conda

   In this variant, the latest (beta) versions of internally developed
   dependencies are fetched from our local conda (beta) package registry, if
   applicable. Furthermore, external dependencies are fetched from conda-forge_
   and respect versions used on the continuous integration (CI) server.  It is
   useful to reproduce bugs reported on the CI, during conda-package test
   builds:

   .. code:: sh

      $ git clone <PACKAGE-A>
      $ cd <PACKAGE-A>
      $ git clone <PACKAGE-B> src/<PACKAGE-B>
      $ mamba-run-on idiap-devtools devtool env -vv src/package-b .
      $ mamba-run-on base mamba env create -n dev -f environment.yaml
      $ conda activate dev
      (dev) $ for pkg in "src/package-b" "."; do pip install --no-build-isolation --no-dependencies --editable "${pkg}"
      (dev) $ # `dev` environment is now ready, just develop


Installing all constrained packages
-----------------------------------

If you plan to develop many packages together, it may be faster to first
pre-install all (constrained) packages, to then pip-install all the individual
packages. Because the mamba_ (or conda_) ecosystem is a superset of Python
packages, we only provide this option:


.. code:: sh

   $ mamba-run-on idiap-devtools devtool fullenv -vv
   $ mamba-run-on base mamba env create -n dev -f environment.yaml
   $ conda activate dev
   (dev) $ for pkg in "src/*"; do pip install --no-build-isolation --no-dependencies --editable "${pkg}"


Creating new packages
---------------------

To create a new package, use our `cookiecutter template
<cookiecutter-template_>`_ and associated instructions.  Do **not** copy
another package source code, or no Xmas gifts for you...


.. include:: links.rst
