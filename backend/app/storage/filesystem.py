"""Private, same-filesystem storage. Names come only from server UUIDs."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def directory(path, *, parent=None, create=False):
    if create:
        try:
            os.mkdir(path, mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
    fd = os.open(path, DIRECTORY, dir_fd=parent)
    try:
        yield fd
    finally:
        os.close(fd)


class FileSystem:
    def __init__(self, root: Path):
        self.root = root

    @contextmanager
    def area(self, name, owner=None):
        with directory(self.root) as root, directory(name, parent=root) as area:
            if owner is None:
                yield area
            else:
                with directory(
                    str(UUID(str(owner))), parent=area, create=True
                ) as owned:
                    os.fsync(area)
                    yield owned

    def available(self):
        with directory(self.root) as root:
            space = os.fstatvfs(root)
            return space.f_bavail * space.f_frsize

    @contextmanager
    def lock(self, operation, *, shared=False):
        with self.area("locks") as area:
            fd = os.open(
                str(operation),
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=area,
            )
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError("invalid storage lock")
                mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                fcntl.flock(fd, mode | fcntl.LOCK_NB)
                os.fsync(area)
                yield
            finally:
                os.close(fd)

    @contextmanager
    def stage(self, operation):
        with self.area("staging") as area:
            fd = os.open(
                str(operation),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
                dir_fd=area,
            )
            with os.fdopen(fd, "wb", buffering=0) as stream:
                os.fsync(area)
                yield stream
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())

    def publish(self, operation, owner, file_id):
        # Keep the staging hard link until SQL commits. It proves which inode an
        # interrupted operation owns; a collision is never overwritten/deleted.
        with self.area("staging") as stage, self.area("files", owner) as final:
            os.link(
                str(operation),
                str(file_id),
                src_dir_fd=stage,
                dst_dir_fd=final,
                follow_symlinks=False,
            )
            os.fsync(final)

    def clean(self, operation, owner, file_id, *, committed=False):
        with self.area("staging") as stage, self.area("files", owner) as final:
            if committed:
                try:
                    source = os.stat(
                        str(operation), dir_fd=stage, follow_symlinks=False
                    )
                except FileNotFoundError:
                    return
                retained = os.stat(str(file_id), dir_fd=final, follow_symlinks=False)
                if (source.st_dev, source.st_ino) != (retained.st_dev, retained.st_ino):
                    raise OSError("storage collision")
            if not committed:
                try:
                    target = os.stat(str(file_id), dir_fd=final, follow_symlinks=False)
                except FileNotFoundError:
                    target = None
                if target is not None:
                    source = os.stat(
                        str(operation), dir_fd=stage, follow_symlinks=False
                    )
                    if (source.st_dev, source.st_ino) != (target.st_dev, target.st_ino):
                        raise OSError("storage collision")
                    os.unlink(str(file_id), dir_fd=final)
                os.fsync(final)
            try:
                os.unlink(str(operation), dir_fd=stage)
            except FileNotFoundError:
                pass
            os.fsync(stage)

    @contextmanager
    def read(self, owner, file_id):
        with self.area("files", owner) as area:
            fd = os.open(
                str(file_id), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=area
            )
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise OSError("invalid stored file")
                yield stream

    def remove(self, operation, owner, file_id):
        """Explicit retained deletion: remove both links before releasing usage."""
        with self.area("staging") as stage, self.area("files", owner) as final:
            for area, name in ((final, str(file_id)), (stage, str(operation))):
                try:
                    os.unlink(name, dir_fd=area)
                except FileNotFoundError:
                    pass
                os.fsync(area)


def initialize(root: Path, uid=10001, gid=10001):
    """One-shot container initializer; never recursively touches existing files."""
    with directory(root) as root_fd:
        os.fchown(root_fd, uid, gid)
        os.fchmod(root_fd, 0o700)
        for name in ("files", "staging", "locks"):
            with directory(name, parent=root_fd, create=True) as area:
                os.fchown(area, uid, gid)
                os.fchmod(area, 0o700)
        os.fsync(root_fd)
