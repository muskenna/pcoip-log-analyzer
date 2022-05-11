
'''
    Document: a computer file containing information input by a computer user and usually created with an application
'''


import bz2
import gzip
from io import BytesIO
import re
import os
import logging
from sys import path
import tarfile
from zipfile import ZipFile

from shutil import copyfileobj, copyfile
from .utilities import getFileContent, formalizeArchive, measureExecution
logger = logging.getLogger('main')
class FileCategorizer():

    def __init__(self, filePath: str, fileTypes: dict, workingDirectory):
        self.filePath = filePath
        #self.contentTypes = contentTypes
        self.fileTypes = fileTypes
        self.workingDirectory = workingDirectory
        self.categorizedFiles = {}

        if not self.fileTypes:
            raise Exception(
                "Signatures for content type maching must be provided")        

    def __getFileFormat(self) -> str:
        '''
            It finds the document format using mime and return a type, which is usually the file extension, but not necessarily.
            If a file witout extension is provided it will be able to find the format anyway

        '''
        filetype = None

        if re.match(".*\\.txt", self.filePath):
            filetype = 'text'

        if re.match(".*\\.zip", self.filePath):
            filetype = 'zip'

        if re.match(".*\\.tar(?:\\.gz|\\.bz2)?$", self.filePath):
            filetype = 'tar'

        # archives without extension etc.
        if not filetype:
            (__newFilePath, archiveTypebyContent) = formalizeArchive(self.filePath)

            if archiveTypebyContent:
                if 'zip' in archiveTypebyContent:
                    filetype = 'zip'
                if 'tar' in archiveTypebyContent:
                    filetype = 'tar'
                if 'text' in archiveTypebyContent or 'txt' in archiveTypebyContent or 'log' in archiveTypebyContent:
                    filetype = 'text'

        logger.debug(f'The file formart is {filetype}')

        return filetype

    def __getFileType(self, fileName='') -> dict:

        logger.debug(f'Defining file type -> [{fileName}]')
        isMergeEnabled = False

        if fileName:
            for filenameSignature, fileTypeProperties in self.fileTypes.items():
                if 'componentType' in fileTypeProperties and 'contentType' in fileTypeProperties:
                    componentType = fileTypeProperties['componentType']
                    contentType = fileTypeProperties['contentType']
                    if 'mergeFiles' in fileTypeProperties and isinstance(fileTypeProperties['mergeFiles'], bool) and fileTypeProperties['mergeFiles']:
                        isMergeEnabled = True
                    if re.match(filenameSignature, fileName):
                        return {"fileName": fileName, "componentType": componentType, "contentType": contentType, 'merge': isMergeEnabled}
        return {}
    
    # def __getContentType(self, fileContent='', fileName='') -> dict:

    #     logger.debug(f'Defining file type -> [{fileName}]')
    #     isMergeEnabled = False

    #     if not fileContent:
    #         return {}

    #     if not self.contentTypes:
    #         raise Exception(
    #             "Signatures for content type maching must be provided")

    #     if fileName:
    #         for filenameSignature, fileTypeProperties in self.fileTypes.items():
    #             if 'componentType' in fileTypeProperties and 'contentType' in fileTypeProperties:
    #                 componentType = fileTypeProperties['componentType']
    #                 contentType = fileTypeProperties['contentType']
    #                 if 'merge' in fileTypeProperties and isinstance(fileTypeProperties['merge'], bool) and fileTypeProperties['merge']:
    #                     isMergeEnabled = True
    #                 if re.match(filenameSignature, fileName):
    #                     return {"fileName": fileName, "componentType": componentType, "contentType": contentType, 'merge': isMergeEnabled}
        # if fileContent:
        #     for product in self.contentTypes['products']:
        #         for productName, contentTypes in product.items():
        #             for contentType in contentTypes:
        #                 signature = contentType['signature']
        #                 contentTypeName = contentType['contentType']

        #                 if re.search(signature, fileContent):
        #                     return {"product": productName, "contentType": contentTypeName}

        return {}

    def __setFileCategory(self, fileCategory: dict):

        if isinstance(fileCategory, dict) == False and 'fileName' not in fileCategory and 'componentType' not in fileCategory and 'contentType' not in fileCategory and 'merge' not in fileCategory and not fileCategory:
            logger.error(
                'The file category object is invalid for file categorization')

        componentType = fileCategory['componentType']
        contentType = fileCategory['contentType']
        fileName = fileCategory['fileName']
        isMergeEnabled = fileCategory['merge']

        logger.debug(
            f'File tagged:  Tags -> [componentType: {componentType}, contentType: {contentType}], File name -> [{fileName}]')

        if fileName and contentType and componentType:

            if 'files' not in self.categorizedFiles:
                self.categorizedFiles['files'] = []

            category = {'fileName': fileName,
                        'contentType': contentType,
                        'isMergeEnabled': isMergeEnabled}

            self.categorizedFiles['componentType'] = componentType
            self.categorizedFiles['files'].append(
                category)
        else:
            logger.error(
                f'A file categorization cannot be created because one of the following values is missing: file name, content type, or component type')

    def __concatenateFilesOfSameType(self):

        updatedCategorizedFiles = []
        categorizedFiles = self.categorizedFiles['files']
        for key, value in self.fileTypes.items():
            if 'mergeFiles' in value and isinstance(value['mergeFiles'], bool) and value['mergeFiles']:
                isFirstEntryRecorded = False
                fileSignatures = key.split('|')
                destinationFileName = value['contentType'] + '.merge'
                destinationFile = os.path.join(
                    self.workingDirectory, destinationFileName)

                with open(destinationFile, 'w') as outfile:
                    for fileSignature in fileSignatures:
                        for categorizedFile in categorizedFiles:
                            if re.match(fileSignature, categorizedFile['fileName']):
                                sourceFile = os.path.join(
                                    self.workingDirectory, categorizedFile['fileName'])
                                with open(sourceFile) as infile:
                                    for line in infile:
                                        outfile.write(line)
                                if not isFirstEntryRecorded:
                                    categorizedFile['fileName'] = destinationFileName
                                    updatedCategorizedFiles.append(
                                        categorizedFile)
                                    isFirstEntryRecorded = True
                logger.debug(f'Same category files merged into the file: {destinationFile}')                                    
        #Reset list
        categorizedFiles = []
        for index in range(len(self.categorizedFiles['files'])):
            if 'isMergeEnabled' not in self.categorizedFiles['files'][index] or ('isMergeEnabled' in self.categorizedFiles['files'][index] and not self.categorizedFiles['files'][index]['isMergeEnabled']):
                categorizedFiles.append(self.categorizedFiles['files'][index])

        categorizedFiles.extend(updatedCategorizedFiles)
        self.categorizedFiles['files'] = categorizedFiles

    @measureExecution
    def getCategorizedFiles(self) -> dict:
        '''
            Description:
                It take a file path and return a dict containing the component type (agent, client, etc) and categorized files
            Returns:
                dict: self.categorizedFiles
        '''
        if os.path.isfile(self.filePath):
            logger.debug(
                f'Starting file categorization with file {self.filePath}')
        if os.path.isdir(self.filePath):
            logger.debug(
                f'Starting file categorization with directory {self.filePath}')

        if self.filePath:
            if not (os.path.isfile(self.filePath) or os.path.isdir(self.filePath)):
                raise FileNotFoundError(
                    f"The directory or file path '{self.filePath}' does not exist")

        # Read content file directly
        if os.path.isfile(self.filePath):

            documentFormat = self.__getFileFormat()

            if documentFormat == 'text':
                #https://stackoverflow.com/questions/41659811/get-basename-of-a-windows-path-in-linux
                fileName = os.path.basename(self.filePath.replace('\\',os.sep))

                if re.match('.*(\\.txt|\\.log|\\.out)', fileName):

                    fileContent = getFileContent(self.filePath, False)

                    contentType = self.__getFileType(fileName)
                    if isinstance(contentType, dict) and len(contentType) > 0:

                        try:
                            dst = os.path.join(self.workingDirectory, fileName)
                            copyfile(self.filePath, dst)
                        except IOError as err:
                            logger.error(
                                f'Copy file {self.filePath} to folder {self.workingDirectory} failed.\nIO operation error: {err.strerror}')

                        self.__setFileCategory(contentType)
                    else:
                        logger.debug(f'File not tagged: [{fileName}]')

            if documentFormat == 'zip':

                with ZipFile(self.filePath, 'r') as zipFile:

                    for zipFileName in zipFile.namelist():
                        if re.match('.*(\\.txt|\\.log|\\.out)', zipFileName):
                            #https://stackoverflow.com/questions/41659811/get-basename-of-a-windows-path-in-linux
                            fileName = os.path.basename(zipFileName.replace('\\',os.sep))

                            # skip directories
                            if not fileName:
                                continue

                            fileContent = zipFile.read(zipFileName)

                            try:
                                # If file content is not text skip
                                fileContent = fileContent.decode("utf-8")
                            except:
                                continue

                            contentType = self.__getFileType(fileName)

                            # Content successfully classified
                            if isinstance(contentType, dict) and len(contentType) > 0:

                                source = zipFile.open(zipFileName)
                                target = open(os.path.join(
                                    self.workingDirectory, fileName), "wb")

                                try:
                                    with source, target:
                                        copyfileobj(source, target)
                                except IOError as err:
                                    logger.error(
                                        f'Copy file {fileName} from zip file to folder {self.workingDirectory} failed.\nIO operation error: {err.strerror}')

                                self.__setFileCategory(contentType)
                            else:
                                logger.debug(f'File not tagged: [{fileName}]')

            if documentFormat == 'tar':
                # TarFile reads .tar, .gzip and .bz2
                with tarfile.open(self.filePath) as tarFile:
                    for tfMember in tarFile.getmembers():
                        #https://stackoverflow.com/questions/41659811/get-basename-of-a-windows-path-in-linux
                        fileName = os.path.basename(tfMember.name.replace('\\',os.sep))

                        # isreg()  as same as isfile
                        if tfMember.isfile():
                            if re.match('.*(\\.txt|\\.out|\\.err|\\.log.?\\d?|\\.bz2|\\.gz)$', fileName):

                                tfInfo = tarFile.extractfile(tfMember)
                                if tfInfo:
                                    fileObject = tfInfo.read()

                                    if re.match('.*(\\.txt|\\.out|\\.err|\\.log.?\\d?)$', fileName):
                                        try:
                                            fileContent = fileObject.decode(
                                                "utf-8")
                                        except:
                                            continue

                                        contentType = self.__getFileType(fileName)

                                    if re.match('.*\\.bz2', fileName):
                                        decompressFile = bz2.decompress(
                                            fileObject)
                                        fileContent = decompressFile.decode(
                                            "utf-8")

                                        contentType = self.__getFileType(fileName)

                                    if re.match('.*\\.gz', fileName):
                                        decompressFile = gzip.decompress(
                                            fileObject)
                                        fileContent = decompressFile.decode(
                                            "utf-8")

                                        contentType = self.__getFileType(fileName)

                                    if isinstance(contentType, dict) and len(contentType) > 0:

                                        if re.match('.*(\\.txt|\\.out|\\.err|\\.log)', fileName):
                                            tfMember.name = fileName
                                            try:
                                                tarFile.extract(
                                                    tfMember, self.workingDirectory)
                                            except IOError as err:
                                                logger.error(
                                                    f'Copy file {fileName} from tar file to folder {self.workingDirectory} failed.\nIO operation error: {err.strerror}')

                                        if re.match('.*(\\.bz2|\\.gz)', fileName):

                                            fileName = re.sub(
                                                r'.bz2|.gz', '.log', fileName)

                                            target = open(os.path.join(
                                                self.workingDirectory, fileName), "wb")

                                            try:
                                                with target:
                                                    target.write(
                                                        decompressFile)
                                            except IOError as err:
                                                logger.error(
                                                    f'Copy file {fileName} from bz2 file to folder {self.workingDirectory} failed.\nIO operation error: {err.strerror}')

                                        self.__setFileCategory(contentType)

                                    else:
                                        logger.debug(
                                            f'File not tagged: [{fileName}]')

        # List files from a directory and then read file content
        if os.path.isdir(self.filePath):

            for (dirPath, _dirNames, fileNames) in os.walk(self.filePath, topdown=False):
                for fileName in fileNames:
                    fileFullPath = os.path.join(dirPath, fileName)

                    if re.match('.*(\\.txt|\\.log|\\.out|\\.err)', fileName):
                        fileContent = getFileContent(fileFullPath, False)

                        contentType = self.__getFileType(fileName)

                        if isinstance(contentType, dict) and len(contentType) > 0:

                            try:
                                dst = os.path.join(
                                    self.workingDirectory, fileName)
                                copyfile(fileFullPath, dst)
                            except IOError as err:
                                logger.error(
                                    f'Copy file {fileFullPath} to folder {self.workingDirectory} failed.\nIO operation error: {err.strerror}')

                            self.__setFileCategory(contentType)

                        else:
                            logger.debug(f'File not tagged: [{fileName}]')

        if self.categorizedFiles:
            self.__concatenateFilesOfSameType()
            # self.categorizedFiles['files'] = sorted(
            #     self.categorizedFiles['files'], key=lambda ct: ct['contentType'])

        return self.categorizedFiles
