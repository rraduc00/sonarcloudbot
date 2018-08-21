#!/usr/bin/env python3

"""
@Author Razvan Raducu

CONSTRAINTS: As of 26th of July 2018 SonarCloud API is limited to the first 10000 results. 
You cannot query more than that. THIS CONSTRAINT IS APPLIED TO EVERY SINGLE QUERY. That is,
when requesting all the projects that meet the filter, only 10000 results can be seen.
When requesting the vulnerability list of the corresponeding key to each result, only
10000 vulnerabilities can be seen and so on.

Problem 1.
We found that we cannot just append every result of the queries looking for vulnerabilities
into one single file because the result is a malformatted JSON file since there cannot be
more than one JSON object per file. 
Solution 1.
The solution is to actually request the first 500 
results of the vulnerability query (page 1) and write them to a file. Immediately after,
parse that file and request the corresponding source code. When we got it, request
the next 500 (page 2) vulnerabilities, write the result to a file (not append) and, once again,
request the sourcecode. This loop goes on until we reach the 10000 results limit imposed
by Sonarcloud's API. 

Problem 2.
Turns out each vulnerable code line is a different entry from the same JSON list. That is,
we could have 13 different results, 13 different issues, but they are just different lines
of the same file. We end up having 13 copies of the same sourcode but with different name. 
Solution 2.
What we came up with is simply compiling all vulnerable lines within the same file, download
the file and append the lines as a comment. (Appending at the end of the file)

"""


# pip install requests
import requests 
import json
import sys
import os.path

############################↓↓↓ Requesting project IDS ↓↓↓######################################
def APIProjectRequest():
	global remainingResults
	global queryJsonResponse

	url = 'https://sonarcloud.io/api/components/search_projects'
	parameters = {'filter':'security_rating>=2 and languages=c','p': p,'ps': ps }

	try:
		req = requests.get(url, params=parameters)
	except requests.exceptions.RequestException as e:
		print(e)
		print("Aborting")
		sys.exit(1)

	print("#### Request made to " + req.url + " ####")

	# Writing the results of the query to a file
	queryJsonResponse = req.json()
	totalResults = queryJsonResponse['paging']['total']
	print("#### Query generated " + str(totalResults) + " results ####")

	

	#print("#### Writing page " + str(p) + " to file ####")

	# The writing is done in 'a' (append) mode (optional)
	#print(json.dumps(queryJsonResponse, indent=4), file=open('sonarQueryResults.json','a'))

	remainingResults = totalResults - (ps*p)
	if remainingResults < 0:
		remainingResults = 0
	print("#### There are " + str(remainingResults) + " left to print ####")

p = 1
ps = 500
remainingResults = 0
queryJsonResponse = 0

APIProjectRequest()

while remainingResults > 500:
	if p == 20: # 500 results * 20 pages = 10000 limit reached
		break
	p+=1
	print("#### Querying again. Requesting pageindex " + str(p) + " ####")
	APIProjectRequest()


#################################↑↑↑  Requesting project IDS  ↑↑↑################################

##################################↓↓↓ Requesting sourcecode ↓↓↓##################################

"""
When requesting sourcecode only the key is needed, as stated by the api DOCS 
https://sonarcloud.io/web_api/api/sources/raw. The key is ['issues']['component']
value from the queryJsonResponse at this moment.
"""

def APISourceCodeRequest():
	url = 'https://sonarcloud.io/api/sources/raw'

	# For each project ID, we get its source code and name it according to the following pattern:
	# fileKey_startLine:endLine.c

	with open('sonarQueryResults.json') as data_file:    
		data = json.load(data_file)

	for issue in data['issues']:
		fileKey = issue['component']
		parameters = {'key':fileKey}
		try:
			req = requests.get(url, params=parameters)
		except requests.exceptions.RequestException as e:
			print(e)
			print("Aborting")
			sys.exit(1)

		print("#### Request made to " + req.url + " ####")

		# We replace '/' with its hex value 2F
		vulnerableFile = ("./"+(str(fileKey)).replace('/','2F'))
		print("Looking if "+ vulnerableFile+ " exists.")
		if not os.path.isfile(vulnerableFile):
			print("++++> File doesn't exist. Creating <++++")
			with open(vulnerableFile, 'ab+') as file:
				file.write(req.content)
				file.write(str.encode("//\t\t\t\t\t\t↓↓↓VULNERABLE LINES↓↓↓\n"))
				file.write(str.encode("// Line starting at: " + str(issue['textRange']['startLine']) + ", ending at: " + str(issue['textRange']['endLine']) + ", startOffset: " + str(issue['textRange']['startOffset']) + ", endOffset: " + str(issue['textRange']['endOffset'])+"\n"))
		else:
			print("----> File exists. Appending vulnerable lines <----")
			with open(vulnerableFile, 'ab+') as file:
				file.write(str.encode("// Line starting at: " + str(issue['textRange']['startLine']) + ", ending at: " + str(issue['textRange']['endLine']) + ", startOffset: " + str(issue['textRange']['startOffset']) + ", endOffset: " + str(issue['textRange']['endOffset'])+"\n"))

		
		

##################################↑↑↑ Requesting sourcecode ↑↑↑##################################

#################################↓↓↓ Requesting vulnerabilities ↓↓↓##############################
"""
Here are the keys of every single repo that meets the following conditions:
	1. Is public 
	2. Is written in C language
	3. Its security rating is >= 2
"""
projectIds = "" 
for component in queryJsonResponse['components']:
	# It's appended into the list to compose the following request.
	projectIds += str(component['key']) + ","

# Deletion of trailing comma. (Right side of index specifier is exclusive)
projectIds = projectIds[:-1]
#print(projectIds)

p = 1
remainingResults = 0

def APIVulnsRequest():
	global remainingResults
	url = 'https://sonarcloud.io/api/issues/search'
	parameters = {'projects':projectIds, 'types':'VULNERABILITY', 'languages':'c', 'ps':500, 'p': p }

	try:
		req = requests.get(url, params=parameters)
	except requests.exceptions.RequestException as e:
		print(e)
		print("Aborting")
		sys.exit(1)

	print("#### Request made to " + req.url + " ####")

	# Writing the results of the query to a file
	queryJsonResponse = req.json()
	print(json.dumps(queryJsonResponse, indent=4), file=open('sonarQueryResults.json','a'))

	## REQUESTING SOURCECODE ##
	print("#### REQUESTING SOURCECODE ####")
	APISourceCodeRequest()

	totalResults = queryJsonResponse['total']
	print("#### Query generated " + str(totalResults) + " results ####")


	remainingResults = totalResults - (ps*p)
	if remainingResults < 0:
		remainingResults = 0
	print("#### There are " + str(remainingResults) + " left to print ####")

APIVulnsRequest()

while remainingResults > 500:
	if p == 20: # 500 results * 20 pages = 10000 limit reached
		break
	p+=1
	print("#### Querying again. Requesting pageindex " + str(p) + " ####")
	APIVulnsRequest()

###############################↑↑↑ Requesting vulnerabilities ↑↑↑################################
