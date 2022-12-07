# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import sys

import click

from ..click import PreserveIndentCommand, verbosity_option
from ..logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Generates the changelog for a single package using merge requests,
     outputs results to a file named ``changelog.md``, in markdown format:

     .. code:: sh

        devtool changelog -vv group/package.xyz -o changelog.md

  2. The same as above, but dumps the changelog to stdout instead of a file:

     .. code:: sh

        devtool changelog -vv group/package.xyz

  3. Generates the changelog for a single package looking at commits
     (not merge requests):

     .. code:: sh

        devtool changelog -vv --mode=commits group/package.xyz

  4. Generates the changelog for a single package looking at merge requests
     starting from a given date of January 1, 2016:

     .. code:: sh

        $ devtool changelog -vv --mode=mrs --since=2016-01-01 group/package.xyz

  5. Generates the changelog for a set of packages, listed one per line in a
     text file:

     .. code:: sh

        $ devtool changelog -vv --mode=mrs --since=2016-01-01 group/package.xyz

""",
)
@click.argument(
    "target",
    nargs=-1,
    required=True,
)
@click.option(
    "-o",
    "--output",
    default=sys.stdout,
    type=click.File(mode="w"),
    required=False,
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["mrs", "tags", "commits"]),
    default="mrs",
    show_default=True,
    help="Changes the way we produce the changelog.  By default, uses the "
    'text in every merge request (mode "mrs"). To use tag annotations, '
    'use mode "tags". If you use "commits" as mode, we use the text '
    "in commits to produce the changelog",
)
@click.option(
    "-s",
    "--since",
    help="A starting date in any format accepted by dateutil.parser.parse() "
    "(see https://dateutil.readthedocs.io/en/stable/parser.html) from "
    "which you want to generate the changelog.  If not set, the package's"
    "last release date will be used",
)
@verbosity_option(logger=logger)
def changelog(target, output, mode, since, **_) -> None:
    """Generates changelog file for package(s) from the Gitlab server.

    This script generates changelogs for either a single package or multiple
    packages, depending on the value of TARGET.  The changelog (in markdown
    format) is written to the output file CHANGELOG.

    There are two modes of operation: you may provide the package name in the
    format ``<gitlab-group>/<package-name>``. Or, optionally, provide an
    existing file containing a list of packages that will be iterated on.

    For each package, we will contact the Gitlab server and create a changelog
    using merge-requests (default), tags or commits since a given date.  If a
    starting date is not passed, we'll use the date of the last tagged value or
    the date of the first commit, if no tags are available in the package.
    """

    import datetime
    import os

    from ..changelog import (
        get_last_tag_date,
        parse_date,
        write_tags_with_commits,
    )
    from ..release import get_gitlab_instance

    gl = get_gitlab_instance()

    # reads package list or considers name to be a package name
    for tgt in target:

        if os.path.exists(tgt) and os.path.isfile(tgt):
            logger.info(f"Reading package names from file {tgt}...")
            with open(tgt) as f:
                packages = [
                    k.strip()
                    for k in f.readlines()
                    if k.strip() and not k.strip().startswith("#")
                ]
        else:
            logger.info(f"Assuming {tgt} is a package name...")
            packages = [tgt]

        # if the user passed a date, convert it
        since_dt = None
        if since is not None:
            since_dt = parse_date(since)

        # iterates over the packages and dumps required information
        for package in packages:

            if "/" not in package:
                raise RuntimeError(
                    f"Package names must contain group name"
                    f" (invalid: {package})"
                )

            # retrieves the gitlab package object
            use_package = gl.projects.get(package)
            logger.info(
                "Found gitlab project %s (id=%d)",
                use_package.attributes["path_with_namespace"],
                use_package.id,
            )

            last_release_date = since_dt or get_last_tag_date(use_package)
            logger.info(
                f"Retrieving data (mode={mode}) since "
                f"{last_release_date:%b %d, %Y %H:%M}",
            )

            # add 1s to avoid us retrieving previous release data
            last_release_date += datetime.timedelta(seconds=1)

            visibility = ["public", "private", "internal"]
            if mode == "tags":
                visibility = ["public"]

            if use_package.attributes["namespace"] == use_package.name:
                # skip system meta-package
                logger.warning(
                    f"Skipping meta package {use_package.attributes['path_with_namespace']}...",
                )
                continue

            if use_package.attributes["visibility"] not in visibility:
                logger.warning(
                    'Skipping package %s (visibility not in "%s")...',
                    use_package.attributes["path_with_namespace"],
                    "|".join(visibility),
                )
                continue

            # write_tags(f, use_package, last_release_date)
            write_tags_with_commits(
                output, use_package, last_release_date, mode
            )

    output.flush()
