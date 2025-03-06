# nso-autom
AUTOM - Automatic Unit Testing Orchestration Module for Cisco Network Services Orchestrator (NSO)

## The AUTOM package is built for NSO and must be loaded in your local NSO server
Initial build is in NSO 6.4.1 but it will run in any NSO 5.2.x or newer.

# AUTOM or Automatic Testing Ochestration Module 
AUTOM is a action package for NSO, the actions available are:
- create-tests   <-- Create-tests generates/updates the necessary files in the packages/name/test folder to compare at the execute-tests or dry-run actions
- execute-tests   <-- Execute-tests creates new files in a execution_log folder with a time-stamp structure, compares the output with the previously created test files and reports success or any failure(s)
- dry-run   <-- Dry-run removes the existing service, dry-runs the addition of the service and compares the output of the dry-run with the previously created test file and reports success or any failure(s)
- load-merge   <-- Load-merge takes input of file-path and will load merge every service_config.xml file it finds in the path.

Important keywords available in most actions:
- no-networking   <-- Will not touch any south-bound network devices (netsim or real)
- test-in-isolation (available in create-tests, automated in execute-tests)  <-- Removes all other service-instances from NSO before generating clean test cases for each service-instance in sequence.

A typical workflow will be for testing: 
Load the packages with generated test files included
Execute load-merge with the input "file-path <path-to-packages-folder>"
This will load-merge all service_config.xml files for execution purposes. Remember that all-service-instances is the default keyword and all test cases will have files generated in sequence.

# AUTOM stores all test files in the packages/name/test folder

Mandatory string input is the "packages-folder-path" which points to the location of the packages folder (where all packages are stored on the NSO server)

# SAMPLE USAGES:

## Create-tests has the options all-service-instances or package-name

admin@ncs# autom create-tests all-service-instances packages-folder-path /var/opt/ncs/current/packages 

## If your testing is meant for a pipeline kind of empty NSO, use optional keyword "test-in-isolation"

admin@ncs# autom create-tests all-service-instances packages-folder-path /var/opt/ncs/current/packages test-in-isolation 
