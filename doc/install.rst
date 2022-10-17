.. _devtools.install:

==============
 Installation
==============

.. todo:: fine-tune installation instructions for devtools here


We support two installation modes, through pip_, or mamba_ (conda).


With pip
--------

.. code-block:: sh

   # stable, from PyPI:
   $ pip install devtools

   # latest beta, from GitLab package registry:
   $ pip install --pre --index-url https://gitlab.idiap.ch/api/v4/groups/bob/-/packages/pypi/simple --extra-index-url https://pypi.org/simple devtools

.. tip::

   To avoid long command-lines you may configure pip to define the indexes and
   package search priorities as you like.


With conda
----------

.. code-block:: sh

   # stable:
   $ mamba install -c https://www.idiap.ch/software/bob/conda -c conda-forge devtools

   # latest beta:
   $ mamba install -c https://www.idiap.ch/software/bob/conda/label/beta -c conda-forge devtools


.. include:: links.rst
