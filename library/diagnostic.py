import os
import re
import math
import random
import string
import logging
from typing import Union
from threading import Thread
from datetime import datetime
from bs4 import BeautifulSoup

from .content import FileCategorizer
from .parser import getParsedSignatureGroups
from .utilities import getJson, getFileContent, getDictHash, measureExecution

logger = logging.getLogger('main')


class _ContinueINOuterLoop(Exception):
    '''
        This class is used to break outer loop
    '''
    pass


class DiagnosticEngine():
    ''' Non-thread class for logger.purpose. Thread class DiagnosticEngineThread wrapped at the bottom. '''

    tokenizedFiles = []
    diagnosticReportContent = {}
    diagnosticRecords = []
    diagnosticTimeSpan = {}
    productTypeName = ''
    productVersionNumber = ''  # MAJOR.MINOR.PATCH

    def __init__(self, filePath: str, configDirectory: str, parentWorkingDirectory: str):

        self.filePath = filePath
        self.configDirectory = configDirectory
        self.parentWorkingDirectory = parentWorkingDirectory
        uniqueDirectoryName = ''.join(random.choice(
            string.ascii_lowercase) for i in range(10))
        self.workingDirectory = os.path.join(
            self.parentWorkingDirectory, uniqueDirectoryName)

    def run(self):

        if os.path.isfile(self.filePath):
            logger.info(
                f'Diagnostic engine started with file {self.filePath}')
        if os.path.isdir(self.filePath):
            logger.info(
                f'Diagnostic engine started with file with directory {self.filePath}')

        try:
            os.mkdir(self.workingDirectory)
            logger.debug(
                f"Working directory '{self.workingDirectory}' created")
        except IOError as err:
            logger.error(
                f"Cannot create directory '{self.workingDirectory}'.\nIO operation error: {err.strerror}")

        # contentTypeConfigFile = os.path.join(
        #     self.configDirectory, 'contentTypes.json')

        fileTypeConfigFile = os.path.join(
            self.configDirectory, 'fileTypes.json')

        # contentTypes = getJson(contentTypeConfigFile)
        fileTypes = getJson(fileTypeConfigFile)

        # contentTypesKeys = [list(x.keys())[0]
        #                     for x in contentTypes['products']]

        # logger.debug(f"Content types: {', '.join(contentTypesKeys)}")

        fileCategorizer = FileCategorizer(
            self.filePath, fileTypes, self.workingDirectory)
        categorizedFiles = fileCategorizer.getCategorizedFiles()

        if categorizedFiles:

            componentType = categorizedFiles['componentType']
            #documentsClassification = categorizedFiles['files']

            workingDirectoryFiles = os.listdir(self.workingDirectory)
            if workingDirectoryFiles:

                self.tokenizedFiles = self.__getParsedFile(
                    self.workingDirectory, componentType, categorizedFiles['files'])

                self.diagnosticRecords = self.__getDiagnosticRecords(
                    componentType, categorizedFiles['files'])

                self.diagnosticTimeSpan = self.__getDiagnosticTotalTimeSpan()

                if self.diagnosticRecords:
                    logger.info(
                        f'{len(self.diagnosticRecords)} diagnostic records generated for file/directory {self.filePath}')
                else:
                    logger.info(
                        f'No diagnostic records generated for file/directory {self.filePath}')

            else:
                logger.info(
                    f"There are not file valid files from  file/directory {self.filePath} for diagnosis in the working directory '{self.workingDirectory}'")

        else:
            logger.info(
                f"File(s) in the path {self.workingDirectory} from  file/directory {self.filePath} do(es) not contain(s) relevant information according to the definitions in the configuration directory '{self.configDirectory}'")

    def __getDiagnosticTotalTimeSpan(self):
        timetamps = []
        totalTimeSpan = {}
        timeOffSet = None
        for record in self.tokenizedFiles:
            if record['start'] != '0000-00-00T00:00:00.000Z' and record['end'] != '0000-00-00T00:00:00.000Z':
                timetamps.append(record['start'])
                timetamps.append(record['end'])

                if not timeOffSet:
                    timeOffSet = record['timeOffSet']
        timetamps.sort()

        if timetamps:
            totalTimeSpan = {
                "startTime":  timetamps[0], "endTime": timetamps[len(timetamps)-1], "timeOffSet": timeOffSet}
        return totalTimeSpan

    def __getFileTimeSpan(self, fileContent: str):

        startTime = ""
        endTime = ""
        timeSpan = {}
        searchTimeOffset = None
        searchNewer = re.search(
            "(?P<end>\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}.\\d{2}.*Z).*", fileContent)
        timeOffset = None

        if not searchTimeOffset:
            searchTimeOffset = re.search(
                ".*COMMON :local time [0-9-]+T[0-9:.]+(?P<offset>.*)", fileContent)
        # String pattern reversed
        searchOlder = re.findall(
            "^(\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}.\\d.*\dZ).*", fileContent, re.MULTILINE)
        if searchOlder:  # not empty
            startTime = searchOlder[len(searchOlder)-1]
            endTime = (searchNewer.groupdict())['end']

        if searchTimeOffset:
            timeOffset = (searchTimeOffset.groupdict())['offset']

        if startTime and endTime:
            timeSpan = {
                "start": startTime,
                "end": endTime,
                "timeOffSet": timeOffset if timeOffset else "not available"}

        return timeSpan

    @measureExecution
    def __getParsedFile(self, directoryPath: str, componentType: str, categorizedFiles: list):
        '''
            Parse/extract information from documents according with regular patterns defined by signature files
            Params:
                directoryPath [string]: location where documents were copied during file categorization time
                categorizedFiles [string]: the name of the product for data mapping
                categorizedFiles [list]: list of dict contains file name and properties for categorization
            Returns
                filesAndTokens [list]: list of token per file per diagnostic definition
        '''

        logger.debug(
            f'Starting analysis of {len(categorizedFiles)} file(s) for the component type "{componentType}"')

        filesAndTokens = []
        previousContentType = ""
        componentDirectory = os.path.join(self.configDirectory, componentType)

        for categorizedFile in categorizedFiles:

            fileName = categorizedFile['fileName']
            contentType = categorizedFile['contentType']

            if previousContentType != contentType:
                signaturesGroups = getJson(os.path.join(
                    componentDirectory, f"{contentType}.{componentType}.signatures.json"))

            if signaturesGroups:

                fullpath = os.path.join(directoryPath, fileName)
                fileContent = getFileContent(fullpath, False)

                if not fileContent:
                    logger.debug(f"The file {fullpath} does not have content")
                else:
                    logger.debug(
                        f'Parsing file {fileName}')
                    tokensGroups = getParsedSignatureGroups(
                        fileContent, signaturesGroups)

                    fileTimeSpan = self.__getFileTimeSpan(fileContent)
                    if tokensGroups:
                        if fileTimeSpan:
                            filesAndTokens.append(
                                {"fileName": fileName, "tokensGroups": tokensGroups, "start": fileTimeSpan['start'], "end": fileTimeSpan['end'], "timeOffSet": fileTimeSpan['timeOffSet']})
                        else:
                            filesAndTokens.append(
                                {"fileName": fileName, "tokensGroups": tokensGroups, "start": "0000-00-00T00:00:00.000Z", "end": "0000-00-00T00:00:00.000Z", "timeOffSet": "00:00"})

                    previousContentType = contentType
            else:
                logger.warning(
                    f"No signature groups found in the file {contentType}.{componentType}.signatures.json")

        filesAndTokens = sorted(filesAndTokens, key=lambda dt: dt['start'])

        return filesAndTokens

    def __getMergedRecords(self, diagnosticsRecords: list, diagnosticName: list) -> list:

        logger.debug(f"Merging '{diagnosticName}' diagnostic records")

        updatedDiagnosticsRecords = []
        mergedRecordsBySessionId = {}

        for record in diagnosticsRecords:
            sessionId = record['sessionid']
            if record['diagnostic'] in diagnosticName:
                if sessionId not in mergedRecordsBySessionId:
                    mergedRecordsBySessionId[sessionId] = [record]
                else:
                    mergedRecordsBySessionId[sessionId].append(record)
            else:
                updatedDiagnosticsRecords.append(record)

        for sessionId, records in mergedRecordsBySessionId.items():
            notes = ""
            startTimestamp = records[0]['startTimestamp']
            endTimestamp = records[len(records)-1]['startTimestamp']

            for record in records:
                notes = notes + record['notes'] + '<br>'

                mergedDiagnosticRecord = {
                    "diagnostic": record['diagnostic'],
                    "category": record['diagnostic']['category'] if 'category' in record['diagnostic'] else 'Uncategorized',
                    "phase": record['phase'],
                    "result": record['result'],
                    "urls": record['urls'],
                    "startTimestamp": startTimestamp,
                    "endTimestamp": endTimestamp,
                    "sessionid": sessionId,
                    "notes": notes,
                }

            updatedDiagnosticsRecords.append(mergedDiagnosticRecord)

        if updatedDiagnosticsRecords:
            updatedDiagnosticsRecords = sorted(
                updatedDiagnosticsRecords, key=lambda dt: dt['startTimestamp'])
        else:
            logger.warning(f"There are no merged records")

        return updatedDiagnosticsRecords

    def __getDiagnosticAggregateStatementMembers(self, formula: str) -> dict:

        FORMULA_PATTERNS = ({"pattern": "^(?!.*index)(?P<preDefinedFormula>.*)\\s(?P<variable1>{\\w+})\\s(?P<operator1>>|<|>=|<=|==|!=)\\s(?P<value1>.*)$",
                             "statement": "countif {received} >= 0.5"},

                            {"pattern": "^(?!.*index)(?P<preDefinedFormula>.*)\\s(?P<variable1>{\\w+})\\s(?P<operator1>>|<|>=|<=|==|!=)\\s(?P<value1>.*)\\s(?P<logicOperator>and|or)\\s(?P<variable2>{\\w+})\\s(?P<operator2>>|<|>=|<=|==|!=)\\s(?P<value2>.*)",
                             "statement": "countif {received} >= 0.5 or {transmitted} >= 0.5"},

                            {"pattern": "(?P<preDefinedFormula>.*)\\sindex (?P<index1>\\d+)\\s(?P<operator1>>|<|>=|<=|==|!=)\\s(?P<value1>.*)$",
                             "statement": "countif index 1 >= 0.5"},

                            {"pattern": "^(?!.*index)(?P<preDefinedFormula>.*)\\s(?P<variable1>\\w+)$",
                             "exastatementmples": "count {received}"},

                            {"pattern": "(?P<preDefinedFormula>.*)\\sindex\\s(?P<index1>\\d+)$",
                             "statement": "count index 1"}
                            )

        PRE_DEFINED_FORMULAS = ['count', 'countif', 'sum', 'sumif']

        for formulaPattern in FORMULA_PATTERNS:
            searchFormulaMembers = re.search(
                formulaPattern['pattern'], formula)
            formulaMembers = {}
            try:
                formulaMembers = searchFormulaMembers.groupdict()
                if formulaMembers['preDefinedFormula'] not in PRE_DEFINED_FORMULAS:
                    continue
                break
            except:
                pass

        if formulaMembers and formulaMembers['preDefinedFormula'] in PRE_DEFINED_FORMULAS:
            return formulaMembers
        else:
            raise ValueError("The aggregate statement is not valid")

    def __getAggregatedValues(self, records: list, formula: str) -> Union[int, float]:
        '''

        examples:
        - __getAggregatedValues(values, 'countif received >= 0.5")-> list of dict
        - __getAggregatedValues(values, 'sumif received >= 0.5")  -> list of dict
        - __getAggregatedValues(values, 'count received") -> list of dict
        - __getAggregatedValues(values, 'sum received") -> list of dict

        - __getAggregatedValues(values, 'countif index 0 >= 0.5") -> list of list
        - __getAggregatedValues(values, 'sumif index 1 >= 0.5")   -> list of list
        - __getAggregatedValues(values, 'count index 0")  -> list of list
        - __getAggregatedValues(values, 'sum index 1") -> list of list

        - __getAggregatedValues(values, 'count") -> list
        - __getAggregatedValues(values, 'sum") -> list
        '''
        formulaMembers = self.__getDiagnosticAggregateStatementMembers(formula)
        formulaMemberNames = list(formulaMembers.keys())
        formulaMemberNames.sort()

        isTokensListOfDict = isTokensListOfLists = False

        if isinstance(records, list) and len(records) > 0:
            if isinstance(records[0], dict):
                isTokensListOfDict = True
            if isinstance(records[0], list) or isinstance(records[0], tuple):
                isTokensListOfLists = True

        if isTokensListOfDict == isTokensListOfLists == False:
            raise ValueError(
                "The list has invalid value. It must be list, list of lists/tuple or list of dicts")

        preDefinedFormula = formulaMembers['preDefinedFormula']

        testMembers = ['preDefinedFormula', 'variable1', 'operator1', 'value1']
        testMembers.sort()
        if formulaMemberNames == testMembers:
            varName1 = formulaMembers['variable1'].replace(
                '{', '').replace('}', '')
            operator1 = formulaMembers['operator1']
            value1 = formulaMembers['value1']
            varName2 = False

        testMembers = ['preDefinedFormula', 'variable1', 'operator1',
                       'value1', 'logicOperator', 'variable2', 'operator2', 'value2']
        testMembers.sort()
        if formulaMemberNames == testMembers:
            varName1 = formulaMembers['variable1'].replace(
                '{', '').replace('}', '')
            operator1 = formulaMembers['operator1']
            value1 = formulaMembers['value1']
            logicOperator = formulaMembers['logicOperator']
            varName2 = formulaMembers['variable2'].replace(
                '{', '').replace('}', '') if 'variable2' in formulaMembers else False
            operator2 = formulaMembers['operator2']
            value2 = formulaMembers['value2']

        if preDefinedFormula == 'countif':

            totalcount = 0
            for record in records:
                if varName1 and varName2:
                    var1 = record[varName1]
                    var2 = record[varName2]

                    # Need to test if the value is text or number, if text the value needs to be surrounded by quotes before execute eval()
                    try:
                        float(value1)
                    except:
                        value1 = f"'{value1}'"
                    try:
                        float(value2)
                    except:
                        value2 = f"'{value2}'"

                    conditonalStatement = f'{var1} {operator1} {value1} {logicOperator} {var2} {operator2} {value2}'
                else:
                    var1 = record[varName1]
                    conditonalStatement = f'{var1} {operator1} {value1}'

                if eval(conditonalStatement):
                    totalcount += 1

            return totalcount
            # return sum(1 for x in values if eval(conditonalStatement))

        if preDefinedFormula == 'count':
            return len(records)

        # if preDefinedFormula == 'sum':
        #     try:
        #         return sum(int(v) for v in values)
        #     except:
        #         try:
        #             return sum(float(v) for v in values)
        #         except:
        #             raise ValueError("Values must be integer or decimal")

        # if preDefinedFormula == 'sumif':
        #     totalsum = 0
        #     for value in values:

        #         # Convert string to integer or float
        #         if isinstance(value, str):
        #             # check if integer
        #             if re.match("^\\d(?!.)", value):
        #                 value = int(value)
        #             else:
        #                 try:
        #                     value = float(value)
        #                 except:
        #                     raise ValueError("The value must be a number")

        #         conditonalStatement = f'{value} {comparisonOperator} {constantValue}'
        #         if eval(conditonalStatement):
        #             totalsum += value

            # return totalsum

    def __getDiagnosticAggregatedData(self, diagnosticDefinition) -> list:

        diagnostics = []

        if len(self.tokenizedFiles) == 0:
            raise ValueError("The dataset must not be empty")

        if not isinstance(self.tokenizedFiles[0], dict):
            raise TypeError("The dataset members must be of dict type")

        diagnosticAggregationStatement = diagnosticDefinition[
            'aggregationStatement'] if 'aggregationStatement' in diagnosticDefinition else False

        dataReference = diagnosticDefinition['dataReference']
        diagnosticSignatureName = dataReference['signatureName']
        diagnosticGroupName = dataReference['groupName']
        diagnosticDomain = dataReference['domain']
        diagnosticConfig = diagnosticDefinition['diagnostic']

        if not diagnosticAggregationStatement:
            return None

        tokensBySessionId = {}
        for tokenizedFile in self.tokenizedFiles:

            #fileName = subset['fileName']
            groups = tokenizedFile['tokensGroups']

            for group in groups:

                if diagnosticDomain == group['domain'] and diagnosticGroupName == group['groupName'] and diagnosticSignatureName == group['signatureName']:

                    tokens = group['tokens']

                    if isinstance(tokens, dict) and len(tokens) > 0:
                        tokens = [tokens]

                    if isinstance(tokens, list) and len(tokens) > 0 and isinstance(tokens[0], dict) and tokens[0]:

                        for token in tokens:
                            sessionid = token['sessionid']
                            if sessionid not in tokensBySessionId:
                                tokensBySessionId[sessionid] = [token]
                            else:
                                tokensBySessionId[sessionid].append(token)

        for sessionIdKey, tokensValue in tokensBySessionId.items():

            tokensValue = sorted(tokensValue, key=lambda dt: dt['timestamp'])
            startTimestamp = tokensValue[0]['timestamp']
            endTimestamp = tokensValue[len(tokensValue)-1]['timestamp']

            aggregatedValues = self.__getAggregatedValues(
                tokensValue, diagnosticAggregationStatement)

            totalCount = len(tokensValue)
            proportion = math.ceil((aggregatedValues / totalCount) * 100)
            aggregationNotes = f"{proportion}% ({aggregatedValues}/{totalCount})"
            aggregationResult = diagnosticConfig['result']

            if aggregatedValues > 0 and aggregatedValues <= (totalCount/2):
                aggregationResult = 'Warning'
            if aggregatedValues > (totalCount/2):
                aggregationResult = 'Failed'

            record = {
                "diagnostic": diagnosticConfig['name'],
                "category": diagnosticConfig['category'] if 'category' in diagnosticConfig else 'Uncategorized',
                "phase": diagnosticGroupName,
                "result": aggregationResult,
                "urls": diagnosticConfig['urls'],
                "startTimestamp": startTimestamp,
                "endTimestamp": endTimestamp,
                "sessionid": sessionIdKey,
                "notes": aggregationNotes
            }
            diagnostics.append(record)

        return diagnostics

    def __getDiagnosticMessageUpdate(self, message: str, tokens: dict) -> str:
        DIAGRULE_VARIABLES_IN_MESSAGE_PATTERN = '([^\\{\\}]+(?=\\}))'
        variables = re.findall(
            DIAGRULE_VARIABLES_IN_MESSAGE_PATTERN, message, flags=re.M)

        if variables:
            for variable in variables:
                message = message.replace(
                    ("{" + f"{variable}" + "}"), tokens[variable])
                # Need review. If signature/label does not match diagnostic/variable from notes

        return message

    def __getProductName(self) -> str:

        for tokenizedFile in self.tokenizedFiles:
            tokensGroups = tokenizedFile['tokensGroups']
            for tokensGroup in tokensGroups:
                if 'Product Info' in tokensGroup['signatureName']:
                    tokens = tokensGroup['tokens']
                    if tokens and 'type' in tokens and tokens['type']:
                        return tokens['type']
        return ""

    def __getNVIDIAGridLicenseStatus(self) -> str:

        for tokenizedFile in self.tokenizedFiles:
            tokensGroups = tokenizedFile['tokensGroups']
            for tokensGroup in tokensGroups:
                if tokensGroup['signatureName'] == 'NVIDIA GRID Licensed':
                    tokens = tokensGroup['tokens']
                    if tokens and 'licenseStatus' in tokens and tokens['licenseStatus']:
                        return tokens['licenseStatus']
        return ""

    def __getNVIDIAVideoAdapterForLinux(self) -> str:

        for tokenizedFile in self.tokenizedFiles:
            tokensGroups = tokenizedFile['tokensGroups']
            for tokensGroup in tokensGroups:
                if tokensGroup['signatureName'] == 'NVIDIA Video Adapter':
                    tokens = tokensGroup['tokens']
                    if tokens and 'videoAdapter' in tokens and tokens['videoAdapter']:
                        return tokens['videoAdapter']
                if tokensGroup['signatureName'] == 'NVIDIA Video Adapter from Xorg':
                    tokens = tokensGroup['tokens']
                    if tokens and 'videoAdapter' in tokens and tokens['videoAdapter']:
                        return tokens['videoAdapter']
        return ""

    def __setDiagnosticRecord(self, tokens: Union[dict, list], diagnosticDefinition: dict) -> dict:

        if 'diagnostic' not in diagnosticDefinition or 'dataReference' not in diagnosticDefinition:
            return {}

        diagnostic = diagnosticDefinition['diagnostic']
        dataReference = diagnosticDefinition['dataReference']

        record = {
            "diagnostic": diagnostic['name'],
            "category": diagnostic['category'] if 'category' in diagnostic else 'Uncategorized',
            "phase": dataReference['groupName'],
            "result": diagnostic['result'],
            "urls": diagnostic['urls'],
            "startTimestamp": tokens['timestamp'] if 'timestamp' in tokens else '-',
            "endTimestamp": tokens['endTimestamp'] if 'endTimestamp' in tokens else '-',
            "sessionid": tokens['sessionid'] if 'sessionid' in tokens else "00000000-0000-0000-0000-000000000000",
            "notes": ""
        }

        message = diagnostic['notes']
        updatedMessage = self.__getDiagnosticMessageUpdate(
            message, tokens)
        record['notes'] = updatedMessage

        # Beginningn >>>>>  Multi steps timeout #########################################
        # Set diagnostic result as 'Failed' if time between first step and last stemp is not greater than the threshold
        if 'diagnostic' in diagnosticDefinition and 'multiStepsTimeout' in diagnostic:
            multiStepsTimeout = diagnostic['multiStepsTimeout']

            diffTimeObj = diffTimeMiliseconds = multiStepsTimeout = None

            startTimestampObj = datetime.strptime(
                tokens['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
            if 'endTimestamp' in tokens:
                endTimestampObj = datetime.strptime(
                    tokens['endTimestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
                diffTimeObj = endTimestampObj - startTimestampObj
                diffTimeMiliseconds = int(
                    (diffTimeObj.microseconds / 1000)) if diffTimeObj else -1

            if diffTimeMiliseconds and multiStepsTimeout and (diffTimeMiliseconds > multiStepsTimeout):
                record['result'] = 'Failed'
                record['urls'] = diagnostic['urls']
                record[
                    'notes'] = f'Time between messages sending and receiving messages timed out (Threshold: {multiStepsTimeout} ms | Measured: {diffTimeMiliseconds} ms)'
        # End >>>>>  Multi steps timeout #########################################

        if 'memoryRequirements' in diagnostic:

            productName = self.__getProductName()
            if productName:
                memoryRequirements = diagnostic['memoryRequirements']
                if type(memoryRequirements) != list:
                    raise TypeError(
                        'The property diagnostic->memoryRequirements must be a list')

                for memoryRequirementByProduct in memoryRequirements:
                    if re.match(memoryRequirementByProduct['productName'], productName):
                        memoryRequirement = memoryRequirementByProduct

                if memoryRequirement:
                    minimumInstalledMB = int(
                        memoryRequirement['minimumInstalledMB'])
                    minimumAvailableMB = int(
                        memoryRequirement['minimumAvailableMB'])
                    reportedInstalledMB = int(tokens['installedMB'])
                    reportedAvailableMB = int(tokens['availableMB'])
                    memoryNotes = f'Installed Memory: {reportedInstalledMB}<br>'

                if reportedInstalledMB < minimumInstalledMB and reportedAvailableMB < minimumAvailableMB:
                    memoryNotes += f'Recommended memory installed: {minimumInstalledMB}<br>'
                    memoryNotes += f'Recommended available memory: {reportedAvailableMB}<br>'
                    record['result'] = 'Failed'
                    record['notes'] = memoryNotes
                else:
                    memoryNotes += f'Recommended memory installed: {minimumInstalledMB}<br>'
                    memoryNotes += f'Available memory is above {minimumAvailableMB} MB which is the minimum required'
                    record['notes'] = memoryNotes
            else:
                logger.warning(
                    "The product name is not available so memory requirements cannot be determined")
        # Beginningn >>>>> NVIDIA Driver #########################################

        if 'NVIDIADriverVersions' in diagnostic:
            record['phase'] = "Install"

            isGridLicenseRequired = False
            isDriverCertified = False
            NVIDIAGridLicenseStatus = self.__getNVIDIAGridLicenseStatus()
            NVIDIAVideoAdapterForLinux = self.__getNVIDIAVideoAdapterForLinux()

            if 'notes' in record and 'Dummy' in record['notes'] and NVIDIAVideoAdapterForLinux:
                record['notes'] = record['notes'].replace(
                    'Dummy', f'NVIDIA {NVIDIAVideoAdapterForLinux}')
                tokens['videoAdapter'] = NVIDIAVideoAdapterForLinux

            NVIDIADriverVersions = diagnostic["NVIDIADriverVersions"]
            if '.' in tokens['driverVersion']:
                driverVersion = float(tokens['driverVersion'])
            else:
                driverVersion = float(
                    tokens['driverVersion'][:3] + '.' + tokens['driverVersion'][3:])

            for NVIDIADriverVersion in NVIDIADriverVersions:
                if driverVersion >= NVIDIADriverVersion:
                    isDriverCertified = True

            if isDriverCertified:
                record[
                    'notes'] += f"<br> NVIDIA Display Driver Version: {driverVersion} (certified)"
            else:
                record[
                    'notes'] += f"<br> NVIDIA Display Driver Version: {driverVersion} (not certified)"
                record['result'] = 'Failed'

            # if NVIDIAGridLicenseStatus:
            #     record['notes'] += f"<br> NVIDIA Display Driver Version: {driverVersion} is certified"

            NVIDIAGridVideoAdapaters = diagnostic['NVIDIAGridVideoAdapaters']
            for NVIDIAGridVideoAdapater in NVIDIAGridVideoAdapaters:
                # if NVIDIAGridVideoAdapater in tokens['videoAdapter']:
                if re.search(f'\\b{NVIDIAGridVideoAdapater}\\b', tokens['videoAdapter']):
                    if NVIDIAGridLicenseStatus:
                        record['notes'] += "<br> NVIDIA Grid Workstation license is installed"
                    else:
                        record['notes'] += "<br> NVIDIA Grid Workstation license is not installed"
                        record['result'] = 'Failed'
                    isGridLicenseRequired = True
                    break

            if not isGridLicenseRequired:
                record['notes'] += "<br> NVIDIA Grid License is not required"

        return record

    def __getAdvDiagResourceAllocationDiagnostic(self, advDiagnosticDataSet: dict) -> list:

        advDiagDefinition = {}
        advDiagDataReference = {}
        recordsForReport = []
        recordsFromLogFiles = []

        for advDiagDataType, advDiagDefinitionsAndRecordGroups in advDiagnosticDataSet.items():
            if advDiagDataType == 'mainDefinitionAndTokenGroups':
                for advDiagDefinitionAndRecords in advDiagDefinitionsAndRecordGroups:
                    recordsFromLogFiles.extend(advDiagDefinitionAndRecords['tokens'])
                    if not advDiagDefinition:
                        advDiagDefinition = advDiagDefinitionAndRecords['diagnosticDefinition']['diagnostic']
                        advDiagDataReference = advDiagDefinitionAndRecords['diagnosticDefinition']['dataReference']
                        continue
        
        recordsBySessionId = {}

        for sessionResourceAllocationToken in recordsFromLogFiles:

            if sessionResourceAllocationToken['sessionid_list']:
                if sessionResourceAllocationToken['sessionid_list'] not in recordsBySessionId:
                    recordsBySessionId[sessionResourceAllocationToken['sessionid_list']] = [
                        sessionResourceAllocationToken]
                else:
                    (recordsBySessionId[sessionResourceAllocationToken['sessionid_list']]).append(
                        sessionResourceAllocationToken)

            if sessionResourceAllocationToken['sessionid_alloc']:
                if sessionResourceAllocationToken['sessionid_alloc'] not in recordsBySessionId:
                    recordsBySessionId[sessionResourceAllocationToken['sessionid_alloc']] = [
                        sessionResourceAllocationToken]
                else:
                    (recordsBySessionId[sessionResourceAllocationToken['sessionid_alloc']]).append(
                        sessionResourceAllocationToken)

        for key, records in recordsBySessionId.items():
            isDirectConnection = False
            for record in records:
                if record['sessionid_list']:
                    isDirectConnection = True
                    continue
                if record['sessionid_alloc']:
                    diagnosticRecord = {
                        "diagnostic": advDiagDefinition['name'],
                        "category": advDiagDefinition['category'] if 'category' in advDiagDefinition else 'Uncategorized',
                        "phase": advDiagDataReference['groupName'],
                        "urls": advDiagDefinition['urls'],
                        "startTimestamp": record['timestamp_alloc'],
                        "sessionid": record['sessionid_alloc'],
                        "result": "Passed",
                        "endTimestamp": "-",
                        "notes": 'Direct resource allocated' if isDirectConnection else 'Brokered resource allocated'
                    }
                    recordsForReport.append(diagnosticRecord)

        return recordsForReport

    def __getAdvDiagEstablishPayload(self, advDiagnosticDataSet: dict) -> list:

        advDiagDefinition = {}
        advDiagDataReference = {}
        recordsForReport = []
        recordsFromLogFiles = []

        for advDiagDataType, advDiagDefinitionsAndRecordGroups in advDiagnosticDataSet.items():
            if advDiagDataType == 'mainDefinitionAndTokenGroups':
                for advDiagDefinitionAndRecords in advDiagDefinitionsAndRecordGroups:
                    recordsFromLogFiles.extend(advDiagDefinitionAndRecords['tokens'])
                    if not advDiagDefinition:
                        advDiagDefinition = advDiagDefinitionAndRecords['diagnosticDefinition']['diagnostic']
                        advDiagDataReference = advDiagDefinitionAndRecords['diagnosticDefinition']['dataReference']
                        continue
        
        for sessionAcceptPayloadTokenStart in recordsFromLogFiles:

            if type(sessionAcceptPayloadTokenStart) == dict and 'timestamp' in sessionAcceptPayloadTokenStart and sessionAcceptPayloadTokenStart['timestamp']:
                # updatedNotes = self.__getDiagnosticMessageUpdate(advDiagDefinition['notes'], sessionAcceptPayloadTokenStart)
                # record = {
                #     "diagnostic": "Accept Payload",
                #     "category": advDiagDefinition['category'] if 'category' in advDiagDefinition else 'Uncategorized',
                #     "phase": advDiagDataReference['groupName'],
                #     "urls": advDiagDefinition['urls'],
                #     "startTimestamp": sessionAcceptPayloadTokenStart['timestamp'],
                #     "sessionid": sessionAcceptPayloadTokenStart['sessionid'],
                #     "result": "Failed",
                #     "endTimestamp": "-",
                #     "notes": advDiagDefinition['notes']
                # }
                record = self.__setDiagnosticRecord(
                    sessionAcceptPayloadTokenStart, advDiagDefinitionAndRecords['diagnosticDefinition'])                
                recordsForReport.append(record)


            #For Agent
            if type(sessionAcceptPayloadTokenStart) == dict and 'conditionStart' in sessionAcceptPayloadTokenStart and sessionAcceptPayloadTokenStart['conditionStart']:
                isPayloadAccepted = False
                timeStampStart = sessionAcceptPayloadTokenStart['timeStampStart']
                sessionIdStart = sessionAcceptPayloadTokenStart['sessionIdStart']

                record = {
                    "diagnostic": advDiagDefinition['name'],
                    "category": advDiagDefinition['category'] if 'category' in advDiagDefinition else 'Uncategorized',
                    "phase": advDiagDataReference['groupName'],
                    "urls": advDiagDefinition['urls'],
                    "startTimestamp": timeStampStart,
                    "sessionid": sessionIdStart,
                }

                for sessionAcceptPayloadTokenEnd in recordsFromLogFiles:

                    if type(sessionAcceptPayloadTokenEnd) == dict and 'conditionEnd' in sessionAcceptPayloadTokenEnd and sessionAcceptPayloadTokenEnd['conditionEnd']:

                        timeStampEnd = sessionAcceptPayloadTokenEnd['timeStampEnd']
                        sessionIdEnd = sessionAcceptPayloadTokenEnd['sessionIdEnd']

                        if sessionIdEnd == sessionIdStart:
                            record['result'] = "Passed"
                            record['endTimestamp'] = timeStampEnd
                            record['notes'] = "Accepted Payload"
                            isPayloadAccepted = True
                            break

                if isPayloadAccepted == False:
                    record['result'] = "Failed"
                    record['endTimestamp'] = timeStampStart
                    record['notes'] = "Accepted Payload Failed"

                recordsForReport.append(record)

        recordsLength = len(recordsForReport)
        for index in range(0, recordsLength):

            currentRecord = recordsForReport[index]
            currentRecordTimeStampStart = datetime.strptime(
                currentRecord['startTimestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')

            if index < recordsLength - 1:

                nextRecord = recordsForReport[index+1]
                nextRecordTimeStampStart = datetime.strptime(
                    nextRecord['startTimestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')

                for sessionAcceptPayloadToken in recordsFromLogFiles:
                    #For Agent
                    if type(sessionAcceptPayloadToken) == dict and 'timeStampClientAddress' in sessionAcceptPayloadToken and sessionAcceptPayloadToken['timeStampClientAddress']:

                        timeStampClientAddress = datetime.strptime(
                            sessionAcceptPayloadToken['timeStampClientAddress'], '%Y-%m-%dT%H:%M:%S.%fZ')

                        if timeStampClientAddress > currentRecordTimeStampStart and timeStampClientAddress < nextRecordTimeStampStart:
                            recordsForReport[index]['notes'] = recordsForReport[index]['notes'] + \
                                f"<br>Client Address: {sessionAcceptPayloadToken['conditionClientAddress']}"
                            break
            else:
                # last record
                for sessionAcceptPayloadToken in recordsFromLogFiles:
                    #For Agent
                    if type(sessionAcceptPayloadToken) == dict and 'timeStampClientAddress' in sessionAcceptPayloadToken and sessionAcceptPayloadToken['timeStampClientAddress']:

                        timeStampClientAddress = datetime.strptime(
                            sessionAcceptPayloadToken['timeStampClientAddress'], '%Y-%m-%dT%H:%M:%S.%fZ')

                        if timeStampClientAddress > currentRecordTimeStampStart:
                            recordsForReport[index]['notes'] = recordsForReport[index]['notes'] + \
                                f"<br>Client Address: {sessionAcceptPayloadToken['conditionClientAddress']}"
                            break

        # sessionIds = {}
        # newRecords = []
        # for record in records:
        #     if record['sessionid'] not in sessionIds:
        #         sessionIds[record['sessionid']] = [record]
        #     else:
        #         sessionIds[record['sessionid']].append(record)

        # for __sessionId, r in sessionIds.items():
        #     s = sorted(r, key=lambda dt: dt['startTimestamp'])
        #     p = s[len(s)-1]
        #     newRecords.append(p)

        # return newRecords
        return recordsForReport

    def __getClientAddress(self):

        hostname = ''
        hostnames = {}

        for tokenizedFile in self.tokenizedFiles:
            tokensGroups = tokenizedFile['tokensGroups']
            for tokensGroup in tokensGroups:
                if tokensGroup['signatureName'] == 'Client Hostname' and tokensGroup['tokens']:
                    if type(tokensGroup['tokens']) is list:
                        for index in range(len(tokensGroup['tokens'])):
                            hostnames[tokensGroup['tokens'][index]['timestamp']
                                      ] = tokensGroup['tokens'][index]['hostname']
                    else:
                        hostnames[tokensGroup['tokens']['timestamp']
                                  ] = tokensGroup['tokens']['hostname']

        if len(hostnames) > 0:
            hostname = hostnames[sorted(hostnames.keys())[-1]]

        return hostname

    def __getAdvDiagLicenseConfiguration(self, advDiagtokensAndDefinitions: dict) -> list:

        records = []
        for advDiagType, tokensAndDefinitions in advDiagtokensAndDefinitions.items():
            if advDiagType == 'mainDefinitionAndTokenGroups':
                mainDiagnosticTokensAndDefinitions = tokensAndDefinitions
            if advDiagType == 'complementaryDefinitionAndTokenGroups':
                additionalDiagnosticTokensAndDefinitions = tokensAndDefinitions

        isLicServerNotAvailable = isHostRegisterToDifferentOrganization = False
        # definition = tokensAndDefinitions['diagnosticDefinition']
        # tokens = tokensAndDefinitions['tokens']

        if advDiagtokensAndDefinitions['complementaryDefinitionAndTokenGroups']:
            errorMessages = [
                'no servers are available to list licenses on', 'could not send capability request']
            supportingDiagnosticTokens = [
                tokens for outerItem in additionalDiagnosticTokensAndDefinitions for tokens in outerItem['tokens']]
            lastRecord = supportingDiagnosticTokens[-1]
            for message in lastRecord.values():
                if message:
                    if message in errorMessages:
                        isLicServerNotAvailable = True

            for supportingDiagnosticToken in supportingDiagnosticTokens:
                for message in supportingDiagnosticToken.values():
                    if message and re.match('Failed to register with the cloud license server.*may already be registered with.*under a different registration', message):
                        isHostRegisterToDifferentOrganization = True

        for mainDiagnosticTokensAndDefinition in mainDiagnosticTokensAndDefinitions:
            mainDiagnosticDefinition = mainDiagnosticTokensAndDefinition['diagnosticDefinition']
            mainTokens = mainDiagnosticTokensAndDefinition['tokens']
            record = self.__setDiagnosticRecord(
                mainTokens, mainDiagnosticDefinition)
            if isLicServerNotAvailable and isHostRegisterToDifferentOrganization:
                record['notes'] = record['notes'] + \
                    '<br>Host allocated to a different organization'
            records.append(record)

        return records

    def __getAdvDiagPacketLoss(self, advDiagtokensAndDefinitions: dict) -> list:
        '''
            It analyses a group of tokens related to packet transmission, apply rules and generate record
            The following string, extracted from the PCoIP log bundle, provide the data necessary for this analysis
                R=000606/003468/002052 T=000000/000000/006343 (A/I/O) Loss=3.21%/0.00%
            Rules:
                If packet loss excess this threshould value then diagnostic result = failure
                If packets were not transmitted then diagnostic result = warning
                Otherwise, the diagnostic result = passed
        '''
        records = []

        for advDiagType, tokensAndDefinitions in advDiagtokensAndDefinitions.items():
            if advDiagType == 'mainDefinitionAndTokenGroups':
                mainDiagnosticTokensAndDefinitions = tokensAndDefinitions
            # if advDiagType == 'complementaryDefinitionAndTokenGroups':
            #     additionalDiagnosticTokensAndDefinitions = tokensAndDefinitions

        for mainDiagnosticTokensAndDefinition in mainDiagnosticTokensAndDefinitions:
            mainDiagnosticDefinition = mainDiagnosticTokensAndDefinition['diagnosticDefinition']
            packetLossThreshouldValue = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['packetLossThreshould']
            mainTokenGroup = mainDiagnosticTokensAndDefinition['tokens']
            for mainTokens in mainTokenGroup:

                # werePacketsReceived = False means all RxA RxI RxO are zero (Audio/Image/Others)
                # werePacketsSent = False means all TxA TxI TxO are zero
                werePacketsReceived = False
                werePacketsSent = False
                isPacketLossAboveThreshould = False
                isReceptionLossAboveThreshould = isTransmissionLossAboveThreshould = False

                # Looking for signed of packet transmission and packet loss
                for key, value in mainTokens.items():
                    if not werePacketsReceived and 'received' in key.lower() and int(value) > 0:
                        werePacketsReceived = True
                    if not werePacketsSent and 'transmitted' in key.lower() and int(value) > 0:
                        werePacketsSent = True
                    if 'receptionLoss' in key and float(value) >= packetLossThreshouldValue:
                        isReceptionLossAboveThreshould = True
                    if 'transmissionLoss' in key and float(value) >= packetLossThreshouldValue:
                        isTransmissionLossAboveThreshould = True
                    if not isPacketLossAboveThreshould and 'loss' in key.lower() and float(value) >= packetLossThreshouldValue:
                        isPacketLossAboveThreshould = True
                    continue

                if werePacketsReceived and werePacketsSent and not (isReceptionLossAboveThreshould or isTransmissionLossAboveThreshould):
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Passed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'PCoIP traffic -> RxStatus: Received | TxStatus: Sent<br>Packet Loss: < {packetLossThreshouldValue}%<br>Full message: {mainTokens["fullMessage"]}'

                elif not (werePacketsReceived and werePacketsSent) and not (isReceptionLossAboveThreshould or isTransmissionLossAboveThreshould):
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Warning'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'PCoIP traffic -> RxStatus: No Data | TxStatus: No Data<br>Packet Loss: 0.00%<br>Full message: {mainTokens["fullMessage"]}'

                elif (isReceptionLossAboveThreshould or isTransmissionLossAboveThreshould):
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Failed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'PCoIP traffic -> RxStatus: {"Received with Loss" if isReceptionLossAboveThreshould else "Received"} | TxStatus: {"Sent with Loss" if isTransmissionLossAboveThreshould else "Sent"}<br>Packet Loss: > {packetLossThreshouldValue}%<br>Full message: {mainTokens["fullMessage"]}'
                else:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Failed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'PCoIP traffic -> RxStatus: ?? | TxStatus: ??<br>Packet Loss: > ??%<br>Full message: {mainTokens["fullMessage"]}'

                record = self.__setDiagnosticRecord(
                    mainTokens, mainDiagnosticDefinition)
                records.append(record)

        return records

    def __getAdvDiagLatency(self, advDiagtokensAndDefinitions: dict) -> list:

        records = []

        for advDiagType, tokensAndDefinitions in advDiagtokensAndDefinitions.items():
            if advDiagType == 'mainDefinitionAndTokenGroups':
                mainDiagnosticTokensAndDefinitions = tokensAndDefinitions

        for mainDiagnosticTokensAndDefinition in mainDiagnosticTokensAndDefinitions:
            mainDiagnosticDefinition = mainDiagnosticTokensAndDefinition['diagnosticDefinition']
            mainTokenGroup = mainDiagnosticTokensAndDefinition['tokens']
            latencyWarningThreshould = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['latencyWarningThreshould']
            latencyFailedThreshould = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['latencyFailedThreshould']

            for mainTokens in mainTokenGroup:

                if int(mainTokens['roundtrip']) < latencyWarningThreshould:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Passed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Latency never exceed {latencyWarningThreshould} ms during the session<br>Full message: {mainTokens["fullMessage"]}'
                elif int(mainTokens['roundtrip']) >= latencyWarningThreshould and int(mainTokens['roundtrip']) < latencyFailedThreshould:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Warning'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Latency exceeded {latencyWarningThreshould} ms, but less than {latencyFailedThreshould}<br>Full message: {mainTokens["fullMessage"]}'
                else:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Failed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Latency exceeded {latencyFailedThreshould} ms<br>Full message: {mainTokens["fullMessage"]}'

                record = self.__setDiagnosticRecord(
                    mainTokens, mainDiagnosticDefinition)
                records.append(record)

        return records

    def __getAdvDiagJitter(self, advDiagtokensAndDefinitions: dict) -> list:

        records = []

        for advDiagType, tokensAndDefinitions in advDiagtokensAndDefinitions.items():
            if advDiagType == 'mainDefinitionAndTokenGroups':
                mainDiagnosticTokensAndDefinitions = tokensAndDefinitions

        for mainDiagnosticTokensAndDefinition in mainDiagnosticTokensAndDefinitions:
            mainDiagnosticDefinition = mainDiagnosticTokensAndDefinition['diagnosticDefinition']
            jitterWarningThreshould = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['jitterWarningThreshould']
            jitterFailedThreshould = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['jitterFailedThreshould']
            mainTokenGroup = mainDiagnosticTokensAndDefinition['tokens']

            for mainTokens in mainTokenGroup:

                if int(mainTokens['variance']) < jitterWarningThreshould:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Passed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Jitter never exceed {jitterWarningThreshould} ms during the session<br>Full message: {mainTokens["fullMessage"]}'
                elif int(mainTokens['variance']) >= jitterWarningThreshould and int(mainTokens['variance']) < jitterFailedThreshould:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Warning'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Jitter exceeded {jitterWarningThreshould} ms, but less than {jitterFailedThreshould}<br>Full message: {mainTokens["fullMessage"]}'
                else:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Failed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'Jitter exceeded {jitterFailedThreshould} ms<br>Full message: {mainTokens["fullMessage"]}'

                record = self.__setDiagnosticRecord(
                    mainTokens, mainDiagnosticDefinition)
                records.append(record)

        return records

    def __getAdvProductVersionValidation(self, advDiagtokensAndDefinitions: dict) -> list:

        records = []

        for advDiagType, tokensAndDefinitions in advDiagtokensAndDefinitions.items():
            if advDiagType == 'mainDefinitionAndTokenGroups':
                mainDiagnosticTokensAndDefinitions = tokensAndDefinitions

        for mainDiagnosticTokensAndDefinition in mainDiagnosticTokensAndDefinitions:
            isVersionSupported = False
            mainDiagnosticDefinition = mainDiagnosticTokensAndDefinition['diagnosticDefinition']
            supportedProductVersions = mainDiagnosticDefinition[
                'diagnostic']['advancedOptions']['supportedProductVersions']
            mainTokens = mainDiagnosticTokensAndDefinition['tokens']

            for supportedProductVersion in supportedProductVersions:
                if supportedProductVersion in mainTokens['version']:
                    isVersionSupported = True

            if 'version' in mainTokens:
                if isVersionSupported:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Passed'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'The version {mainTokens["version"]} is supported'
                else:
                    mainDiagnosticDefinition['diagnostic']['result'] = 'Warning'
                    mainDiagnosticDefinition['diagnostic'][
                        'notes'] = f'The version {mainTokens["version"]} is not recommended for deployment'
            else:
                mainDiagnosticDefinition['diagnostic']['result'] = 'Warning'

            mainTokens['endTimestamp'] = '-'
            record = self.__setDiagnosticRecord(
                mainTokens, mainDiagnosticDefinition)

            records.append(record)

        if not records:
            return records

        records = sorted(
            records, key=lambda dt: dt['startTimestamp'], reverse=True)

        uniqueRecords = []
        oldestRecords = [records[-1]]

        for index in range(len(records)):
            if index == len(records) - 1:
                uniqueRecords.append(records[index])
            else:
                if records[index]['notes'] != records[index+1]['notes']:
                    uniqueRecords.append(records[index])

        # All records have the same result / notes, so we want to select the oldest one to be at the top of the list
        if len(uniqueRecords) == 1:
            return oldestRecords
        else:
            return uniqueRecords
    
    def __getAdvDiagResolutionNegotiation(self, advDiagnosticDataSet: dict) -> list:

        advDiagDefinition = {}
        advDiagDataReference = {}        
        recordsForReport = []
        recordsFromLogFiles = []
        for advDiagDataType, advDiagDefinitionsAndRecordGroups in advDiagnosticDataSet.items():
            if advDiagDataType == 'mainDefinitionAndTokenGroups':
                for advDiagDefinitionAndRecords in advDiagDefinitionsAndRecordGroups:
                    recordsFromLogFiles.extend(advDiagDefinitionAndRecords['tokens'])
                    if not advDiagDefinition:
                        advDiagDefinition = advDiagDefinitionAndRecords['diagnosticDefinition']['diagnostic']
                        advDiagDataReference = advDiagDefinitionAndRecords['diagnosticDefinition']['dataReference']
                        continue


        def getRecord(startIndex: int, endIndex: int, numDisplaysreceived: int, displayResNegociationMessages: list):

            numberOfValidyTopologies = 0
            requestedWidth = deliveredWidth = requestedHeight = deliveredHeight = 0
            recordsForanalysis = []
            timestamps = []

            for i in range(startIndex, endIndex + 1):
                recordsForanalysis.append(displayResNegociationMessages[i])
                timestamps.append(
                    displayResNegociationMessages[i]['timestamp'])
                sessionid = displayResNegociationMessages[i]['sessionid']

            timestamps.sort()
            rs = {'notes': ""}

            for recordForanalysis in recordsForanalysis:

                displayid = recordForanalysis['displayid']
                if displayid not in rs:
                    rs[displayid] = {}

                if 'request' in recordForanalysis:
                    rs[displayid]['request'] = {
                        'width': recordForanalysis['width'], 'height': recordForanalysis['height']}
                    rs['notes'] += f"Topology requested -> DisplayId: {recordForanalysis['displayid']}, Resolution: {recordForanalysis['width']} x {recordForanalysis['height']}<br>"

                if 'response' in recordForanalysis:

                    rs[displayid]['response'] = {
                        'width': recordForanalysis['width'], 'height': recordForanalysis['height']}
                    rs['notes'] += f"Topology delivered -> DisplayId: {recordForanalysis['displayid']}, Resolution: {recordForanalysis['width']} x {recordForanalysis['height']}<br>"

            numberOfRequests = 0
            for k, v in rs.items():
                try:
                    int(k)
                    numberOfRequests += 1 if 'request' in v else 0
                except:
                    pass

            if not numberOfRequests:
                return {}

            for k, v in rs.items():
                try:
                    int(k)
                    requestedWidth = int(v['request']['width'])
                    deliveredWidth = int(v['response']['width'])
                    requestedHeight = int(v['request']['height'])
                    deliveredHeight = int(v['response']['height'])

                    # For Windowed mode the delivered topologies is always off by a few pixels, and it does not mean a failure
                    # if error "Bad descriptor received (suspect corrupted EDID). Forcing 1024x768", keep the resolution as is

                    # The difference between topology requested and received within 100 pixels is considered a successfull topology negociation (100+100)
                    if (abs(requestedWidth - deliveredWidth) + abs(requestedHeight - deliveredHeight)) <= 200:
                        numberOfValidyTopologies += 1
                except:
                    pass

            #
            if int(numDisplaysreceived) == numberOfValidyTopologies:

                record = {
                    "diagnostic": advDiagDefinition['name'],
                    "category": advDiagDefinition['category'] if 'category' in advDiagDefinition else 'Uncategorized',
                    "phase": advDiagDataReference['groupName'],
                    "result": "Passed",
                    "urls": advDiagDefinition['urls'],
                    "startTimestamp": timestamps[0],
                    "endTimestamp": timestamps[-1],
                    "sessionid": sessionid,
                    "notes": "The requested and delivered display resolutions are the same or within +/- 200 pixels<br>" + rs['notes']
                }

                return record
            else:

                record = {
                    "diagnostic": advDiagDefinition['name'],
                    "category": advDiagDefinition['category'] if 'category' in advDiagDefinition else 'Uncategorized',
                    "phase": advDiagDataReference['groupName'],
                    "result": "Warning",
                    "urls": advDiagDefinition['urls'],
                    "startTimestamp": timestamps[0],
                    "endTimestamp": timestamps[len(timestamps) - 1],
                    "sessionid": sessionid,
                    "notes": 'The requested and delivered display resolutions are different<br>' + rs['notes']
                }

                return record

        recordsFromLogFiles = sorted(
            recordsFromLogFiles, key=lambda dt: dt['timestamp'])
        topologiesReceivedFromHosts = {}

        for i in range(len(recordsFromLogFiles)):
            if 'numDisplaysreceived' in recordsFromLogFiles[i]:
                topologiesReceivedFromHosts[i] = recordsFromLogFiles[i]['numDisplaysreceived']

        startIndex = 0
        for index, numDisplaysreceived in topologiesReceivedFromHosts.items():
            endIndex = index - 1
            record = getRecord(
                startIndex, endIndex, numDisplaysreceived, recordsFromLogFiles)
            if record:
                recordsForReport.append(record)
            startIndex = index + 1

        return recordsForReport

    def __getAdvDiagAcceptPayload(self, advDiagnosticDataSet: dict) -> list:
        
        advDiagDefinition = {}
        advDiagDataReference = {}
        recordsForReport = []
        recordsFromLogFiles = []

        for advDiagDataType, advDiagDefinitionsAndRecordGroups in advDiagnosticDataSet.items():
            if advDiagDataType == 'mainDefinitionAndTokenGroups':
                for advDiagDefinitionAndRecords in advDiagDefinitionsAndRecordGroups:
                    recordsFromLogFiles.extend(advDiagDefinitionAndRecords['tokens'])
                    if not advDiagDefinition:
                        advDiagDefinition = advDiagDefinitionAndRecords['diagnosticDefinition']['diagnostic']
                        advDiagDataReference = advDiagDefinitionAndRecords['diagnosticDefinition']['dataReference']
                        continue

        for recordFromLogFiles in recordsFromLogFiles:
            #The session ids for the accept payload must match to pass, otherwise look for a networking interruption or other issue using another diagnostic
            if recordFromLogFiles['sessionid'] == recordFromLogFiles['sessionid_response'] == recordFromLogFiles['sessionid_complete']:
                record = self.__setDiagnosticRecord(
                    recordFromLogFiles, advDiagDefinitionAndRecords['diagnosticDefinition'])                
                recordsForReport.append(record)

        return recordsForReport

    def __getAdvancedDiagnostics(self, tokensAndDenifinitionForAdvancedDiagnostics: dict) -> list:
        allrecords = []
        for diagnosticsName, tokensAndDefinitions in tokensAndDenifinitionForAdvancedDiagnostics.items():
            if diagnosticsName == 'License Configuration':
                records = self.__getAdvDiagLicenseConfiguration(
                    tokensAndDefinitions)
            if diagnosticsName == 'Packet Loss':
                records = self.__getAdvDiagPacketLoss(
                    tokensAndDefinitions)
            if diagnosticsName == 'Latency':
                records = self.__getAdvDiagLatency(
                    tokensAndDefinitions)
            if diagnosticsName == 'Jitter':
                records = self.__getAdvDiagJitter(
                    tokensAndDefinitions)
            if diagnosticsName == 'Agent Version' or diagnosticsName == 'Client Version':
                records = self.__getAdvProductVersionValidation(
                    tokensAndDefinitions)
            if diagnosticsName == 'Resolution Negotiation':
                records = self.__getAdvDiagResolutionNegotiation(
                    tokensAndDefinitions)
            if diagnosticsName == 'Resource Allocation':
                records = self.__getAdvDiagResourceAllocationDiagnostic(
                    tokensAndDefinitions)
            #Client side
            if diagnosticsName == 'Establish Payload':
                records = self.__getAdvDiagEstablishPayload(
                    tokensAndDefinitions)
            #Agent side
            if diagnosticsName == 'Accept Payload':
                records = self.__getAdvDiagAcceptPayload(
                    tokensAndDefinitions)
            allrecords.extend(records)   

        return allrecords

    @measureExecution
    def __getDiagnosticRecords(self, productType, fileTypes: dict) -> dict:

        if not isinstance(self.tokenizedFiles, list) or (isinstance(self.tokenizedFiles, list) and len(self.tokenizedFiles) == 0) or not isinstance(self.tokenizedFiles[0], dict) or (self.tokenizedFiles[0] and len(self.tokenizedFiles[0]) == 0):
            raise ValueError(
                "Tokenized signatures must be provided to generate diagnostic record")

        logger.info('Generating diagnostic records...')

        diagnosticRecords = list()

        diagnosticsDefinitionForSessionAcceptPayloadAnalysis = ""
        sessionAcceptPayloadTokens = []
        diagnosticsDefinitionForSessionResourceAllocationAnalysis = ""
        sessionResourceAllocationTokens = []

        isAdditionalDiagnostic = False
        tokensAndDenifinitionForAdvancedDiagnostics = {}

        componentDirectory = os.path.join(self.configDirectory, productType)

        _continueINOuterLoop = _ContinueINOuterLoop()

        for tokenizedFile in self.tokenizedFiles:
            for fileType in fileTypes:
                if fileType['fileName'] == tokenizedFile['fileName']:
                    contentType = fileType['contentType']
                    diagnosticsDefinitions = getJson(os.path.join(
                        componentDirectory, f"{contentType}.{productType}.diagnostics.json"))
                    break

            tokensGroups = tokenizedFile['tokensGroups']
            for tokensGroup in tokensGroups:
                if "diagnostics" in diagnosticsDefinitions:
                    try:
                        for diagnosticsDefinition in diagnosticsDefinitions['diagnostics']:

                            dataReference = diagnosticsDefinition['dataReference']
                            diagDomain = dataReference['domain']
                            diagGroupName = dataReference['groupName']
                            diagSignatureName = dataReference['signatureName']

                            if diagDomain == tokensGroup['domain'] and diagGroupName == tokensGroup['groupName'] and diagSignatureName == tokensGroup['signatureName']:

                                # if 'aggregationStatement' in diagnosticsDefinition and diagnosticsDefinition['aggregationStatement']:

                                #     hashedDiagnosticsDefinition = getDictHash(
                                #         diagnosticsDefinition)
                                #     if hashedDiagnosticsDefinition not in diagnosticsDefinitionsWithAggregation:
                                #         diagnosticsDefinitionsWithAggregation[
                                #             hashedDiagnosticsDefinition] = diagnosticsDefinition

                                #     raise _continueINOuterLoop

                                tokens = tokensGroup['tokens']

                                if 'name' in diagnosticsDefinition['diagnostic'] and re.match(".*(?:Agent|Client) (?:Type|Version).*$", diagnosticsDefinition['diagnostic']['name'], re.IGNORECASE):
                                    for tokenKey, tokenValue in tokens.items():
                                        if 'type' == tokenKey.lower():
                                            self.productTypeName = tokenValue
                                        if 'version' == tokenKey.lower():
                                            self.productVersionNumber = tokenValue

                                # if 'name' in diagnosticsDefinition['diagnostic'] and 'Accept Payload' == diagnosticsDefinition['diagnostic']['name']:
                                #     if tokens:

                                #         if re.match('Accept Payload failed on port.*4172', diagnosticsDefinition['dataReference']['signatureName']):
                                #             tokens[0]['specificFailure'] = diagnosticsDefinition['dataReference']['signatureName']
                                #             tokens[0]['notes'] = diagnosticsDefinition['diagnostic']['notes']
                                #             #tokens = [tokens]

                                #         sessionAcceptPayloadTokens.extend(
                                #             tokens)
                                #     if not diagnosticsDefinitionForSessionAcceptPayloadAnalysis and 'name' in diagnosticsDefinition['diagnostic'] and 'urls' in diagnosticsDefinition['diagnostic']:
                                #         diagnosticsDefinitionForSessionAcceptPayloadAnalysis = diagnosticsDefinition

                                #     raise _continueINOuterLoop

                                if 'advancedAnalysis' in diagnosticsDefinition['diagnostic'] and tokens:
                                    # Old approach
                                    if 'directOrBrokeredConnection' == diagnosticsDefinition['diagnostic']['advancedAnalysis']:
                                        sessionResourceAllocationTokens.extend(
                                            tokens)
                                    if not diagnosticsDefinitionForSessionResourceAllocationAnalysis and 'name' in diagnosticsDefinition['diagnostic'] and 'urls' in diagnosticsDefinition['diagnostic']:
                                        diagnosticsDefinitionForSessionResourceAllocationAnalysis = diagnosticsDefinition

                                    raise _continueINOuterLoop

                                if 'advancedOptions' in diagnosticsDefinition['diagnostic'] and tokens:
                                    # New approach
                                    # isMainDiagnostic = False
                                    isAdditionalDiagnostic = False

                                    advancedOptions = diagnosticsDefinition['diagnostic']['advancedOptions']
                                    advancedDiagnosticName = diagnosticsDefinition[
                                        'diagnostic']['name']

                                    # if 'isMainDiagnostic' in advancedOptions and isinstance(advancedOptions['isMainDiagnostic'], bool):
                                    #     isMainDiagnostic = advancedOptions['isMainDiagnostic']

                                    if 'isAdditionalDiagnostic' in advancedOptions and isinstance(advancedOptions['isAdditionalDiagnostic'], bool) and advancedOptions['isAdditionalDiagnostic']:
                                        isAdditionalDiagnostic = True

                                    # Add a diagnostic name to the dictionary
                                    if advancedDiagnosticName not in tokensAndDenifinitionForAdvancedDiagnostics.keys():
                                        tokensAndDenifinitionForAdvancedDiagnostics[advancedDiagnosticName] = dict(
                                        )
                                        tokensAndDenifinitionForAdvancedDiagnostics[advancedDiagnosticName]['mainDefinitionAndTokenGroups'] = list(
                                        )
                                        tokensAndDenifinitionForAdvancedDiagnostics[advancedDiagnosticName]['complementaryDefinitionAndTokenGroups'] = list(
                                        )

                                    infoType = 'complementaryDefinitionAndTokenGroups' if isAdditionalDiagnostic else 'mainDefinitionAndTokenGroups'
                                    tokensAndDenifinitionForAdvancedDiagnostics[advancedDiagnosticName][infoType].append(
                                        {'diagnosticDefinition': diagnosticsDefinition, "tokens": tokens})

                                    raise _continueINOuterLoop

                                if isinstance(tokens, dict) and len(tokens) > 0:

                                    addRecord = True
                                    record = self.__setDiagnosticRecord(
                                        tokens, diagnosticsDefinition)

                                    # Add a record to the list of record if the record does not exist
                                    # This feature is helpful for reporting 'install' time information, such as product type and version, and hardware related information.
                                    # Those pieces of that do not change very often
                                    if 'oncePerReport' in diagnosticsDefinition and diagnosticsDefinition['oncePerReport']:
                                        if len(diagnosticRecords) > 0:
                                            for diagnosticRecord in diagnosticRecords:
                                                if record['notes'] == diagnosticRecord['notes']:
                                                    addRecord = False
                                                    break
                                    if addRecord:
                                        diagnosticRecords.append(record)

                                # Token is list and contains data
                                if isinstance(tokens, list) and len(tokens) > 0 and isinstance(tokens[0], dict):

                                    for token in tokens:
                                        record = self.__setDiagnosticRecord(
                                            token, diagnosticsDefinition)
                                        diagnosticRecords.append(record)

                                # if isinstance(token[0], list) or isinstance(token[0], tuple):
                                #     print('listOfLists')
                                # if isinstance(token[0], str) or isinstance(token[0], int) or isinstance(token[0], float):
                                #     print('primitive type')
                    except _ContinueINOuterLoop:
                        continue

        # acceptPayloanRecords = self.__getAcceptPayloadDiagnostic(
        #     sessionAcceptPayloadTokens, diagnosticsDefinitionForSessionAcceptPayloadAnalysis)

        # diagnosticRecords.extend(acceptPayloanRecords)

        if tokensAndDenifinitionForAdvancedDiagnostics:
            advancedDiagnosticsRecords = self.__getAdvancedDiagnostics(
                tokensAndDenifinitionForAdvancedDiagnostics)

            diagnosticRecords.extend(advancedDiagnosticsRecords)

        # aggregationDefinitions = list(
        #     diagnosticsDefinitionsWithAggregation.values())

        diagnosticRecords = self.__getMergedRecords(
            diagnosticRecords, ["Video Controller Type"])

        # diagnosticAggregatedRecords = []

        # for aggregationDefinition in aggregationDefinitions:
        #     diagnosticAggregatedRecords = self.__getDiagnosticAggregatedData(
        #         aggregationDefinition)
        #     diagnosticRecords.extend(diagnosticAggregatedRecords)

        diagnosticRecords = sorted(
            diagnosticRecords, key=lambda dt: dt['startTimestamp'])

        return diagnosticRecords

    def __getSummaryReportData(self):
        '''
        It summarize the dataset by grouping diagnostics that didnt pass into categories
        '''
        categorizedRecords = {}
        for diagnosticRecord in self.diagnosticRecords:
            if diagnosticRecord['result'].lower() == 'failed' or diagnosticRecord['result'].lower() == 'warning' and 'category' in diagnosticRecord and diagnosticRecord['category'].lower() != 'non-category':

                if diagnosticRecord['category'] not in categorizedRecords:
                    categorizedRecords[diagnosticRecord['category']] = {
                        'Failed': 1, 'Warning': 0} if diagnosticRecord['result'].lower() == 'failed' else {'Failed': 0, 'Warning': 1}

                else:
                    if diagnosticRecord['result'].lower() == 'failed':
                        categorizedRecords[diagnosticRecord['category']
                                           ]['Failed'] += 1
                    if diagnosticRecord['result'].lower() == 'warning':
                        categorizedRecords[diagnosticRecord['category']
                                           ]['Warning'] += 1

        return categorizedRecords

    def getSourceFile(self):
        sourceFileName = ""
        if os.path.isfile(self.filePath):
            sourceFileName = os.path.basename(self.filePath)
        return sourceFileName

    def getDiagnosticReport(self):
        '''
            It takes diagnostic records (list of dicts), execute post-processing, and generate a html report string
        '''
        logger.info(
            f'Generating diagnostic report for file or directory: {self.filePath}')
        appVersionFile = os.path.join(
            self.configDirectory, 'version.json')

        appVersion = getJson(appVersionFile)

        if len(self.diagnosticRecords) == 0 or not isinstance(self.diagnosticRecords[0], dict) or len(self.diagnosticRecords[0]) == 0:
            logger.info(
                f'The report file was not generated because no diagnostic data was found in the file {self.filePath}')
            return None

        clientHostname = self.__getClientAddress()
        summaryData = self.__getSummaryReportData()
        sumaryReportTimeline = f"Start: {self.diagnosticTimeSpan['startTime']}<br>End: {self.diagnosticTimeSpan['endTime']}<br>Timeline in UTC | Local time: {self.diagnosticTimeSpan['timeOffSet']}"
        # productTypeName =
        # productVersionNumber =

        # HTML structure with empty body
        bs = BeautifulSoup()

        html = bs.new_tag('html')
        bs.insert(0, html)

        head = bs.new_tag('head')
        html.insert(0, head)

        style = bs.new_tag('style')
        script = bs.new_tag('script')

        reportStyleFile = os.path.join(
            self.configDirectory, 'custom.css')
        reportScriptFile = os.path.join(
            self.configDirectory, 'logai.js')

        styleContent = getFileContent(reportStyleFile, False)
        scriptContent = getFileContent(reportScriptFile, False)

        style.append(styleContent)
        head.insert(0, style)

        script.append(scriptContent)
        head.insert(0, script)

        body = bs.new_tag('body')
        html.insert(1, body)

        # Adding content to the HTML body - Summary Table 1
        summaryTable1 = bs.new_tag('table')
        summaryTable1['class'] = 'summaryTable1'
        body.insert(0, summaryTable1)

        summaryTable1Rows = {"Product Version": self.productVersionNumber,
                             "Product Type": self.productTypeName, "Report timeline": sumaryReportTimeline}

        for summaryTable1RowKey, summaryTable1RowValue in summaryTable1Rows.items():
            summaryHeaderColumn1 = bs.new_tag('td')
            summaryHeaderColumn1.string = summaryTable1RowValue
            tr = bs.new_tag('tr')
            tr.insert(0, summaryHeaderColumn1)
            summaryTable1.insert(0, tr)

            summaryHeaderColumn2 = bs.new_tag('td')
            summaryHeaderColumn2.string = summaryTable1RowKey
            tr.insert(0, summaryHeaderColumn2)
            summaryTable1.insert(0, tr)

        summaryHeader = bs.new_tag('th')
        summaryHeader['colspan'] = 2
        summaryHeader.string = 'Summary'
        tr = bs.new_tag('tr')
        tr.insert(0, summaryHeader)
        summaryTable1.insert(0, tr)

        # Adding content to the HTML body - Details
        htmlTable = bs.new_tag('table')
        body.insert(3, htmlTable)

        htmlRow = bs.new_tag('tr')
        htmlCol = bs.new_tag('td')
        htmlCol['colspan'] = 7
        htmlCol['id'] = 'bottomBanner'
        htmlCol.string = f"Report Generated on {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} (UTC) | version: {appVersion['logaiVersion']}"
        htmlRow.insert(0, htmlCol)
        htmlTable.insert(0, htmlRow)

        htmlRow = bs.new_tag('tr')
        htmlCol = bs.new_tag('td')
        htmlCol['colspan'] = 7
        htmlCol['id'] = 'topBanner'
        htmlCol.string = f'Teradici - Diagnostic Report'
        htmlRow.insert(0, htmlCol)
        htmlTable.insert(0, htmlRow)

        logstimespanRecord = {
            "phase": "Install",
            "category": 'Uncategorized',
            "diagnostic": "Report Timeline",
            "result": "Passed",
            "urls": {"description": "https://help.teradici.com/s/article/6072#TestClientReport"},
            "startTimestamp": f"{self.diagnosticTimeSpan['startTime']}",
            "endTimestamp": f"{self.diagnosticTimeSpan['endTime']}",
            "sessionid": "00000000-0000-0000-0000-000000000000",
            "notes": f"Timeline in UTC | Local time: {self.diagnosticTimeSpan['timeOffSet']}"
        }

        if clientHostname:
            logstimespanRecord['notes'] = logstimespanRecord['notes'] + \
                f"<br>Client hostname: {clientHostname}"

        self.diagnosticRecords.insert(0, logstimespanRecord)

        diagnosticDataFields = ["phase", "diagnostic", "result",
                                "startTimestamp", "endTimestamp", "sessionid", "notes"]

        HTMLTableHeaders = ["Notes", "Session ID",
                            "End Timestamp", "Start Timestamp", "Result", "Diagnostic", "Phase"]

        isHeaderAdded = False
        results = {'failed': 0, "warning": 0}
        for record in self.diagnosticRecords:
            htmlRow = bs.new_tag('tr')
            if not isHeaderAdded:
                for HTMLTableHeader in HTMLTableHeaders:
                    htmlHeader = bs.new_tag('th')
                    htmlHeader.string = HTMLTableHeader
                    if HTMLTableHeader == 'Diagnostic':
                        htmlHeader['class'] = 'absorbing-column'
                    if HTMLTableHeader == 'Result':
                        htmlHeader.string = f'{HTMLTableHeader}<br><span id="resultFilter2">Filter&nbsp;&#9660;</span>'
                    htmlRow.insert(0, htmlHeader)
                htmlTable.insert(len(htmlTable.contents), htmlRow)
                htmlRow = bs.new_tag('tr')
                isHeaderAdded = True

            count = 0
            for diagnosticDataField in diagnosticDataFields:
                if record[diagnosticDataField].lower() == "failed":
                    results['failed'] += 1
                if record[diagnosticDataField].lower() == "warning":
                    results['warning'] += 1
                htmlCol = bs.new_tag('td')
                htmlLinkRef = bs.new_tag('a')
                htmlLinkRef['target'] = "_blank"
                if diagnosticDataField == 'diagnostic':  # diagnosticDataField == 'result'
                    htmlLinkRef['href'] = record['urls']['description']
                    htmlLinkRef.string = record[diagnosticDataField]
                    htmlCol.insert(0, htmlLinkRef)
                elif diagnosticDataField == 'result' and (record[diagnosticDataField].lower() != "passed" and record[diagnosticDataField].lower() != "info"):
                    htmlLinkRef['href'] = record['urls']['fix']
                    htmlLinkRef.string = record[diagnosticDataField]
                    htmlCol.insert(0, htmlLinkRef)
                elif 'timestamp' in diagnosticDataField.lower():
                    if record[diagnosticDataField] == '-':
                        htmlCol.string = record[diagnosticDataField]
                    else:
                        try:
                            datetime.strptime(
                                record[diagnosticDataField][:23] + 'Z', '%Y-%m-%dT%H:%M:%S.%fZ')
                            timeStampSplit = (
                                record[diagnosticDataField][:23] + 'Z').split('T')
                            htmlCol.string = timeStampSplit[0] + \
                                'T<br>' + timeStampSplit[1]
                        except:
                            htmlCol.string = '-'
                            pass
                else:
                    htmlCol.string = record[diagnosticDataField]

                htmlRow.insert(count, htmlCol)
                count += 1
            htmlTable.insert(len(htmlTable.contents), htmlRow)

        # Adding content to the HTML body - Summary Table 2
        summaryTable2 = bs.new_tag('table')
        summaryTable2['class'] = 'summaryTable2'
        body.insert(1, summaryTable2)

        summaryTable2Rows = [[results['warning'], results['failed'], '',
                              '<span id="resultFilter1">Diagnostic Results:&nbsp;&#9660;</span>'], ['Warning', 'Failures', '', '']]

        counterTr = 0
        for summaryTable2Row in summaryTable2Rows:
            summaryTb2Row = bs.new_tag('tr')
            counterTd = 0
            for summaryTable2Field in summaryTable2Row:
                summaryTb2Column = bs.new_tag('td')
                if counterTr == 0 and counterTd == 0:
                    summaryTb2Column['class'] = 'summaryTableZeroZeroField'
                summaryTb2Column.string = str(summaryTable2Field) if isinstance(
                    summaryTable2Field, int) else summaryTable2Field
                if counterTr == 0 and counterTd == 2:
                    if results['failed'] > 0:
                        summaryTb2Column['style'] = "background: red;"
                    elif results['failed'] == 0 and results['warning']  > 0:
                        summaryTb2Column['style'] = "background: yellow;"
                    else:
                        summaryTb2Column['style'] = "background: green;"
                summaryTb2Row.insert(0, summaryTb2Column)
                counterTd += 1
            summaryTable2.insert(0, summaryTb2Row)
            counterTr += 1

        # Adding content to the HTML body - Summary Table 3

        summaryTable3 = bs.new_tag('table')
        summaryTable3['class'] = 'summaryTable3'
        body.insert(2, summaryTable3)

        summaryTable3Rows = []
        for summaryCategory, summaryResults in summaryData.items():
            summaryTable3Rows.append([summaryResults['Warning'], summaryResults['Failed'], '',summaryCategory])

        summaryTable3Rows = sorted(summaryTable3Rows, key=lambda x: x[3])
        summaryTable3Rows.append(['Warning', 'Failed', '', ''])

        counterTr = 0
        for summaryTable3Row in summaryTable3Rows:
            warnings = summaryTable3Row[0]
            failures = summaryTable3Row[1]
            summaryTb3Row = bs.new_tag('tr')
            counterTd = 0
            for summaryTable3Field in summaryTable3Row:
                summaryTb3Column = bs.new_tag('td')
                if counterTr == 0 and counterTd == 0:
                    summaryTb3Column['class'] = 'summaryTableZeroZeroField'                
                summaryTb3Column.string = str(summaryTable3Field) if isinstance(
                    summaryTable3Field, int) else summaryTable3Field
                if counterTr < len(summaryTable3Rows)-1 and counterTd == 2:
                    if failures > 0:
                        summaryTb3Column['style'] = "background: red;"
                    elif failures == 0 and warnings  > 0:
                        summaryTb3Column['style'] = "background: yellow;"
                    else:
                        summaryTb3Column['style'] = "background: green;"
                summaryTb3Row.insert(0, summaryTb3Column)
                counterTd += 1
            summaryTable3.insert(0, summaryTb3Row)
            counterTr += 1

        #About formatter https://www.crummy.com/software/BeautifulSoup/bs4/doc/#output-formatters#
        formattedHtmlContent = html.prettify(formatter=None)
        return formattedHtmlContent


class DiagnosticEngineThread(DiagnosticEngine, Thread):
    def __init__(self, filePath: str, configDirectory: str, parentWorkingDirectory: str):
        super().__init__(filePath, configDirectory, parentWorkingDirectory)

        logger.info(
            f'Diagnostic engine thread initialized for file {self.filePath}')
        Thread.__init__(self)

    def run(self):
        super().run()
