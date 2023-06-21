# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import typing

import click

from idiap_devtools.click import validate_profile
from idiap_devtools.profile import Profile

from ...click import PreserveIndentCommand, verbosity_option
from ...logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Runs the release procedure for all packages listed in ``changelog.md``:

     .. code:: sh

        devtool gitlab release -vv changelog.md

     .. tip::

        In case of errors, just edit the changelog file to remove packages
        already released before relaunching the application.

  2. The option ``--dry-run`` can be used to let the script print what it would
     do instead of actually doing it:

     .. code:: sh

        devtool gitlab release -vv --dry-run changelog.md

  3. You may also pin package dependencies upon the release, so that the
     shipped package respects a particular development profile set of pins:

     .. code:: sh

        devtool gitlab release -vv --pin-dependencies changelog.md

     The `default` profile is used, if set on your configuration file.
     Otherwise, you may specify it explicitly like:

     .. code:: sh

        devtool gitlab release -vv --profile=specific --pin-dependencies changelog.md

""",
)
@click.argument("changelog", type=click.File("rt", lazy=False))
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
    "--pin-dependencies/--no-pin-dependencies",
    default=False,
    help="If set, then pin dependencies from the dev-profile on the package "
    "to be released.  By default your default dev-profile is used.  You may "
    "override this using the --profile option",
)
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@verbosity_option(logger=logger)
def release(
    changelog: typing.TextIO,
    profile: str,
    pin_dependencies: bool,
    dry_run: bool,
    **_,
) -> None:
    """Tags packages on GitLab from an input CHANGELOG in markdown format.

    By using a CHANGELOG file as an input (e.g. that can be generated with the
    ``changelog`` command), this script goes through all packages listed (and
    in order):

        * Modifies ``pyproject.toml`` with the new release number and pins the
          dependencies according to the specified profile's constraints (if one
          was specified)
        * Sets-up the README links to point to the correct pipeline and
          documentation for the package
        * Commits, tags and pushes the git project adding the changelog
          description for the GitLab release page
        * Waits for the pipeline launched by the previous step to end
        * Bumps the package version again, to the next beta patch
        * Re-modifies the README to point to the "latest" documentation and
          pipeline versions
        * Re-commits and pushes the whole with the option ``[ci skip]``.

    N.B.: When the option ``pin-dependencies`` is set, the versions of the
    dependencies in ``pyproject.toml`` will be pinned to those of the Python
    ``constraints.txt`` file available in the select development profile.

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

    import packaging.version

    from ...gitlab import get_gitlab_instance
    from ...gitlab.release import (
        get_next_version,
        release_package,
        wait_for_pipeline_to_finish,
    )

    gl = get_gitlab_instance()

    # 1. loads profile data
    the_profile = Profile(profile)

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

    if dry_run:
        click.secho("!!!! DRY RUN MODE !!!!", fg="yellow", bold=True)
        click.secho(
            "No changes will be committed to GitLab.", fg="yellow", bold=True
        )

    for pkg_number, (header, line) in enumerate(pkgs):
        match = header_re.match(header)

        assert match, f"Line `{header}' somehow did not match title regexp"

        pkg = match.groupdict()["pkg"]
        bump = match.groupdict()["bump"]

        # gets the description for this package depending if that is the last
        # package listed, or not
        if pkg_number < (len(pkgs) - 1):
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
            f"`{use_package.attributes['path_with_namespace']}' "
            f"(id={use_package.id})",
        )

        # process the "bump" to be performed
        tag = bump.strip().lower()

        if tag in ("patch", "minor", "major"):
            logger.info(
                f"Processing package {pkg} to perform a {tag} release bump"
            )

            # gets the "next" tag for this package
            vtag = get_next_version(use_package, bump)
            logger.info(
                f"Bumping version of "
                f"{use_package.attributes['path_with_namespace']} "
                f"to {vtag}",
            )

        elif re.match(packaging.version.VERSION_PATTERN, tag, re.VERBOSE):
            vtag = f"v{tag}"
            logger.info(f"Tagging package {pkg} to {vtag} (forced)")

        else:
            raise RuntimeError(
                f"Cannot process tag {tag}: the value should be one of patch, "
                f"minor, or major, or a valid PEP-440 version number (to "
                f"force a tag)"
            )

        # release the package with the found tag and its comments
        pipeline_id = release_package(
            gitpkg=use_package,
            tag_name=vtag,
            tag_comments=description_text,
            dry_run=dry_run,
            profile=the_profile if pin_dependencies else None,
        )
        if not dry_run:
            # now, wait for the pipeline to finish, before we can release the
            # next package
            wait_for_pipeline_to_finish(use_package, pipeline_id)

    logger.info(f"Finished processing {changelog.name}")
