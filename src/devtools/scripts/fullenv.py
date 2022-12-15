# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import sys

import click

from ..click import PreserveIndentCommand, validate_profile, verbosity_option
from ..logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(cls=PreserveIndentCommand)
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
    "-Y",
    "--only-python/--no-only-python",
    default=False,
    show_default=True,
    help="Only installs Python packages, and not conda packages "
    "(except for Python itself, and pip)",
)
@click.option(
    "-o",
    "--output",
    default="environment.yaml",
    help="The name of the environment plan",
)
@verbosity_option(logger=logger)
def fullenv(
    profile,
    python,
    only_python,
    output,
    **_,
) -> None:
    """Creates a development environment with all constrained packages.

    .. code:: sh

       $ conda activate base
       (base) $ devtool fullenv -vv ../profile
       (base) $ mamba env create -n dev -f environment.yaml
       (base) $ conda activate dev

    You may, of course, hand-edit the output file ``environment.yaml`` to
    adjust for details, add conda or Python packages you'd like to complement
    your work environment.  An example would be adding debuggers such as
    ``ipdb`` to the installation plan before calling ``mamba env create``.
    """

    import os
    import typing

    import yaml

    from ..profile import Profile

    the_profile = Profile(profile)

    base_environment = dict(python=python, pip=None)

    if only_python:
        conda_packages = None
    else:
        conda_packages = the_profile.conda_constraints(python)

    if conda_packages is not None:
        conda_packages.update(base_environment)
    else:
        conda_packages = base_environment

    python_packages = the_profile.python_constraints()
    if python_packages is None:
        python_packages = []

    # filter out all conda packages already in the list
    conda_to_python = the_profile.get(("conda", "to_python"), {})
    python_to_conda = {
        v: k for k, v in conda_to_python.items() if k != "__ignore__"
    }
    python_packages = [
        k
        for k in python_packages
        if python_to_conda.get(k.project_name, k.project_name)
        not in conda_packages
    ]

    data: dict[str, typing.Any] = dict(channels=["conda-forge"])

    data["dependencies"] = sorted(
        [f"{k} {v}" if v is not None else k for k, v in conda_packages.items()]
    )

    if python_packages:
        data["dependencies"].append(
            dict(pip=sorted([str(k) for k in python_packages]))
        )

    # backup previous installation plan, if one exists
    if os.path.exists(output):
        backup = output + "~"
        if os.path.exists(backup):
            os.unlink(backup)
        os.rename(output, backup)

    with open(output, "w") as f:
        yaml.dump(data, f)

    click.echo(
        "Run the following commands to create and prepare your development environment:"
    )
    install_cmds = [
        f"mamba env create --force -n dev -f {output}",
        "conda activate dev",
    ]
    for k in install_cmds:
        click.secho(k, fg="yellow", bold=True)
