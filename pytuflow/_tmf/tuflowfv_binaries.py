from .tuflow_binaries import TuflowBinaries


class TuflowFVBinaries(TuflowBinaries):
    WINDOWS_BIN_NAME = 'TUFLOW_iSP_w64'
    LINUX_BIN_NAME = ''
    NAME = 'tuflowfv'
    STANDARD_LINUX_LOCATIONS = ('/opt/tuflowfv',)

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
