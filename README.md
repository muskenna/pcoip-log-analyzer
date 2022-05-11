# pcoip-log-analyzer
Tool for analyzing PCoIP client and agent logs and generate a diagnostic report
It accept text files and compressed file (Linux and Windows)

Requirements
    They are described in the requirements file and can be installed automatically using the following command line:
        `pip install -r requirements`
Command-line arguments
    Required: `--filePath`
    Optional: `--debug`

How to execute the script from the command line
    `'..\loganalyzer\main.py' '--filePath=C:\ProgramData\Teradici\Support\supportbundle-client-2022-05-11T085247Z.zip, C:\ProgramData\Teradici\Support\supportbundle-client-2022-05-11T085247Z.tar.gz, C:\Users\usr\AppData\Local\Teradici\PCoIPClient\logs\pcoip_client_2022_03_08T22_36_45Z_00003e98.txt' '--debug'`

