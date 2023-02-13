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

  1. List running jobs on any runners with tag "bob" (default):

     .. code:: sh

        devtool gitlab jobs -vv


  2. List running jobs on a runner with tag "macos":

     .. code:: sh

        devtool gitlab jobs -vv macos


  3. List running jobs on a runner with tag "macos" and "foo":

     .. code:: sh

        devtool gitlab jobs -vv macos foo

""",
)
@click.argument("tags", nargs=-1)
@click.option(
    "-s",
    "--status",
    type=click.Choice(["running", "success", "failed", "canceled"]),
    default="running",
    show_default=True,
    help='The status of jobs we are searching for - one of "running", '
    '"success", "failed" or "canceled"',
)
@verbosity_option(logger=logger)
def jobs(status, tags, **_) -> None:
    """Lists jobs on a given runner identified by description."""

    from ...gitlab import get_gitlab_instance

    gl = get_gitlab_instance()

    tags = tags or ["bob"]

    # search for the runner(s) to affect
    runners = gl.runners.list(tag_list=tags)

    if not runners:
        raise RuntimeError("Cannot find runner with tags = %s" % "|".join(tags))

    for runner in runners:
        jobs = runner.jobs.list(all=True, status=status)
        click.echo(
            "Runner %s (id=%d) -- %d running"
            % (
                runner.attributes["description"],
                runner.attributes["id"],
                len(jobs),
            )
        )
        for k in jobs:
            click.echo(
                "** job %d: %s (%s), since %s, by %s [%s]"
                % (
                    k.id,
                    k.attributes["project"]["path_with_namespace"],
                    k.attributes["name"],
                    k.attributes["started_at"],
                    k.attributes["user"]["username"],
                    k.attributes["web_url"],
                )
            )
