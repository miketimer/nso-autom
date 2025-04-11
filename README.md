# nso-autom
AUTOM - Automatic Unit Testing Orchestration Module for Cisco Network Services Orchestrator (NSO)

## The AUTOM package is built for NSO and must be loaded in your local NSO server
Initial build is built in NSO v6.4.1 but it will run in any NSO v5.2.3 or newer.

# AUTOM or Automatic Unit Testing Ochestration Module
### AUTOM is an action package for NSO, the actions available are:
- create-tests   <-- Create-tests generates/updates the necessary files in the packages/name/test folder to compare at the execute-tests or dry-run actions
- execute-tests   <-- Execute-tests creates new files in a execution_log folder with a time-stamp structure, compares the output with the previously created test files and reports success or any failure(s)
- dry-run   <-- Dry-run removes the existing service, dry-runs the addition of the service and compares the output of the dry-run with the previously created test file and reports success or any failure(s)
- load-merge   <-- Load-merge takes input of file-path and will load merge every service_config.xml file it finds in the path.

### Important keywords available in most actions:
- no-networking   <-- Will not touch any south-bound network devices (netsim or real)
- test-in-isolation (available in create-tests, automated in execute-tests)  <-- Removes all other service-instances from NSO before generating clean test cases for each service-instance in sequence.

### A typical workflow will be for testing:
<p>If you already have test files generated previously:</p>
<p>*******************************************************************************************************************************************</p>
<p>Load the packages with generated test files included<br />
Execute load-merge with the input "file-path &lt;path-to-packages-folder&gt;"<br /></p>
<p><code>admin@ncs# autom load-merge service-config file-path packages</code></p>
<p>This will load-merge all service_config.xml files for execution purposes.</p>
<p>*******************************************************************************************************************************************</p>
<p>IF you haven't already created test cases, do the following steps before modifying your package code/yang:</p>
<p>*******************************************************************************************************************************************</p>
<p>Run the autom create-tests action with all-service-instances as keyword and packages-folder-path set to your NSO runtime packages folder, all test cases will have files generated in sequence.</p>
<p><code>admin@ncs# autom create-tests all-service-instances test-in-isolation packages-folder-path packages</code><br /></p>
<p>*******************************************************************************************************************************************</p>
<p>Modify any and all code/templates/yang etc.</p>
<p>Before committing any code to git, run the autom execute-tests action with keyword all-service-instances to check for the failures.</p>
<p><code>admin@ncs# autom execute-tests all-service-instances packages-folder-path packages</code></p>
<p>Open any logs that show the differences found, double check the modifications shown.</p>
<p>If the modifications are expected, run the action autom create-tests all-service-instances (with optional keyword test-in-isolation) to create new test cases.</p>
<p><code>admin@ncs# autom create-tests all-service-instances test-in-isolation packages-folder-path packages</code><br /></p>
<p>Commit package modifications with new test cases included in the tests folder to git. </p>

# AUTOM stores all test files in the packages/name/test folder

Mandatory string input is the "packages-folder-path" which points to the location of the packages folder (where all packages are stored on the NSO server)

# SAMPLE USAGES:

## Create-tests has the options all-service-instances or package-name

admin@ncs# autom create-tests all-service-instances packages-folder-path /var/opt/ncs/current/packages

## If your testing is meant for a pipeline kind of empty NSO, use optional keyword "test-in-isolation"

admin@ncs# autom create-tests all-service-instances packages-folder-path /var/opt/ncs/current/packages test-in-isolation

## Execute-tests reads options from the created test files, creates new execution_log and timestamp folders for each run

admin@ncs# autom execute-tests all-service-instances packages-folder-path /var/opt/ncs/current/packages
