# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Utilities to interact with GitLab."""


import logging
import os
import pathlib
import shutil
import tarfile
import tempfile

from io import BytesIO

import gitlab
import gitlab.v4.objects

logger = logging.getLogger(__name__)


def get_gitlab_instance() -> gitlab.Gitlab:
    """Returns an instance of the gitlab object for remote operations."""
    # tries to figure if we can authenticate using a global configuration
    cfgs = ["~/.python-gitlab.cfg", "/etc/python-gitlab.cfg"]
    cfgs = [os.path.expanduser(k) for k in cfgs]
    if any([os.path.exists(k) for k in cfgs]):
        gl = gitlab.Gitlab.from_config(
            "idiap", [k for k in cfgs if os.path.exists(k)]
        )
    else:  # ask the user for a token or use one from the current runner
        server = os.environ.get("CI_SERVER_URL", "https://gitlab.idiap.ch")
        token = os.environ.get("CI_JOB_TOKEN")
        if token is None:
            logger.debug(
                "Did not find any of %s nor CI_JOB_TOKEN is defined. "
                "Asking for user token on the command line...",
                "|".join(cfgs),
            )
            token = input(f"{server} (private) token: ")
        gl = gitlab.Gitlab(server, private_token=token, api_version="4")

    return gl


def download_path(
    package: gitlab.v4.objects.projects.Project,
    path: str,
    output: pathlib.Path | None = None,
    ref: str | None = None,
) -> None:
    """Downloads paths from gitlab, with an optional recurse.

    This method will download an archive of the repository from chosen
    reference, and then it will search inside the zip blob for the path to be
    copied into output.  It uses :py:class:`zipfile.ZipFile` to do this search.
    This method will not be very efficient for larger repository references,
    but works recursively by default.

    Args:

      package: the gitlab package object to use (should be pre-fetched)

      path: the path on the project to download

      output: where to place the path to be downloaded - if not provided, use
        the basename of ``path`` as storage point with respect to the current
        directory

      ref: the name of the git reference (branch, tag or commit hash) to use.
        If None specified, defaults to the default branch of the input package
    """

    output = output or pathlib.Path(os.path.realpath(os.curdir))
    ref = ref or package.default_branch

    logger.debug(
        'Downloading archive of "%s" from "%s"...',
        ref,
        package.attributes["path_with_namespace"],
    )
    archive = package.repository_archive(ref=ref)
    logger.debug("Archive has %d bytes", len(archive))
    logger.debug('Searching for "%s" within archive...', path)

    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as f:
            f.extractall(path=d)

        # move stuff to "output"
        basedir = os.listdir(d)[0]
        shutil.move(os.path.join(d, basedir, path), output)
