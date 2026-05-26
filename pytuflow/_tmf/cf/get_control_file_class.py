from pathlib import Path

from . import tcf, tgc, ecf, tbc, qcf, tef, tesf, toc, trd, trfc, tscf, adcf, cf_build_state


def get_control_file_class(fpath: str | Path) -> type[cf_build_state.ControlFileBuildState]:
    if isinstance(fpath, str):
        fpath = Path(fpath)
    if fpath.suffix.lower() in ['.tcf', '.2cf']:
        return tcf.TCF
    elif fpath.suffix.lower() == '.tgc':
        return tgc.TGC
    elif fpath.suffix.lower() == '.ecf':
        return ecf.ECF
    elif fpath.suffix.lower() == '.tbc':
        return tbc.TBC
    elif fpath.suffix.lower() == '.qcf':
        return qcf.QCF
    elif fpath.suffix.lower() == '.tef':
        return tef.TEF
    elif fpath.suffix.lower() == '.tesf':
        return tesf.TESF
    elif fpath.suffix.lower() == '.toc':
        return toc.TOC
    elif fpath.suffix.lower() == '.trd':
        return trd.TRD
    elif fpath.suffix.lower() in ['.trfc', '.trfcf']:
        return trfc.TRFC
    elif fpath.suffix.lower() == '.tscf':
        return tscf.TSCF
    elif fpath.suffix.lower() == '.adcf':
        return adcf.ADCF

    raise ValueError(f'Unsupported or unrecognised control file with extension {fpath.suffix}.')
