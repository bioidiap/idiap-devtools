# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Utilities for retrieving, parsing and auto-generating changelogs."""

from __future__ import annotations

import datetime
import io
import logging
import textwrap
import typing

import dateutil.parser
import gitlab
import gitlab.v4.objects
import pytz

logger = logging.getLogger(__name__)


def parse_date(s: typing.TextIO | str) -> datetime.datetime:
    """Parses any date supported by :py:meth:`dateutil.parser.parse`

    Automatically applies the "Europe/Zurich" timezone


    Arguments:

        s: The input readable stream or string to be parsed into a date


    Returns:

        A :py:class:`datetime.datetime`.
    """
    return dateutil.parser.parse(s, ignoretz=True).replace(
        tzinfo=pytz.timezone("Europe/Zurich")
    )


def _sort_commits(
    commits: typing.Iterable[gitlab.v4.objects.commits.ProjectCommit],
    reverse: bool,
) -> list[typing.Any]:
    """Sorts gitlab commit objects using their ``committed_date`` attribute.

    Arguments:

        commits: A list of commits to process

        reverse: Indicates if the sorting should be reversed


    Returns:

        The input list of ``commits``, sorted
    """

    return sorted(
        commits, key=lambda x: parse_date(x.committed_date), reverse=reverse
    )


def _sort_tags(
    tags: typing.Iterable[gitlab.v4.objects.tags.ProjectTag], reverse: bool
) -> list[typing.Any]:
    """Sorts gitlab tags objects using their ``committed_date`` attribute.

    Arguments:

        tags: A list of tags to process

        reverse: Indicates if the sorting should be reversed


    Returns:

        The input list of ``tags``, sorted
    """

    return sorted(
        tags,
        key=lambda x: parse_date(x.commit["committed_date"]),
        reverse=reverse,
    )


def get_file_from_gitlab(
    gitpkg: gitlab.v4.objects.projects.Project, path: str, ref: str = "main"
) -> io.StringIO:
    """Retrieves a file from a Gitlab repository.

    Arguments:

        gitpkg: The gitlab project to fetch the datafile from

        path: The internal path to the file to retrieve

        ref: Branch, commit or reference to get file from, at GitLab


    Returns:

        A string I/O object you can use like a file.
    """

    return io.StringIO(gitpkg.files.get(file_path=path, ref=ref).encode())


def get_last_tag_date(
    package: gitlab.v4.objects.projects.Project,
) -> datetime.datetime:
    """Returns the last release date for the given package.

    Falls back to the first commit date if the package has not yet been tagged


    Arguments:

        package: The gitlab project object from where to fetch the last release
                 date information


    Returns:

        A :py:class:`datetime.datetime` object that refers to the last date the
        package was released.  If the package was never released, then returns
        the date just before the first commit.


    Raises:

        RuntimeError: if the project has no commits.
    """

    # according to the Gitlab API documentation, tags are sorted from the last
    # updated to the first, by default - no need to do further sorting!
    tag_list = package.tags.list(
        page=1, per_page=1
    )  # Silence userWarning on list()

    if tag_list:
        # there are tags, use these
        last = tag_list[0]
        logger.debug(
            "Last tag for package %s (id=%d) is %s",
            package.name,
            package.id,
            last.name,
        )
        return parse_date(last.commit["committed_date"]) + datetime.timedelta(
            milliseconds=500
        )

    else:
        commit_list = package.commits.list(all=True)

        if commit_list:
            # there are commits, use these
            first = _sort_commits(commit_list, reverse=False)[0]
            logger.debug(
                "First commit for package %s (id=%d) is from %s",
                package.name,
                package.id,
                first.committed_date,
            )
            return parse_date(first.committed_date) - datetime.timedelta(
                milliseconds=500
            )

        else:
            # there are no commits nor tags - abort
            raise RuntimeError(
                "package %s (id=%d) does not have commits "
                "or tags so I cannot devise a good starting date"
                % (package.name, package.id)
            )


def _get_tag_changelog(tag: gitlab.v4.objects.tags.ProjectTag) -> str:
    try:
        return tag.release["description"]
    except Exception:
        return ""


def _write_one_tag(
    f: typing.TextIO, pkg_name: str, tag: gitlab.v4.objects.tags.ProjectTag
) -> None:
    """Prints commit information for a single tag of a given package.

    Arguments:

        f: open text stream, ready to be written at

        pkg_name: The name of the package we are writing tags of

        tag: The tag value
    """

    git_date = parse_date(tag.commit["committed_date"])
    newline = "\n"
    f.write(f"  - {tag.name} ({git_date:%b %d, %Y %H:%M}){newline}{newline}")

    for line in _get_tag_changelog(tag).replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if line.startswith("* ") or line.startswith("- "):
            line = line[2:]

        line = line.replace("!", pkg_name + "!").replace(
            pkg_name + pkg_name, pkg_name
        )
        line = line.replace("#", pkg_name + "#")
        if not line:
            continue
        f.write(f"    - {line}{newline}")

    f.write(f"{newline}")


def _write_commits_range(
    f: typing.TextIO,
    pkg_name: str,
    commits: typing.Iterable[gitlab.v4.objects.commits.ProjectCommit],
) -> None:
    """Writes all commits of a given package within a range, to the output
    file.

    Arguments:

        f: open text stream, ready to be written at

        pkg_name: The name of the package we are writing tags of

        commits: List of commits to be written
    """

    for commit in commits:
        commit_title = commit.title

        # skip commits that do not carry much useful information
        if (
            "[skip ci]" in commit_title
            or "Merge branch" in commit_title
            or "Increased stable" in commit_title
        ):
            continue

        commit_title = commit_title.strip()
        commit_title = commit_title.replace("!", pkg_name + "!").replace(
            pkg_name + pkg_name, pkg_name
        )
        commit_title = commit_title.replace("#", pkg_name + "#")

        f.write(f"  - {commit_title}")
        f.write("\n")

    f.write("\n")


def _write_mergerequests_range(
    f: typing.TextIO,
    pkg_name: str,
    mrs: typing.Iterable[gitlab.v4.objects.merge_requests.ProjectMergeRequest],
) -> None:
    """Writes all merge-requests of a given package, with a range, to the
    output file.

    Arguments:

        f: A :py:class:`File` ready to be written at

        pkg_name: The name of the package we are writing tags of

        mrs: The list of merge requests to write
    """

    for mr in mrs:
        title = mr.title.strip().replace("\r", "").replace("\n", " ")
        title = title.replace(" !", " " + pkg_name + "!")
        title = title.replace(" #", " " + pkg_name + "#")

        if mr.description is not None and mr.description.strip():
            description = mr.description.replace(" !", " " + pkg_name + "!")
            description = description.replace(" #", " " + pkg_name + "#")
            description = "\n\n" + description + "\n\n"
            f.write(
                f"  - {pkg_name}!{mr.iid}: {title}{textwrap.indent(description, '    ')}"
            )

        else:
            description = "No description for this MR"
            f.write(f"  - {pkg_name}!{mr.iid}: {title}")
            f.write("\n\n")

    f.write("\n")


def get_changes_since(
    gitpkg: gitlab.v4.objects.projects.Project, since: datetime.datetime
) -> tuple[
    list[gitlab.v4.objects.merge_requests.ProjectMergeRequest],
    list[gitlab.v4.objects.tags.ProjectTag],
    list[gitlab.v4.objects.commits.ProjectCommit],
]:
    """Gets the list of MRs, tags, and commits since the provided date.

    Arguments:

        gitpkg : A gitlab package object

        since : a date and time to start looking changes from


    Returns:

        A list of merge requests, tags and commits for the given package, since
        the determined date.
    """

    # get tags since release and sort them
    tags = gitpkg.tags.list(all=True)

    # sort tags by date
    tags = [k for k in tags if parse_date(k.commit["committed_date"]) >= since]
    tags = _sort_tags(tags, reverse=False)

    # get commits since release date and sort them too
    commits = gitpkg.commits.list(since=since, all=True)

    # sort commits by date
    commits = _sort_commits(commits, reverse=False)

    # get merge requests since the release data
    mrs = list(
        reversed(
            gitpkg.mergerequests.list(
                state="merged",
                updated_after=since,
                order_by="updated_at",
                all=True,
            )
        )
    )

    return mrs, tags, commits


def write_tags_with_commits(
    f: typing.TextIO,
    gitpkg: gitlab.v4.objects.projects.Project,
    since: datetime.datetime,
    mode: str,
) -> None:
    """Writes all tags and commits of a given package to the output file.

    Arguments:

        f: A stream ready to be written at

        gitpkg: A pointer to the gitlab package object

        since: Starting date

        mode: One of ``mrs`` (merge-requests), ``commits`` or ``tags``
            indicating how to list entries in the changelog for this package
    """

    mrs, tags, commits = get_changes_since(gitpkg, since)
    newline = "\n"

    f.write(
        f"# {gitpkg.attributes['path_with_namespace']}:"
        f" patch{newline}{newline}"
    )

    # go through tags and writes each with its message and corresponding
    # commits
    start_date = since
    for tag in tags:
        # write tag name and its text
        _write_one_tag(f, gitpkg.attributes["path_with_namespace"], tag)
        end_date = parse_date(tag.commit["committed_date"])

        if mode == "commits":
            # write commits from the previous tag up to this one
            commits4tag = [
                k
                for k in commits
                if (start_date < parse_date(k.committed_date) <= end_date)
            ]
            _write_commits_range(
                f, gitpkg.attributes["path_with_namespace"], commits4tag
            )

        elif mode == "mrs":
            # write merge requests from the previous tag up to this one
            # the attribute 'merged_at' is not available in GitLab API as of 27
            # June 2018
            mrs4tag = [
                k
                for k in mrs
                if (start_date < parse_date(k.updated_at) <= end_date)
            ]
            _write_mergerequests_range(
                f, gitpkg.attributes["path_with_namespace"], mrs4tag
            )

        start_date = end_date

    if mode != "tags":
        if mode == "mrs":
            # write leftover merge requests
            # the attribute 'merged_at' is not available in GitLab API as of 27
            # June 2018
            leftover_mrs = [
                k for k in mrs if parse_date(k.updated_at) > start_date
            ]
            _write_mergerequests_range(
                f, gitpkg.attributes["path_with_namespace"], leftover_mrs
            )

        else:
            # write leftover commits that were not tagged yet
            leftover_commits = [
                k for k in commits if parse_date(k.committed_date) > start_date
            ]
            _write_commits_range(
                f, gitpkg.attributes["path_with_namespace"], leftover_commits
            )


def write_tags(
    f: typing.TextIO,
    gitpkg: gitlab.v4.objects.projects.Project,
    since: datetime.datetime,
) -> None:
    """Writes all tags of a given package to the output file.

    Arguments:

        f: A stream ready to be written at

        gitpkg: A pointer to the gitlab package object

        since: Starting date
    """

    tags = gitpkg.tags.list()
    # sort tags by date
    tags = [k for k in tags if parse_date(k.commit["committed_date"]) >= since]
    tags = _sort_tags(tags, reverse=False)

    newline = "\n"
    f.write(
        f"# {gitpkg.attributes['path_with_namespace']}:"
        f" patch{newline}{newline}"
    )

    for tag in tags:
        _write_one_tag(f, gitpkg.attributes["path_with_namespace"], tag)
