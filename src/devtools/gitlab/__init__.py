# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Utilities to interact with GitLab."""


import logging
import os

import gitlab

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
