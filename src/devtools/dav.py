# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

"""Utilities for managing WebDAV resources."""

import hashlib
import logging
import os
import pathlib

import tomli
import webdav3.client

logger = logging.getLogger(__name__)


def _setup_webdav_client(
    server: str, root: str, username: str, password: str
) -> webdav3.client.Client:
    """Configures and checks the webdav client."""

    # setup webdav connection
    webdav_options: dict[str, str] = dict(
        webdav_hostname=server,
        webdav_root=root,
        webdav_login=username,
        webdav_password=password,
    )

    retval = webdav3.client.Client(webdav_options)
    assert retval.valid()

    return retval


def _get_config():
    """Returns a dictionary with server parameters, or ask them to the user."""

    from .profile import USER_CONFIGURATION

    # tries to figure if we can authenticate using a configuration file

    if os.path.exists(USER_CONFIGURATION):
        with open(USER_CONFIGURATION, "rb") as f:
            data = tomli.load(f)
    else:
        data = {}

    # this does some sort of validation for the "webdav" data...
    if "webdav" in data:
        if (
            "server" not in data["webdav"]
            or "username" not in data["webdav"]
            or "password" not in data["webdav"]
        ):
            raise KeyError(
                'If the configuration file contains a "webdav" '
                "section, it should contain 3 variables defined inside: "
                '"server", "username", "password".'
            )
    else:
        # ask the user for the information, in case nothing available
        logger.warn(
            "Requesting server information for webDAV operation. "
            "(To create a configuration file, and avoid these, follow "
            "the Setup subsection at our Installation manual.)"
        )
        webdav_data = dict()
        webdav_data["server"] = input("The base address of the server: ")
        webdav_data["username"] = input("Username: ")
        webdav_data["password"] = input("Password: ")
        data["webdav"] = webdav_data

    return data["webdav"]


def compute_sha256(path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(65535), b""):
            sha256_hash.update(byte_block)
    file_hash = sha256_hash.hexdigest()
    return file_hash


def augment_path_with_hash(path: str) -> str:
    """Adds the first 8 digits of sha256sum of a file to its name.

    Example::

        augment_path_with_hash('/datasets/pad-face-replay-attack.tar.gz')
        '/datasets/pad-face-replay-attack-a8e31cc3.tar.gz'
    """
    p = pathlib.Path(path)
    if not p.is_file():
        raise ValueError(
            f"Can only augment path to files with a hash. Got: {path}"
        )
    file_hash = compute_sha256(path)[:8]
    suffix = "".join(p.suffixes)
    base_name = str(p.name)[: -len(suffix) or None]
    new_path = p.parent / f"{base_name}-{file_hash}{suffix}"
    return str(new_path)


def setup_webdav_client(private):
    """Returns a ready-to-use WebDAV client."""

    config = _get_config()
    root = "/private-upload" if private else "/public-upload"
    c = _setup_webdav_client(
        config["server"], root, config["username"], config["password"]
    )
    return c
