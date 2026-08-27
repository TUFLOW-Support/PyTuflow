from pathlib import Path
import sys
import logging

import pytest

from ...pytuflow._tmf import TCF, TGC, TBC


def test_logging_setup(caplog):
    
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\nGeometry Control File == ../some_control_file.tgc\n')
    try:
        # Default should be WARNING (> INFO)
        tcf = TCF(p)
        for record in caplog.records:
            assert(record.levelno > logging.INFO)

        # Message for no TGC is ERROR (< CRITICAL)
        caplog.clear()
        tcf = TCF(p, log_level='CRITICAL')
        for record in caplog.records:
            assert(record.levelno > logging.ERROR)

        # Should have INFO level messages
        caplog.clear()
        tcf = TCF(p, log_level='INFO')
        messages = [
            rec.message for rec in caplog.records if rec.levelno == logging.INFO
        ]
        assert len(messages) > 0
    except Exception as e:
        raise e
    finally:
        p.unlink()
        

def test_logging_setup_to_file_with_name(caplog):
    p = Path(__file__).parent / 'test_control_file.tcf'
    log_p = Path(__file__).parent / 'pytuflow_logs.log'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\nGeometry Control File == ../some_control_file.tgc\n')
    try:
        tcf = TCF(p, log_to_file=log_p)
        assert log_p.exists()

        lines = []
        with log_p.open('r') as f:
            lines = f.readlines()
        assert len(lines) > 2

        for record in caplog.records:
            assert(record.levelno > logging.INFO)
        
    except Exception as e:
        raise e
    finally:
        p.unlink()
        logging.getLogger('pytuflow').handlers.clear() # Remove log handler ownership before deleting!
        log_p.unlink()


def test_logging_setup_to_file_with_folder(caplog):
    p = Path(__file__).parent / 'test_control_file.tcf'
    log_p = Path(__file__).parent
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\nGeometry Control File == ../some_control_file.tgc\n')
    try:
        tcf = TCF(p, log_to_file=log_p)
        assert log_p.exists()

    except Exception as e:
        raise e
    finally:
        p.unlink()
        logging.getLogger("pytuflow").handlers.clear() # Remove log handler ownership before deleting!
        log_p = log_p.joinpath("pytuflow_logs.log")
        log_p.unlink()
