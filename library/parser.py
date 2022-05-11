import re
import logging
from typing import Union
from .utilities import getAggregatedLists, measureExecution
logger = logging.getLogger('main')
def __getParsedSignature(fileContent: str, signature: str, labels: list = [], multipleOccurenciesEnabled=False) -> Union[list, dict]:
    '''
    Return tokenized signatures parsed using regular expression

    :param fileContent:
    :param signature:
    :param labels:
    :param multipleOccurenciesEnabled:

    Examplo of regex named capture group
    e.g.: "CLIENT :(?P<type>.*PCoIP.*):(?P<version>\\d+.\\d+.\\d+)_.*is starting up.*"
    "?P<type>" and "?P<version>" are sintaxes used to name the capture groups
    '''
    tokens = None
    if multipleOccurenciesEnabled == False:
        # Single occurrences of the signature
        searchResult = re.search(
            signature, fileContent, flags=re.MULTILINE)

        if not searchResult:
            return {}

        # Return a dict with labeled tokens, because the signature pattern contains named capture groups
        labeledTokens = searchResult.groupdict()

        if labeledTokens:
            tokens = labeledTokens
        else:
            # Return a list as last resort, because tokens could not be labeled
            unlabeledtokens = searchResult.groups()

            if len(unlabeledtokens) > 0:
            
                labeledTokens = getAggregatedLists(labels, unlabeledtokens)
            
                if len(labeledTokens) > 0:
                    tokens = labeledTokens
                else:
                    tokens = unlabeledtokens
            else:
                return {}
            # If signature pattern does not contains named capture groups,
            # and labels are defined by the signature settings from the json file
            # then a dict can be built using list aggregation


    else:
        labeledTokens = []
        # if the signature contains named capture sintax then used re.compile and finditer to create a list of dicts
        # It is useful to name a value, or to classify a value
        if '?P<' in signature:
            pattern = re.compile(signature, re.MULTILINE)

            for matchObj in pattern.finditer(fileContent):
                groupdict = matchObj.groupdict()
                if groupdict:
                    labeledTokens.append(matchObj.groupdict())

        # Return a list of dict with labeled tokens, because the signature pattern contains named capture groups
        if labeledTokens:
            tokens = labeledTokens

        else:
            # Return list of tuples containing multiple occurrences of a signature
            unlabeledtokensGroup = re.findall(
                signature, fileContent, flags=re.MULTILINE)
            if len(unlabeledtokensGroup) > 0:
                if len(unlabeledtokensGroup[0]) == len(labels): #if addLabels:
                    labeledtokensGroup = []

                    for unlabeledtokens in unlabeledtokensGroup:
                        labeledTokens = getAggregatedLists(
                            labels, unlabeledtokens)
                        labeledtokensGroup.append(labeledTokens)

                    tokens = labeledtokensGroup
                else:
                    tokens = unlabeledtokensGroup
            else:
                return []
    return tokens


@measureExecution
def getParsedSignatureGroups(fileContent: str, signaturesGroups: str):

    def getReversedMultilineString(fileContent) -> str:
        reversedList = ''
        lines = fileContent.splitlines()
        for line in lines:
            reversedList = line + '\n' + reversedList

        return reversedList

    datasets = []
    reversedFileContent = ''
    isReverseLookupEnabled = False

    for groupName, groupSettings in signaturesGroups.items():
        for signatureSettings in groupSettings['signatures']:

            if 'reverseLookup' in signatureSettings and isinstance(signatureSettings['reverseLookup'], bool) and signatureSettings['reverseLookup']:
                isReverseLookupEnabled = True
                if not reversedFileContent:
                    reversedFileContent = getReversedMultilineString(fileContent)

            if isReverseLookupEnabled:
                content = reversedFileContent
                isReverseLookupEnabled = False
            else:
                content = fileContent

            dataset = {}
            # if isinstance(signatureSettings['signaturePattern'], list):
            #     signatures = signatureSettings['signaturePattern']

            if isinstance(signatureSettings['signaturePattern'], str):
                signature = signatureSettings['signaturePattern']
            else:
                raise TypeError(
                    "The signature attribute must be string or list")

            isMultipleOccurenciesEnabled = signatureSettings[
                'multipleOccurencies'] if 'multipleOccurencies' in signatureSettings else False

            dataset["groupName"] = groupName
            dataset["domain"] = groupSettings["domain"]
            dataset["signatureName"] = signatureSettings['signatureName']

            if "labels" in signatureSettings:
                labels = signatureSettings["labels"]
                # To return a dict, all necessary labels must be available to name capture data, otherwise, a list or None will return
                # labels can come from regex capture groups or the labels json attribute
                tokens = __getParsedSignature(
                    content, signature, labels, multipleOccurenciesEnabled=isMultipleOccurenciesEnabled)
            else:
                # to return dict, regex capture groups must be defined, otherwise, a list or None will return
                tokens = __getParsedSignature(
                    content, signature, multipleOccurenciesEnabled=isMultipleOccurenciesEnabled)

            dataset["tokens"] = tokens
            datasets.append(dataset)

    return datasets
