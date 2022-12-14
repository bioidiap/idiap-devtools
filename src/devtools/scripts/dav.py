# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import click

from ..click import AliasedGroup, PreserveIndentCommand, verbosity_option
from ..logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.group(cls=AliasedGroup)
def dav() -> None:
    """Commands for managing content on a WebDAV server.

    Commands defined here require a server, username and a password to
    operate properly.  These values will be asked to you everytime you
    use a subcommand in this group.  To avoid repetitive asking, create
    a configuration file as indicated in the
    :ref:`devtools.install.setup.webdav` section of the user guide.
    """
    pass


@dav.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. List contents of 'public':

     $ devtool dav -vv list


  2. List contents of 'public/databases/latest':

     $ devtool dav -vv list databases/latest


  3. List contents of 'private/docs':

     $ devtool dav -vv list -p docs

""",
)
@click.option(
    "-p",
    "--private/--no-private",
    default=False,
    help="If set, use the 'private' area instead of the public one",
)
@click.option(
    "-l",
    "--long-format/--no-long-format",
    default=False,
    help="If set, print details about each listed file",
)
@click.argument(
    "path",
    default="/",
    required=False,
)
@verbosity_option(logger=logger)
def list(private, long_format, path, **_) -> None:
    """List the contents of a given WebDAV directory."""

    from ..dav import setup_webdav_client

    if not path.startswith("/"):
        path = "/" + path
    cl = setup_webdav_client(private)
    contents = cl.list(path)
    remote_path = cl.get_url(path)
    click.secho(f"ls {remote_path}", bold=True)
    for k in contents:
        if long_format:
            info = cl.info("/".join((path, k)))
            click.echo("%-20s  %-10s  %s" % (info["created"], info["size"], k))
        else:
            click.echo(k)


@dav.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Creates directory 'foo/bar' on the remote server:

     $ devtool dav -vv mkdir foo/bar

""",
)
@click.option(
    "-p",
    "--private/--no-private",
    default=False,
    help="If set, use the 'private' area instead of the public one",
)
@click.argument(
    "path",
    required=True,
)
@verbosity_option(logger=logger)
def makedirs(private, path, **_):
    """Creates a given directory, recursively (if necessary)

    Gracefully exists if the directory is already there.
    """

    from ..dav import setup_webdav_client

    if not path.startswith("/"):
        path = "/" + path
    cl = setup_webdav_client(private)
    remote_path = cl.get_url(path)

    if cl.check(path):
        click.secho(
            f"directory {remote_path} already exists", fg="yellow", bold=True
        )

    rpath = ""
    for k in path.split("/"):
        rpath = "/".join((rpath, k)) if rpath else k
        if not cl.check(rpath):
            click.secho(f"mkdir {rpath}", bold=True)
            cl.mkdir(rpath)


@dav.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Removes (recursively), everything under the 'remote/path/foo/bar' path:

     $ devtool dav -vv rmtree remote/path/foo/bar

     Notice this does not do anything for security.  It just displays what it
     would do.  To actually run the rmtree comment pass the --execute flag (or
     -x)


  2. Realy removes (recursively), everything under the 'remote/path/foo/bar'
     path:

     $ devtool dav -vv rmtree --execute remote/path/foo/bar


""",
)
@click.option(
    "-p",
    "--private/--no-private",
    default=False,
    help="If set, use the 'private' area instead of the public one",
)
@click.option(
    "-x",
    "--execute/--no-execute",
    default=False,
    help="If this flag is set, then execute the removal",
)
@click.argument(
    "path",
    required=True,
)
@verbosity_option(logger=logger)
def rmtree(private, execute, path, **_) -> None:
    """Removes a whole directory tree from the WebDAV server.

    ATTENTION: There is no undo!  Use --execute to execute.
    """

    from ..dav import setup_webdav_client

    if not execute:
        click.secho("!!!! DRY RUN MODE !!!!", fg="yellow", bold=True)
        click.secho(
            "Nothing is being executed on server.  Use -x to execute.",
            fg="yellow",
            bold=True,
        )

    if not path.startswith("/"):
        path = "/" + path
    cl = setup_webdav_client(private)
    remote_path = cl.get_url(path)

    if not cl.check(path):
        click.secho(
            f"resource {remote_path} does not exist", fg="yellow", bold=True
        )
        return

    click.secho(f"rm -rf {remote_path}", bold=True)
    if execute:
        cl.clean(path)


@dav.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Uploads a single file to a specific location:

     $ devtool dav upload -vv --checksum local/file remote


  2. Uploads various resources at once:

     $ devtool dav upload -vv --checksum local/file1 local/dir local/file2 remote

""",
)
@click.option(
    "-p",
    "--private/--no-private",
    default=False,
    help="If set, use the 'private' area instead of the public one",
)
@click.option(
    "-x",
    "--execute/--no-execute",
    default=False,
    help="If this flag is set, then execute the removal",
)
@click.option(
    "-c",
    "--checksum/--no-checksum",
    default=False,
    help="If set, will augment the filename(s) on the server with 8 first characters of their sha256 checksum.",
)
@click.argument(
    "local",
    required=True,
    type=click.Path(file_okay=True, dir_okay=True, exists=True),
    nargs=-1,
)
@click.argument(
    "remote",
    required=True,
)
@verbosity_option(logger=logger)
def upload(private, execute, checksum, local, remote, **_) -> None:
    """Uploads a local resource (file or directory) to a remote destination.

    If the local resource is a directory, it is uploaded recursively.  If the
    remote resource with the same name already exists, an error is raised (use
    rmtree to remove it first).

    If the remote location does not exist, it is an error as well.  As a
    consequence, you cannot change the name of the resource being uploaded with
    this command.

    ATTENTION: There is no undo!  Use --execute to execute.
    """

    import os
    import re
    import tempfile

    from ..dav import augment_path_with_hash, setup_webdav_client

    if not execute:
        click.secho("!!!! DRY RUN MODE !!!!", fg="yellow", bold=True)
        click.secho(
            "Nothing is being executed on server.  Use -x to execute.",
            fg="yellow",
            bold=True,
        )

    if not remote.startswith("/"):
        remote = "/" + remote
    cl = setup_webdav_client(private)

    if not cl.check(remote):
        click.secho(
            f"base remote directory for upload {remote} does not exist",
            fg="red",
            bold=True,
        )
        return

    for k in local:

        if not os.path.isdir(k):
            path_with_hash = k
            if checksum:
                path_with_hash = augment_path_with_hash(k)
            actual_remote = remote + os.path.basename(path_with_hash)
            remote_path = cl.get_url(actual_remote)
        else:
            actual_remote = "/".join((remote, os.path.basename(k)))
            actual_remote = re.sub("/+", "/", actual_remote)
            remote_path = cl.get_url(actual_remote)

        if cl.check(actual_remote):
            click.secho(
                f"resource {remote_path} already exists", fg="yellow", bold=True
            )
            click.secho(
                "remove it first before uploading a new copy",
                fg="yellow",
                bold=True,
            )
            continue

        if os.path.isdir(k):
            if checksum:
                # checksumming requires we create a new temporary directory
                # structure in which the filenames are already hashed
                # correctly, as there are no means to pass a set of remote
                # paths at client call.
                with tempfile.TemporaryDirectory() as d:
                    for root, __, files in os.walk(k):
                        for f in files:
                            rel_dir = os.path.relpath(root, k)
                            os.makedirs(os.path.join(d, rel_dir), exist_ok=True)
                            src = os.path.join(k, rel_dir, f)
                            path_with_hash = augment_path_with_hash(src)
                            os.symlink(
                                os.path.join(os.path.realpath(k), rel_dir, f),
                                os.path.join(
                                    d,
                                    rel_dir,
                                    os.path.basename(path_with_hash),
                                ),
                            )
                    click.secho(f"cp -r {d} {remote_path}", bold=True)
                    if execute:
                        cl.upload_directory(
                            local_path=d, remote_path=actual_remote
                        )
            else:
                # it is a simple upload, you can use the actual local directory
                # as a pointer
                click.secho(f"cp -r {k} {remote_path}", bold=True)
                if execute:
                    cl.upload_directory(local_path=k, remote_path=actual_remote)
        else:
            click.secho(f"cp {k} {remote_path}", bold=True)
            if execute:
                cl.upload_file(local_path=k, remote_path=actual_remote)
