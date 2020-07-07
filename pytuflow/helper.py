"""
 --------------------------------------------------------
        tuflowqgis_library - tuflowqgis operation functions
        begin                : 2013-08-27
        copyright            : (C) 2013 by Phillip Ryan
        email                : support@tuflow.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from math import floor
from datetime import timedelta


def getPathFromRel(dir, relPath, **kwargs):
    """
    return the full path from a relative reference

    :param dir: string -> directory
    :param relPath: string -> relative path
    :return: string - full path
    """

    outputDrive = kwargs['output_drive'] if 'output_drive' in kwargs.keys() else None
    variables_on = kwargs['variables_on'] if 'variables_on' in kwargs else False
    
    _components = relPath.split(os.sep)
    components = []
    for c in _components:
        components += c.split('\\')
    path = dir
    
    if outputDrive:
        components[0] = outputDrive
    
    for c in components:
        if c == '..':
            path = os.path.dirname(path)
        elif c == '.':
            continue
        else:
            found = False
            for p in os.walk(path):
                for d in p[1]:  # directory
                    if c.lower() == d.lower():
                        path = os.path.join(path, d)
                        found = True
                        break
                if found:
                    break
                for f in p[2]:  # files
                    if c.lower() == f.lower():
                        path = path = os.path.join(path, f)
                        found = True
                        break
                if found:
                    break
                # not found if it reaches this point
                path = os.path.join(path, c)
                break
    
    return path


def getOSIndependentFilePath(dir, folders):
    """
    Returns a case sensitive file path from a case insenstive file path. Assumes dir is already correct.
    
    :param dir: str full path to working directory
    :param folders: str or list -> subfolders and file
    :return: str full case sensitive file path
    """
    
    if type(folders) is list:
        folders = os.sep.join(folders)
        
    return getPathFromRel(dir, folders)


def roundSeconds(dateTimeObject, prec):
    """rounds datetime object to nearest second"""

    newDateTime = dateTimeObject

    a = 500000  # 0.5s
    b = 1000000  # 1.0s
    if prec > 0:
        a = a / (10 ** prec)
        b = b / (10 ** prec)
    ms = newDateTime.microsecond - floor(newDateTime.microsecond / b) * b
    if ms >= a:
        newDateTime = newDateTime + timedelta(microseconds=b)

    return newDateTime - timedelta(microseconds=ms)

    

if __name__ == '__main__':
    a = r"C:\TUFLOW\Tutorial_Data_QGIS\Tutorial_Data_QGIS\QGIS\Complete_Model\tuflow\results"
    b = r"..\model\<<module>>_<<cell_size>>_001.tgc"
    v = {'module': ['M03'], 'cell_size': ['5m']}
    s = ['M03']
    e = []
    c = ['<<module>>', '<<~s1~>>', '<<~s2~>>']
    hours = 1.5
    
    #combinations = getVariableCombinations(c, v, s, e)
    #for c in combinations:
    #print(c)
    
    #folders = getAllFolders(a, b, v, s, e)
    #for folder in folders:
    #	print(folder)
    #0.003750000149011612
    print(convertHoursToTime(0.00375))
    