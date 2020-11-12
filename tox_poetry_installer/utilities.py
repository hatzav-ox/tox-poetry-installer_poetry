"""Helper utility functions, usually bridging Tox and Poetry functionality"""
from pathlib import Path
from typing import Sequence
from typing import Set

from poetry.core.packages import Package as PoetryPackage
from poetry.installation.pip_installer import PipInstaller as PoetryPipInstaller
from poetry.io.null_io import NullIO as PoetryNullIO
from poetry.poetry import Poetry
from poetry.puzzle.provider import Provider as PoetryProvider
from poetry.utils.env import VirtualEnv as PoetryVirtualEnv
from tox import reporter
from tox.venv import VirtualEnv as ToxVirtualEnv

from tox_poetry_installer import constants
from tox_poetry_installer import exceptions
from tox_poetry_installer.datatypes import PackageMap


def install_to_venv(
    poetry: Poetry, venv: ToxVirtualEnv, packages: Sequence[PoetryPackage]
):
    """Install a bunch of packages to a virtualenv

    :param poetry: Poetry object the packages were sourced from
    :param venv: Tox virtual environment to install the packages to
    :param packages: List of packages to install to the virtual environment
    """

    reporter.verbosity1(
        f"{constants.REPORTER_PREFIX} Installing {len(packages)} packages to environment at {venv.envconfig.envdir}"
    )

    installer = PoetryPipInstaller(
        env=PoetryVirtualEnv(path=Path(venv.envconfig.envdir)),
        io=PoetryNullIO(),
        pool=poetry.pool,
    )

    for dependency in packages:
        reporter.verbosity1(f"{constants.REPORTER_PREFIX} installing {dependency}")
        installer.install(dependency)


def find_transients(packages: PackageMap, dependency_name: str) -> Set[PoetryPackage]:
    """Using a poetry object identify all dependencies of a specific dependency

    :param poetry: Populated poetry object which can be used to build a populated locked
                   repository object.
    :param dependency_name: Bare name (without version) of the dependency to fetch the transient
                            dependencies of.
    :returns: List of packages that need to be installed for the requested dependency.

    .. note:: The package corresponding to the dependency named by ``dependency_name`` is included
              in the list of returned packages.
    """

    try:

        def find_deps_of_deps(name: str, transients: PackageMap):
            if name in PoetryProvider.UNSAFE_PACKAGES:
                reporter.warning(
                    f"{constants.REPORTER_PREFIX} installing package '{name}' using Poetry is not supported; skipping installation of package '{name}'"
                )
            else:
                transients[name] = packages[name]
                for dep in packages[name].requires:
                    if dep.name not in transients.keys():
                        find_deps_of_deps(dep.name, transients)

        transients: PackageMap = {}
        find_deps_of_deps(packages[dependency_name].name, transients)

        return set(transients.values())
    except KeyError:
        if any(
            delimiter in dependency_name
            for delimiter in constants.PEP508_VERSION_DELIMITERS
        ):
            raise exceptions.LockedDepVersionConflictError(
                f"Locked dependency '{dependency_name}' cannot include version specifier"
            ) from None
        raise exceptions.LockedDepNotFoundError(
            f"No version of locked dependency '{dependency_name}' found in the project lockfile"
        ) from None
