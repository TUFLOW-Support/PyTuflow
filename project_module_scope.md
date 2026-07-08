# Requirements for pytuflow.project module

## Basic overview of what the module should be able to do

- Create a new TUFLOW HPC project from scratch
    - The project can be bare bones or include additional modules
- Insert modules into an existing project
    - e.g. insert Quadtree, AD control files and commands
    - e.g. insert infiltration commands (soil commands) into a control file (this is not a TUFLOW module, but should be treated as such in this python module)

## More details on how the module should work

- The project control files should be based on template control files
- The templates should be customisable by the user
    - variables and directives can be used to help the script do more complicated actions
    - feel free to include things like loop expansion e.g. for map output commands, these commands are dynamic based on which formats the users wants to use
    - The tool should still be able to operate without directives etc. pytuflow classes (e.g. pytuflow.TCF) can be used to help find good locations to insert commands if directives are not found
    - I think doing something like having the base templates copied into a cache directory the first time the tool is run and then the user can modify them freely
- Defaults should also be modifiable. 
- Defaults don't neccessarily need to be values, e.g. for something like cell size, if the user does not choose a value, then a default value of "<cell size>  ! TODO populate with an appropriate cell size for your model" can be used to mark a spot the user will be required to fill in prior to running. Sometimes this is preferable than choosing a value since it is not up to the tool to decide what a given model's cell size is.

## Template files

- Example template files are within "example_control_File_templates/hpc"
- The templates contain variables already, but feel free to modify and add directives as needed
- Modules are:
    - Events
    - Estry
    - Quadtree
    - Soils
    - AD
    - Operational controls (TOC)
    - Rainfall control file (rf)

## How this tool should be run

- The tool should be able to run with a python script
- The tool should be able to run via the command line e.g. `python -m ...`

## Other

- The framework should be modular enough to enable a similar setup for TUFLOW FV in the future

## Addendum

- Modules may contain multiple commands, or even blocks of commands. These blocks could be placed in different locations or different control files. E.g. the 'soils' module will generate a command in the TCF with the soils.tsoilf, and I would like it to also add soil commands in the TGC file (e.g. Set Soil == 1). Each module should also have a json file, that is cached for customisation by the user, that sets the command block(s) and each block can be multiple commands. Command blocks that are not associated with the control file can be appended to the bottom of the control file.