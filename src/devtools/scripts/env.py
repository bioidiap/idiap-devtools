# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import sys
import typing

import click

from ..click import PreserveIndentCommand, validate_profile, verbosity_option
from ..logging import setup
from ..profile import Profile

logger = setup(__name__.split(".", 1)[0])


def _load_conda_packages(
    meta: list[str], conda_config: typing.Any
) -> tuple[list[str], list[str], list[str]]:
    """Loads dependence packages by scanning conda recipes.

    Input entries in ``meta`` may correspond to various types of entries, out
    of which, we will not ignore in this function:

        * A full path to a ``meta.yaml`` file that will be scanned
        * A project directory containing a conda recipe at ``conda/meta.yaml``
        * The name of a conda package to install (condition: does not contain a
          path separator nor exists as a file or directory in the filesystem)


    Arguments:

        meta: List of directories, conda recipes and conda package names to parse.

        conda_config: Profile-dependent conda configuration to use for
            determining packages to install and constraints.


    Returns:

        A list of non-consumed elements from the ``meta`` list, the list of
        parsed package names, and finally the list of dependencies from the
        parsed recipes.
    """

    import os

    from .. import conda, utils

    consumed = []
    parsed_packages = []
    conda_packages = []

    for m in meta:

        if m.endswith("meta.yaml"):
            # user has passed the full path to the file
            # we can consume this from the input list
            recipe_dir = os.path.dirname(m)
            logger.info(f"Parsing conda recipe at {recipe_dir}...")
            pkg_name, pkg_deps = conda.parse_dependencies(
                recipe_dir, conda_config
            )
            logger.info(
                f"Added {len(pkg_deps)} packages from package '{pkg_name}'"
            )
            parsed_packages.append(pkg_name)
            conda_packages += pkg_deps
            consumed.append(m)

        elif os.path.exists(os.path.join(m, "conda", "meta.yaml")):
            # it is the root of a project
            # may need to parse it for python packages later on
            recipe_dir = os.path.join(m, "conda")
            logger.info(f"Parsing conda recipe at {recipe_dir}...")
            pkg_name, pkg_deps = conda.parse_dependencies(
                recipe_dir, conda_config
            )
            logger.info(
                f"Added {len(pkg_deps)} packages from package '{pkg_name}'"
            )
            parsed_packages.append(pkg_name)
            conda_packages += pkg_deps

        elif not os.path.exists(m) and os.sep not in m:
            # it is a conda package name, add to list of packages to install
            # we can consume this from the input list
            logger.info(f"Adding conda package {m}...")
            conda_packages.append(m)
            consumed.append(m)

    meta = [k for k in meta if k not in consumed]

    # we should install all packages that have not been parsed yet
    conda_packages = [k for k in conda_packages if k not in parsed_packages]

    # now we sort and make it unique
    conda_packages = utils.uniq(sorted(conda_packages))

    logger.info(
        f"Adding {len(conda_packages)} conda packages to installation plan",
    )
    return meta, parsed_packages, conda_packages


def _load_python_packages(
    the_profile: Profile,
    python: str,
    meta: list[str],
    conda_pkgs: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Loads dependence packages by scanning Python recipes.

    Input entries in ``meta`` may correspond to various types of entries, out
    of which, we will not ignore in this function:

        * A full path to a ``pyproject.toml`` file that will be scanned
        * A project directory containing a Python project declaration at
          ``pyproject.toml``


    Arguments:

        the_profile: The current development profile, that will be looked up
          for conda-to-Python package name translations.

        python: The version of Python to load conda constraints for

        meta: List of directories, and Python project definitions to scan

        conda_pkgs: List of conda packages that either have been parsed, or
            are dependencies of parsed recipes.  We must **not** install Python
            equivalents for those.


    Returns:

        A list of non-consumed elements from the ``meta`` list, the list of
        pure-Python dependencies from the parsed recipes, that are not at
        ``conda_pkgs`` and have no conda equivalents, and finally, an extension
        to the list of conda packages that can be installed that way.
    """

    import os

    from .. import python as pyutils
    from .. import utils

    parsed_packages = [k.split(" ", 1)[0] for k in conda_pkgs]
    to_python = the_profile.get(("conda", "to_python"), {})
    parsed_packages = [to_python.get(k, k) for k in parsed_packages]

    consumed = []
    python_packages = []

    for m in meta:

        if m.endswith("pyproject.toml"):

            # user has passed the full path to the file
            # we can consume this from the input list
            logger.info(f"Parsing Python package at {m}...")
            pkg_name, pkg_deps = pyutils.dependencies_from_pyproject_toml(m)
            logger.info(
                f"Added {len(pkg_deps)} Python packages from package '{pkg_name}'",
            )
            parsed_packages.append(pkg_name)
            python_packages += pkg_deps
            consumed.append(m)

        elif os.path.exists(os.path.join(m, "pyproject.toml")):
            # it is the root of a project
            proj = os.path.join(m, "pyproject.toml")
            logger.info(f"Parsing Python package at {proj}...")
            pkg_name, pkg_deps = pyutils.dependencies_from_pyproject_toml(proj)
            logger.info(
                f"Added {len(pkg_deps)} Python packages from package '{pkg_name}'",
            )
            parsed_packages.append(pkg_name)
            python_packages += pkg_deps
            consumed.append(m)

    meta = [k for k in meta if k not in consumed]

    # if there are equivalent conda-pinned packages, we should prefer them
    # instead of pure-Python versions without any constraints
    conda_constraints = the_profile.conda_constraints(python)
    if conda_constraints is None:
        conda_constraints = {}

    constrained = [k for k in python_packages if k.specs]
    unconstrained = [k for k in python_packages if not k.specs]

    has_conda = [
        f"{k.project_name} {conda_constraints[k.project_name]}"
        for k in unconstrained
        if k.project_name in conda_constraints
    ]
    no_conda = [
        k for k in unconstrained if k.project_name not in conda_constraints
    ]

    # we should install all packages that have not been parsed yet, and have no
    # conda equivalent via Python/pip
    python_packages_str = [
        str(k)
        for k in constrained + no_conda
        if k.project_name not in parsed_packages
    ]

    # now we sort and make it unique
    python_packages_str = utils.uniq(sorted(python_packages_str))

    has_conda = utils.uniq(sorted(has_conda))

    logger.info(
        f"Adding {len(python_packages_str)} Python and {len(has_conda)} conda "
        f"packages to installation plan",
    )
    return meta, python_packages_str, has_conda


def _simplify_conda_plan(deps: list[str]) -> list[str]:
    """Simplifies the conda package plan by removing reduntant entries."""

    from .. import utils

    pins_striped = [k.split()[0] for k in deps if len(k.split()) > 1]
    no_pins = [k for k in deps if len(k.split()) == 1]

    keep_no_pins = [k for k in no_pins if k not in pins_striped]

    full_pins = [k for k in deps if len(k.split()) > 1]
    return utils.uniq(sorted(keep_no_pins + full_pins))


def _add_missing_conda_pins(
    the_profile: Profile, python: str, deps: list[str]
) -> list[str]:
    """Adds pins to unpinned packages, to respect the profile."""

    from .. import utils

    pinned_packages = the_profile.conda_constraints(python)

    if pinned_packages is None:
        return deps

    no_pins = [k for k in deps if len(k.split()) == 1 and k in pinned_packages]

    no_change = [k for k in deps if k not in no_pins]

    new_pins = [f"{k} {v}" for k, v in pinned_packages.items() if k in no_pins]

    return utils.uniq(sorted(no_change + new_pins))


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Creates an environment installation plan for developing the currently
     checked-out package, and the development profile in ``../profile``:

     .. code:: sh

        $ git clone <package>
        $ cd <package>
        $ conda activate base
        (base) devtool env -vv .
        (base) $ mamba env create -n dev -f environment.yaml
        (base) $ conda activate dev
        (dev) $ pip install --no-build-isolation --no-dependencies --editable .

     You may, of course, hand-edit the output file ``environment.yaml`` to
     adjust for details, add conda or Python packages you'd like to complement
     your work environment.  An example would be adding debuggers such as
     ``ipdb`` to the installation plan before calling ``mamba env create``.

  2. By default, we use the native Python version of your conda installation
     as the Python version to use for the newly created environment. You may
     select a different one with `--python=X.Y'.  You may also set the output
     filename with ``--output=name.yaml``, if the default does not please you:

     .. code:: sh

        $ conda activate base
        (base) devtool env -vv --python=3.9 --output=whatever-i-like.yaml .

  3. To develop multiple packages you checked out, just add the meta package
     files of all packages you wish to consider, then pip-install the packages
     on teh top of the created environment, in reverse dependence order
     (e.g. package A depends on B):

     .. code:: sh

        $ mkdir dev-dir
        $ cd dev-dir
        $ git clone <repo-of-B> src/B
        $ git clone <repo-of-A> src/A
        $ conda activate base
        (base) $ devtool env -vv src/*
        (base) $ mamba env create -n dev -f environment.yaml
        (base) $ conda activate dev
        (dev) $ pip install --no-build-isolation --no-dependencies --editable "src/B"
        (dev) $ pip install --no-build-isolation --no-dependencies --editable "src/A"

""",
)
@click.argument(
    "meta",
    nargs=-1,
    required=True,
)
@click.option(
    "-P",
    "--profile",
    default="default",
    show_default=True,
    callback=validate_profile,
    help="Directory containing the development profile (and a file named "
    "profile.toml), or the name of a configuration key pointing to the "
    "development profile to use",
)
@click.option(
    "-p",
    "--python",
    default=("%d.%d" % sys.version_info[:2]),
    show_default=True,
    help="Version of python to build the environment for",
)
@click.option(
    "-u/-U",
    "--public/--no-public",
    default=True,
    help="Set this to **include** private channels/indexes on your plan. "
    "For conda packages in this case, you **must** execute this within the "
    "Idiap intranet.",
)
@click.option(
    "-s/-S",
    "--stable/--no-stable",
    default=False,
    help="Set this to **exclude** beta channels from your build",
)
@click.option(
    "-o",
    "--output",
    default="environment.yaml",
    help="The name of the environment plan",
)
@verbosity_option(logger=logger)
def env(
    meta,
    profile,
    python,
    public,
    stable,
    output,
    **_,
) -> None:
    """Creates a development environment for one or more projects.

    The environment is created by scanning conda's ``meta.yaml`` and Python
    ``pyproject.toml`` files for all input projects.  All input that is not an
    existing file path, is considered a supplemental conda package to be
    installed.  The environment is dumped to disk in the form of a
    conda-installable YAML environment.  The user may edit this file to add
    Python packages that may be of interest.

    To interpret ``meta.yaml`` files found on the input directories, this
    command uses the conda render API to discover all profile-constrained and
    unconstrained packages to add to the new environment.
    """

    import os

    import yaml

    # 1. loads profile data
    the_profile = Profile(profile)

    # 2. loads all conda package data, reset "meta" to remove consumed entries
    conda_config = the_profile.conda_config(python, public, stable)
    meta, conda_parsed, conda_packages = _load_conda_packages(
        meta, conda_config
    )
    # 3. loads all python package data, reset "meta" to remove consumed entries
    meta, python_packages, extra_conda_packages = _load_python_packages(
        the_profile, python, meta, conda_parsed + conda_packages
    )

    # At this point, there shouldn't be anything else to consume
    if meta:
        logger.error(
            f"Ended parsing with unconsumed entries from the command-line: "
            f"{' ,'.join(meta)}"
        )

    # Adds python on the required version
    conda_packages.append(f"python {python}")
    conda_packages += extra_conda_packages

    # Performs "easy" simplification: if a package appears in two entries,
    # however one of them is a pin, keep only the pin
    conda_packages = _simplify_conda_plan(conda_packages)

    # Adds missing pins
    conda_packages = _add_missing_conda_pins(
        the_profile, python, conda_packages
    )

    # Write package installation plan, in YAML format
    data: dict[str, typing.Any] = dict(channels=conda_config.channels)

    if python_packages:
        # must install "pip"
        conda_packages.append("pip")
        conda_packages.append(
            dict(  # type: ignore
                pip=the_profile.python_indexes(public, stable) + python_packages
            )
        )

    data["dependencies"] = conda_packages

    # backup previous installation plan, if one exists
    if os.path.exists(output):
        backup = output + "~"
        if os.path.exists(backup):
            os.unlink(backup)
        os.rename(output, backup)

    with open(output, "w") as f:
        yaml.dump(data, f)

    click.secho(
        f"Run 'mamba env create -n dev -f {output}' to create environment",
        fg="yellow",
        bold=True,
    )
