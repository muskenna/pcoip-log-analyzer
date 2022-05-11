import os
import logging
import argparse
import traceback
from dotenv import load_dotenv
import webbrowser
import tempfile
from datetime import datetime

try:
    from .library.utilities import getValidFilePath, delete_dir
    from .library.diagnostic import DiagnosticEngine, DiagnosticEngineThread
    from .library.logger import getCustomLogger, setCustomLoggerLevel
except:
    from library.utilities import getValidFilePath, delete_dir
    from library.diagnostic import DiagnosticEngine, DiagnosticEngineThread
    from library.logger import getCustomLogger, setCustomLoggerLevel

logger = getCustomLogger()

def runDiagnosticProcessing(filePaths: list = []):

    level = logging.getLevelName(logger.getEffectiveLevel())
    debug = level == 'DEBUG'

    logger.info(' ## Starting diagnostic process ##')

    parentWorkingDirectory = tempfile.mkdtemp()

    if not isinstance(filePaths, list):
        message = 'The file paths must be a list'
        logger.error('The file paths must be a list')
        raise TypeError(f'{message}')

    currentDirectory = os.path.dirname(os.path.realpath(__file__))
    configDirectory = os.path.join(currentDirectory, 'config')

    diagnosticPool = []
    for filePath in filePaths:
        diagnosticEngine = DiagnosticEngine(filePath, configDirectory, parentWorkingDirectory) if debug else DiagnosticEngineThread(filePath, configDirectory, parentWorkingDirectory)
        diagnosticPool.append(diagnosticEngine)

    # start all threads first
    for diagnosticEngine in diagnosticPool:

        if debug:
            diagnosticEngine.run()
        else:
            diagnosticEngine.start()

    # wait for all threads to finish
    if not debug:
        for diagnosticEngine in diagnosticPool:
            diagnosticEngine.join()

    diagnosticReports = []
    localReportNameToFileName = {}

    for diagnosticEngine in diagnosticPool:

        #For local execution, a file name or directoy can be passed as command argument
        fileName = diagnosticEngine.getSourceFile()

        if not fileName:
            timeStamp = datetime.today().strftime('%Y%m%d%H%M%S%M')
            fileName = f'report-{timeStamp}.dir'

        if os.path.isfile(diagnosticEngine.filePath):
            logger.info(
                f'Requesting diagnostic report with file {diagnosticEngine.filePath}')
        if os.path.isdir(diagnosticEngine.filePath):
            logger.info(
                f'Requesting diagnostic report with directory {diagnosticEngine.filePath}')

        content = diagnosticEngine.getDiagnosticReport()
        if fileName and content:
            
            # get original log file name
            reportFileName = 'report.html'
            report = {"fileName": reportFileName, "content": content}

            localReportNameToFileName[reportFileName] = fileName
            
            diagnosticReports.append(report)
            logger.info(
                f'Report file: "{reportFileName}" -> Source file: {fileName}')


    reportDirectory = None
    for diagnosticReport in diagnosticReports:
        # make local report dir persistent for viewing, separate from 'parentWorkingDirectory'
        reportDirectory = os.path.join(tempfile.gettempdir(), 'teralogreports')
        #report folder deletion needs review because it is deleting reports generated from directory path
        delete_dir(reportDirectory) # clean up old reports
        try:
            os.mkdir(reportDirectory)
        except IOError as err:
            logger.error(
                f"Cannot create report directory '{reportDirectory}'.\nIO operation error: {err.strerror}")

        reportFileName = diagnosticReport['fileName']
        reportFileTarget = os.path.join(reportDirectory, reportFileName)
        with open(reportFileTarget, "a+") as fTarget:
            fileContent = diagnosticReport['content']
            # Need to handle the following error that will occur if mixed encoding is found. In this case, Roman alphabet and Chinese
            # Exception has occurred: UnicodeEncodeError       (note: full exception trace is shown but execution is paused at: <module>)
            # 'charmap' codec can't encode characters in position 10131-10146: character maps to <undefined>
            fTarget.write(fileContent)
        webbrowser.open_new_tab(reportFileTarget)

        # local test sending reports back to Salesforce

        if reportDirectory:
            message = f"Diagnostic reports directory: {reportDirectory}"
        else:
            message = f"There is not diagnostic records, because the input provided does not contain relevant information"
        
        logger.info(message)

    # clean up temp dir
    delete_dir(parentWorkingDirectory)


if __name__ == "__main__":

    '''
    This is the entry poing for IDEs, like VS Code, and future executable that can be generated for distribution

    '''

    # .env not working: https://github.com/microsoft/vscode-python/issues/9358,
    # workaround to use dotenv module
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument('--filePath', type=str, help='File path to an archive or text file')
    # simply use '--debug' without argument value to enable debugging, or absent to disable debugging by default
    parser.add_argument('--debug', default=False, action='store_true', help='For development purpose')
    args = parser.parse_args()
    filePaths = getValidFilePath(args.filePath)

    setCustomLoggerLevel(logger, 'DEBUG' if args.debug else 'INFO')
    logger.info(f"Processing file: Name: {filePaths}")
    
    try:
        runDiagnosticProcessing(filePaths=filePaths)
    except Exception as err:
        logger.error(f'Failed to process the diagnostic report. Check the tracebacl below:')
        logger.error(traceback.format_exc())
