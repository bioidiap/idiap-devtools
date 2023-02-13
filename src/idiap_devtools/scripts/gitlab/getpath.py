# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import click

from ...click import PreserveIndentCommand, verbosity_option
from ...logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Get the file ``profile.toml`` from software/dev-profile's default branch:

     .. code:: sh

        devtool gitlab getpath software/dev-profile profile.toml


  2. Get the directory ``gitlab`` (and eventual sub-directories) from
     software/dev-profile:

     .. code:: sh

        devtool gitlab getpath software/dev-profile gitlab

""",
)
@click.argument("package")
@click.argument("path")
@click.argument("output", type=click.Path(exists=False), required=False)
@click.option(
    "-r",
    "--ref",
    help="Download path from the provided git reference (may be a branch, "
    "tag or commit hash).  If not set, then use the default package "
    "branch as reference to download.",
)
@verbosity_option(logger=logger)
def getpath(package, path, output, ref, **_) -> None:
    """Downloads files and directories from gitlab.

    Files are downloaded and stored.  Directories are recursed and fully
    downloaded to the client.
    """

    from ...gitlab import download_path, get_gitlab_instance

    if "/" not in package:
        raise RuntimeError('PACKAGE should be specified as "group/name"')

    gl = get_gitlab_instance()

    # we lookup the gitlab package once
    use_package = gl.projects.get(package)
    logger.info(
        "Found gitlab project %s (id=%d)",
        use_package.attributes["path_with_namespace"],
        use_package.id,
    )
    download_path(use_package, path, output, ref=ref)
