@echo off
python -c "import sys; from fief.cli.main import main; sys.exit(main())" %*
if exist %HOME%\.config\fiefexport.bat (
    %HOME%\.config\fiefexport.bat
	del %HOME%\.config\fiefexport.bat 
) else (
    REM pass
)