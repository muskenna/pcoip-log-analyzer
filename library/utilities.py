import os
import shutil
import stat
import json
import zipfile
import hashlib
import logging
import tempfile
import datetime
import time
from io import BytesIO
import subprocess
from pathlib import Path
logger = logging.getLogger('main')
def measureExecution(function):
    def timed(*args, **kw):

        startTime = time.time()
        result = function(*args, **kw)
        endTime = time.time()
        executionTime = int((endTime - startTime) * 1000)
        if 'log_time' in kw:
            name = kw.get('log_name', function.__name__.upper())
            kw['log_time'][name] = executionTime
        else:
            logger.debug(
                f'>>> Function {function.__name__} finished executing in {str(executionTime)} ms <<<')

        return result

    return timed

def extractFileContent(f, reverse):
    fileContent = ""

    try:
        if reverse:
            content = f.readlines()
            content.reverse()
            fileContent = ''.join(content)
        else:
            fileContent = f.read()
        return fileContent

    except:
        pass


def getJson(path):
    jdata = None
    if os.path.exists(path):
        with open(path, 'r') as jf:
            try:
                jdata = json.load(jf)
            except:
                logger.error(f'*** exception handling: {path}')
                raise
    else:
        logger.warning(f"getJson: The json file {path} does not exists.")
    return jdata


def getDictHash(dictData: dict):
    dhash = hashlib.md5()
    encoded = json.dumps(dictData, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()


def getValidFilePath(filePath: str):

    if not isinstance(filePath, str):
        raise TypeError('The file path must be an string')

    filePaths = []
    paths = filePath.split(',')
    if paths:
        for path in paths:
            path = path.strip()
            if os.path.isfile(path) or os.path.isdir(path):
                filePaths.append(path)
    else:
        if os.path.isfile(filePath) or os.path.isdir(filePath):
            filePath = filePath.strip()
            filePaths.append(filePath)

    return filePaths


def getFileContent(filePath: str, reverse: bool):
    if os.path.isfile(filePath):

        # Used for reading different encoded files, read the first and last time to find the session duration from the time stamps
        with open(filePath, 'r', encoding='utf-8', errors='ignore') as f:
            try:
                fileContent = extractFileContent(f, reverse)
            except:
                with open(filePath, 'r', errors='ignore') as f:
                    fileContent = extractFileContent(f, reverse)

        return fileContent


def getAggregatedLists(firstList: list, secondList: list) -> dict:
    '''
    Aggregated two lists into dict

    Return dict
    :param firstList: list of value
    :param secondList: list of value
    '''
    # Lists must be of the same length, otherwise, the list with the least items decides the length of the dict
    aggregatedLists = {}
    if len(firstList) > 0 and len(firstList) == len(secondList):
        aggregatedLists = dict(zip(firstList, secondList))

    return aggregatedLists


def setLog(message: str, type: str):

    if type == 'info':
        logger.info(f'{datetime.datetime.utcnow().isoformat()}: {message}')
    if type == 'warning':
        logger.warning(f'{datetime.datetime.utcnow().isoformat()}: {message}')
    if type == 'error':
        logger.error(f'{datetime.datetime.utcnow().isoformat()}: {message}')


def get7zpath():
    rootDir = Path(os.path.realpath(__file__)).parent.parent
    return os.path.join(rootDir, 'ext/7zz' if str(rootDir).replace('\\', '/').startswith('/home/site/wwwroot') else 'ext/7z.exe')


def formalizeArchive(filePath: str):
    ''' Test real archive type, and if needed, make a copy with file extension to reflect its type,
        which does matter to ensure proper handling of the archive.
        :return: new file path, and its file extension.
    '''
    fileExt = Path(filePath).suffix
    exePath = get7zpath()
    try:
        testArchive = subprocess.run(f'{exePath} t {filePath}', shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        if b'Type = gzip' in testArchive:
            fileExt = '.tar.gz'
        if b'Type = bzip2' in testArchive:
            fileExt = '.tar.bz2'            
        elif b'Type = tar' in testArchive:
            fileExt = '.tar'
        elif b'Type = zip' in testArchive:
            fileExt = '.zip'
    except Exception as e:
        logger.error(f'subprocess exception: {e}')
        newFilePath = filePath

    if fileExt is not None:
        newFilePath = os.path.realpath(filePath).replace(fileExt, '').replace('.gz', '').replace('.tar', '').replace('.zip', '') + fileExt
        if os.path.realpath(newFilePath) != os.path.realpath(filePath):
            newFilePath = shutil.copy2(filePath, newFilePath)

    return (newFilePath, fileExt)


def getArchiveFile(diagnosticReports: list):
    """
    Add the given files into a zip file in memory
    :param files: a map of file name to its content
    :return: The binary data of the result zip file.
    """
    if len(diagnosticReports) == 0:
        notFoundMessage = '<html><body><p>There was no log found in the provided files.</p><p>The analysis tool is currently compatible with log files on the following products:</p><ul><li>PCoIP Software Client (Windows, Linux, MacOS)</li><li>PCoIP Host (Standard Agent or Graphics Agent on Windows, Linux, or macOS)</li><li>See <a href="https://help.teradici.com/s/article/1093">here</a> for how to create and submit the support bundles.</li></ul><p>The following Teradici product are not yet compatible with the analysis tool</p><ul><li>PCoIP CAS-M</li><li>PCoIP Connection Manager</li><li>PCoIP Security Gateway</li><li>PCoIP License Server</li><li>PCoIP Connection Broker</li><li>Zero Client</li><li>Remote Workstation Card</li></ul></body></html>'
        diagnosticReports.append(
            {"fileName": "NoLogFound.html", "content": notFoundMessage})

    dataBytes = BytesIO()
    with zipfile.ZipFile(dataBytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zipFile:
        
        for diagnosticReport in diagnosticReports:
        
            fileName = diagnosticReport['fileName']
            fileContent = diagnosticReport['content']
            
            logger.info(f'Generating archive file based on the diagnostic content of the file {fileName}')

            if not (fileContent or fileName):
                message = f'The diagnost report object does not contain file name and content'
                logger.error(message)
                raise ValueError(message)
            
            zipFile.writestr(fileName, fileContent)

    return dataBytes.getvalue()


def rmtree_error_handler(func, path, exc_info):
    '''
    Error handler for ``shutil.rmtree``.
    If the error is due to an access error (read only file) it attempts to add write permission and then retries.
    If the error is for another reason it re-raises the error.
    Usage : ``shutil.rmtree(path, onerror=rmtree_errorhandler)``
    '''
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise Exception('Error is not an access error')

def delete_dir(working_directory):
    '''
    Deletes the working directory
    :returns: void
    '''

    if os.path.isdir(working_directory):
        shutil.rmtree(working_directory, onerror=rmtree_error_handler)
        logger.info(f'Successfully deleted working directory: {working_directory}')
    else:
        logger.warning(f'Working directory does not exist, or has already been deleted: {working_directory}')

