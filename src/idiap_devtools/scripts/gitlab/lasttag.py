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

  1. Get the last tag information of the software/clapp package:

     .. code::

        devtool gitlab lasttag software/clapp


  2. Get the last tag information of the beat/beat.core package:

     .. code::

        devtool gitlab lasttag beat/beat.core

""",
)
@click.argument("package")
@verbosity_option(logger=logger)
def lasttag(package, **_) -> None:
    """Returns the last tag information on a given PACKAGE."""
    import gitlab

    from ...gitlab import get_gitlab_instance
    from ...gitlab.changelog import parse_date

    if "/" not in package:
        raise RuntimeError('PACKAGE should be specified as "group/name"')

    gl = get_gitlab_instance()

    # we lookup the gitlab package once
    try:
        use_package = gl.projects.get(package)
        logger.info(
            "Found gitlab project %s (id=%d)",
            use_package.attributes["path_with_namespace"],
            use_package.id,
        )

        tag_list = use_package.tags.list(page=1, per_page=1)

        if tag_list:
            # there are tags, use these
            tag = tag_list[0]
            date = parse_date(tag.commit["committed_date"])
            click.echo(f"{package}: {tag.name} ({date:%Y-%m-%d %H:%M:%S})")
        else:
            click.echo(f"{package}: <no tags>")

    except gitlab.GitlabGetError:
        logger.warning(
            "Gitlab access error - package %s does not exist?",
            package,
            exc_info=True,
        )
        click.secho(f"{package}: unknown", fg="yellow")
