import logging
import os
import shutil
import typing
from typing import TYPE_CHECKING
import json
from pathlib import Path
from collections import OrderedDict

from .settings import get_cache_dir

if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .tmf_types import PathLike


logger = logging.getLogger('pytuflow')


class TuflowBinaries:
    """Class for managing TUFLOW binary versions and paths. A single instance of this class is created and used
    globally. This instance should be used rather than manually initialising this class.
    To access the instance, import the :data:`tuflow_binaries` variable:

    Examples
    --------
    >>> from pytuflow.util import tuflow_binaries
    >>> tuflow_binaries.get('2023-03-AE')
    'C:/TUFLOW/releases/2023-03-AE/TUFLOW_iSP_w64.exe'
    """

    def __init__(self):
        self._tuflow_version_json = self.tuflow_version_json()
        self._settings = {}
        self._version2bin = None

        #: dict: User registered TUFLOW binary locations
        self.user_bin_locations = {}

        #: list[Path]: Registered TUFLOW binary folders
        self.user_folders = {}

        self.refresh_from_settings()

    @property
    def version2bin(self) -> dict:
        #: dict: TUFLOW binaries ``{version name: path}``
        if self._version2bin is None:
            self.load_versions()
        return self._version2bin

    def __repr__(self):
        return '<TuflowBinaries>'

    def __contains__(self, item):
        return item in self.version2bin

    def __getitem__(self, item):
        return self.version2bin[item]

    def clear(self):
        self._version2bin.clear()
        self.user_folders.clear()
        self.user_bin_locations.clear()
        self.save_tuflow_settings_cache()

    def count(self):
        return len(self.version2bin)

    def items(self) -> typing.Generator[tuple[str, str], None, None]:
        """Generator that yields the TUFLOW binary versions and paths as tuples.

        Yields
        ------
        tuple[str, str]
            Tuple containing the TUFLOW version name and path to the binary.
        """
        for item in self.version2bin.items():
            yield item

    def get(self, item: str, default: typing.Any = None) -> str:
        return self.version2bin.get(item, default)

    @staticmethod
    def tuflow_version_json() -> Path:
        """Returns the path to the JSON file containing stored TUFLOW version info.

        Returns
        -------
        Path
            Path to the JSON file containing stored TUFLOW version info.
        """
        return Path(get_cache_dir()) / 'tuflow_versions.json'

    def refresh_from_settings(self):
        """Updates the internal state based on the setting cache (JSON file) in case it was modified from a separate pytuflow process."""
        self._settings = self.load_tuflow_settings_cache()
 
        #: dict: User registered TUFLOW binary locations
        self.user_bin_locations = self._settings.get('bin', OrderedDict())
 
        #: list[Path]: Registered TUFLOW binary folders``
        self.user_folders = self._settings.get('folders', [])
 
        self.load_versions()

    def load_tuflow_settings_cache(self) -> dict:
        """Load the TuflowVersions object from the JSON file.

        Returns
        -------
        dict
            The settings dictionary containing the registered TUFLOW binaries and folders.
        """
        if self._tuflow_version_json.exists():
            with self._tuflow_version_json.open() as fo:
                try:
                    return json.load(fo, object_pairs_hook=OrderedDict)
                except json.JSONDecodeError:
                    logger.warning('TUFLOW version cache file is corrupted. A new cache file will be created.')
        return {}

    def save_tuflow_settings_cache(self) -> None:
        """Saves the tuflow versions to the cache (JSON file)."""
        self._settings = {'bin': self.user_bin_locations, 'folders': self.user_folders}
        if not Path(get_cache_dir()).exists():
            Path(get_cache_dir()).mkdir(parents=True)
        with self._tuflow_version_json.open('w') as fo:
            json.dump(self._settings, fo, indent=4)

    def load_versions(self):
        # start with folders
        d = self._load_tuflow_folders(self.user_folders)

        # update with user registered versions
        d.update(self.user_bin_locations)

        # finally, the installed locations take precedence over everything else
        d.update(self.load_installed_tuflow_versions())

        self._version2bin = d

    @staticmethod
    def load_installed_tuflow_versions():
        if os.name == 'nt':
            return TuflowBinaries.enum_msi_tuflow()
        else:
            # quick check
            folders = ['/opt/tuflow']
            versions = TuflowBinaries._load_tuflow_folders(folders)
            if versions:
                for version, bin in versions.copy().items():
                    actual_version = TuflowBinaries.tuflow_version_query(bin)
                    if actual_version:
                        versions.pop(version)
                        versions[actual_version] = bin
                return versions
            # query package managers
            pkg_manager = TuflowBinaries.package_manager()
            if pkg_manager == 'dpkg':
                return TuflowBinaries.load_dpkg_tuflow()
            elif pkg_manager == 'rpm':
                return TuflowBinaries.load_rpm_tuflow()
            return {}

    @staticmethod
    def _load_tuflow_folders(folders: list[str | Path]) -> dict:
        tuflow = 'TUFLOW_iSP_w64' if os.name == 'nt' else 'tuflow-isp'
        d = OrderedDict()
        for folder in folders:
            p = Path(folder)
            for f in p.glob(f'**/{tuflow}*'):
                version = f.parent.name
                if os.name != 'nt':
                    version = version.replace('tuflow_', '')
                d[version] = str(f)
        return d

    @staticmethod
    def tuflow_version_query(bin_path: str) -> str | None:
        """Only tested post 2026."""
        import subprocess
        try:
            output = subprocess.check_output([bin_path, '-version'], text=True)
            version_text = [x for x in output.splitlines() if x.startswith('TUFLOW Build:')]
            if not version_text:
                return None
            version_text = version_text[0]
            v = version_text.split(' ')[-1]
            if '-iSP' in v:
                v = v.split('-iSP')[0]
            if '-iDP' in v:
                v = v.split('-iDP')[0]
            return v
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    @staticmethod
    def package_manager() -> str | None:
        if shutil.which('dpkg-query'):
            return 'dpkg'
        if shutil.which('rpm'):
            return 'rpm'
        return None

    @staticmethod
    def load_dpkg_tuflow() -> dict:
        import subprocess
        versions = {}
        try:
            output = subprocess.check_output(['dpkg-query', '-L', 'tuflow'], text=True)
            bins = [x for x in output.splitlines() if 'tuflow-isp' in x]
            for bin in bins:
                version = TuflowBinaries.tuflow_version_query(bin)
                if version:
                    versions[version] = bin
            return versions
        except subprocess.CalledProcessError:
            return {}

    @staticmethod
    def load_rpm_tuflow() -> dict:
        import subprocess
        versions = {}
        try:
            output = subprocess.check_output(['rpm', '-ql', 'tuflow'], text=True)
            bins = [x for x in output.splitlines() if 'tuflow-isp' in x]
            for bin in bins:
                version = TuflowBinaries.tuflow_version_query(bin)
                if version:
                    versions[version] = bin
            return versions
        except subprocess.CalledProcessError:
            return {}

    @staticmethod
    def enum_msi_tuflow() -> dict:
        """no-doc"""
        import winreg
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BMT Commercial Australia Pty Ltd"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\BMT Commercial Australia Pty Ltd"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\BMT Commercial Australia Pty Ltd"),
        ]

        versions = {}

        for hive, path in roots:
            try:
                key = winreg.OpenKey(hive, path)
            except FileNotFoundError:
                continue

            try:
                subkey_count = winreg.QueryInfoKey(key)[0]
            except OSError:
                continue

            for i in range(subkey_count):
                try:
                    subkey_name = winreg.EnumKey(key, i)

                    # Example: "TUFLOW 2026.0"
                    if subkey_name.startswith("TUFLOW"):
                        subkey = winreg.OpenKey(key, subkey_name)
                        path, _ = winreg.QueryValueEx(subkey, "Path")
                        version, _ = winreg.QueryValueEx(subkey, "Version")
                        exe = None
                        for p in Path(path).glob('*.exe'):
                            if 'isp' in p.stem.lower():
                                exe = str(p)
                                break
                        if exe:
                            versions[version] = exe


                except OSError:
                    continue

        return versions



#: TuflowBinaries: Global instance of the TuflowBinaries class. See :class:`TuflowBinaries` for class information.
tuflow_binaries = TuflowBinaries()


def register_tuflow_binary(version_name: str, version_path: 'PathLike') -> None:
    """Register (save) a TUFLOW binary version path. Versions saved via this method will take precedence over versions
    found in registered folders :func:`register_tuflow_binary_folder <pytuflow.util.register_tuflow_binary_folder>`.

    Parameters
    ----------
    version_name : str
        Name of the TUFLOW binary version e.g. '2023-03-AE'
    version_path : PathLike
        Path to the TUFLOW binary executable
    """
    tuflow_binaries.user_bin_locations[version_name] = str(version_path)
    tuflow_binaries.save_tuflow_settings_cache()
    logger.info('New TUFLOW binary registered: {} - {}'.format(version_name, version_path))


def register_tuflow_binary_folder(folder: 'PathLike') -> None:
    """Register a directory containing TUFLOW releases. The directory should contain subdirectories (folders)
    named after the TUFLOW version and each subdirectory should contain the TUFLOW binaries
    (i.e. no further subdirectories should be present). The directory names are used as the registered version
    name and the available binaries are refreshed each time a TUFLOW binary is requested (i.e. a simulation is run).

    It is best if this directory is a local directory and not a network drive. Binaries registered via
    :func:`register_tuflow_binary <pytuflow.util.register_tuflow_binary>` are given priority over
    binaries found using this method.

    Parameters
    ----------
    folder : PathLike
        Directory containing TUFLOW binaries
    """
    if folder not in tuflow_binaries.user_folders:
        tuflow_binaries.user_folders.append(folder)
        logger.info('New TUFLOW binary folder registered: {}'.format(folder))
        tuflow_binaries.save_tuflow_settings_cache()
