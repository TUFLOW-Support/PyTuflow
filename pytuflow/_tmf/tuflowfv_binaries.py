import logging
import typing

from .tuflow_binaries import TuflowBinaries

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from .tmf_types import PathLike


logger = logging.getLogger('pytuflow')


class TuflowFVBinaries(TuflowBinaries):
    WINDOWS_BIN_NAME = 'TUFLOWFV'
    LINUX_BIN_NAME = ''
    NAME = 'tuflowfv'
    MSI_NAME = 'TUFLOW FV'
    STANDARD_LINUX_LOCATIONS = ('/opt/tuflowfv',)
    CACHE_NAME = 'tuflowfv_versions.json'

    @classmethod
    def tuflow_version_query(cls, bin_path: str) -> str | None:
        """Only tested post 2026."""
        import subprocess
        try:
            output = subprocess.check_output([bin_path, '-version'], stderr=subprocess.PIPE, text=True)
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
            try:
                output = subprocess.run([bin_path], input='\n', text=True, capture_output=True)
                line = [x for x in output.stdout.splitlines() if 'Build version:' in x]
                if line:
                    return line[0].split(':')[-1].strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

    @classmethod
    def _custom_filter(cls, path: str) -> bool:
        return True


#: TuflowFVBinaries: Global instance of the TuflowBinaries class. See :class:`TuflowBinaries` for class information.
tuflowfv_binaries = TuflowFVBinaries()


def register_tuflowfv_binary(version_name: str, version_path: 'PathLike') -> None:
    """Register (save) a TUFLOW binary version path. Versions saved via this method will take precedence over versions
    found in registered folders :func:`register_tuflow_binary_folder <pytuflow.util.register_tuflow_binary_folder>`.

    Parameters
    ----------
    version_name : str
        Name of the TUFLOW binary version e.g. '2023-03-AE'
    version_path : PathLike
        Path to the TUFLOW binary executable
    """
    tuflowfv_binaries.user_bin_locations[version_name] = str(version_path)
    tuflowfv_binaries.save_tuflow_settings_cache()
    logger.info('New TUFLOW binary registered: {} - {}'.format(version_name, version_path))


def register_tuflowfv_binary_folder(folder: 'PathLike') -> None:
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
    if folder not in tuflowfv_binaries.user_folders:
        tuflowfv_binaries.user_folders.append(folder)
        logger.info('New TUFLOW binary folder registered: {}'.format(folder))
        tuflowfv_binaries.save_tuflow_settings_cache()
