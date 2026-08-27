from PyInstaller.utils.hooks import collect_all


print('<<<< collecting hook data >>>>>>')
_, _, hiddenimports = collect_all('fm_to_estry.converters')
_, _, hiddenimports_ = collect_all('fm_to_estry.parsers.units')
hiddenimports.extend(hiddenimports_)
