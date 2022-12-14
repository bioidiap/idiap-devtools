# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import typing

import click

from ..click import PreserveIndentCommand, verbosity_option
from ..logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Runs the release procedure for all packages listed in ``changelog.md``:

     .. code:: sh

        $ devtool release -vv changelog.md

     .. tip::

        In case of errors, just edit the changelog file to remove packages
        already released before relaunching the application.

  2. The option `-dry-run` can be used to let the script print what it would
     do instead of actually doing it:

     .. code:: sh

        $ devtool release -vv changelog.md

""",
)
@click.argument("changelog", type=click.File("rt", lazy=False))
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@verbosity_option(logger=logger)
def release(changelog: typing.TextIO, dry_run: bool, **_) -> None:
    """Tags packages on GitLab from an input CHANGELOG in markdown format.

    By using a CHANGELOG file as an input (e.g. that can be generated with the
    ``changelog`` command), this script goes through all packages listed (and
    in order):

        * Modifies ``pyproject.toml`` with the new release number
        * Sets-up the README links to point to the correct pipeline and
          documentation for the package
        * Commits, tags and pushes the git project adding the changelog
          description for the GitLab release page
        * Waits for the pipeline launched for the previous step to end
        * Bumps the package version again, to the next beta patch
        * Re-modifies the README to point to the "latest" documentation and
          pipeline versions
        * Re-commits the whole with the option ``[ci skip]``.

    The changelog is expected to have the following structure:

    .. code:: markdown

       # group-name/package-name: ``major``|``minor``|``patch``

         Description of changes in group-name/package-name

       # group-name/package-name-2: ``major``|``minor``|``patch``

         Description of changes in group-name/package-name-2

    The headings, each, correspond to package names, followed by a colon
    (``:``), and then one of the following keywords: ``major``, ``minor``, or
    ``patch``, indicating which part of the version number will be bumped
    during the release procedure (N.B.: following semantic version numbering).

    An indented piece of text marks the release notes for the package to be
    tagged, in any amount of detail.  The description of a single package is
    suffixed by another package heading, or the end of the file.

    You may use `GitLab-flavoured markdown (GLFM)
    <https://docs.gitlab.com/ee/user/markdown.html>`_ to refer to closed issues
    or merge requests.  Alternatively, use the command ``changelog`` to
    auto-generate the description for your release.
    """

    import re
    import textwrap

    from ..release import (
        get_gitlab_instance,
        get_next_version,
        release_package,
        wait_for_pipeline_to_finish,
    )

    gl = get_gitlab_instance()

    # traverse all packages in the changelog, edit older tags with updated
    # comments, tag them with a suggested version, then try to release, and
    # wait until done to proceed to the next package
    changelogs: list[str] = changelog.readlines()

    header_re = re.compile(
        r"^\s*#+\s*(?P<pkg>\S+(/\S+)+)\s*:\s*(?P<bump>\S+)\s*$"
    )

    # find the starts of each package's description at the changelog
    pkgs = [
        (line, k) for k, line in enumerate(changelogs) if header_re.match(line)
    ]

    # if we are in a dry-run mode, let's let it be known
    if dry_run:
        logger.warning("#### DRY RUN MODE ####")
        logger.warning("N.B.: No changes will be committed to GitLab.")

    for pkg_number, (header, line) in enumerate(pkgs):

        match = header_re.match(header)

        assert match, f"Line `{header}' somehow did not match title regexp"

        pkg = match.groupdict()["pkg"]
        bump = match.groupdict()["bump"]

        logger.info(
            f"Processing package {pkg} to perform a {bump} release bump"
        )

        # gets the description for this package depending if that is the last
        # package listed, or not
        if pkg_number < len(pkgs):
            description = changelogs[(line + 1) : pkgs[pkg_number + 1][1]]
        else:
            description = changelogs[(line + 1) :]

        # we clean-up the description a bit, to strip empty lines in the begin
        # and end
        description = [k for k in description if k.strip()]

        # tidy up description by joining and re-indenting
        description_text = textwrap.dedent("\n".join(description))

        # retrieves the gitlab package object
        use_package = gl.projects.get(pkg)
        logger.info(
            f"Found GitLab package "
            f"`use_package.attributes['path_with_namespace']' "
            f"(id={use_package.id})",
        )

        # gets the "next" tag for this package
        tag = get_next_version(use_package, bump)
        logger.info(
            f"Bumping version of "
            f"use_package.attributes['path_with_namespace'] "
            f"to {tag}",
        )

        # release the package with the found tag and its comments
        pipeline_id = release_package(
            use_package, tag, description_text, dry_run
        )
        # now, wait for the pipeline to finish, before we can release the
        # next package
        wait_for_pipeline_to_finish(use_package, pipeline_id)

    logger.info(f"Finished processing {changelog.name}")
