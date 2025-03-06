# -*- mode: python; python-indent: 4 -*-
"""
AUTOM dry_run_execute_action
"""
from datetime import datetime
import difflib
import os
import socket
import subprocess
import time
import ncs
import _ncs
from _ncs import maapi
from ncs.dp import Action
from ..helpers.tools import config_cli_cleanup, get_config_from_device, write_file, read_file
from ..comparison.config_comparison import compare_xml
from ..helpers.xpath import xpath
from ..helpers.create_helper import dryrun_configuration, service_has_plan, zombie_exists, delete_kpath_from_cdb, wait_for_zombie
from ..helpers.create_helper import _open_new_trans, _close_trans, compare_config_devices_affected
from ..helpers.create_helper import load_cdb_config_from_file, compare_config_devices_affected
from ..helpers.create_helper import redeploy_reconcile_no_networking, redeploy_reconcile

def run_command(command):
    return subprocess.getoutput(command)

class AutomDryRunExecute(Action):
    """
    AutomDryRunExecute class - inherits from ncs.dp.Action
    """
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        """
        :param uinfo [TODO:type]: [TODO:description]
        :param name [TODO:type]: [TODO:description]
        :param kp [TODO:type]: [TODO:description]
        :param input [TODO:type]: [TODO:description]
        :param output [TODO:type]: [TODO:description]
        :param trans [TODO:type]: [TODO:description]
        """
        # ignoring W0622 redefined-builtin for input
        # ignorning R0913 too-many-arguments for cb_action
        # pylint: disable = W0622 R0913
        self.log.info("autom_dry_run_execute_action called")
        # Opening socket, connecting to low-level maapi API
        _ncs.dp.action_set_timeout(uinfo, 180)
        trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
        folder_path = input.file_path
        #command = f'find {folder_path} | grep "dry_run_data.txt"'
        command = f'find {folder_path} -name "dry_run_data.txt"'
        command_output = run_command(command)
        self.log.info(command_output)
        test_data_array = []
        file  = command_output.splitlines()
        exec_result =""
        for item in file:
            dry_run_data = read_file(item).splitlines()
            try:
                for data in dry_run_data[0].split(";"):
                    if len(str(data))>0:
                        keypath_node = ncs.maagic.get_node(trans, data)
                        xpath_node = xpath(keypath_node)
                    else:
                        break
                    self.log.info("Deleting keypath: ", keypath_node._path)
                    #xpath_node = CreateAction.find_xpath_for_keypath(self, keypath_node._path, service_xpath)
                    plan_exists, plan_location = service_has_plan(self, keypath_node._path, xpath_node, uinfo)
                    if plan_exists is not False:
                        plan_xpath = xpath(plan_location)
                    delete_kpath_from_cdb(sock_maapi, keypath_node, input.no_networking, uinfo) # sock_maapi, kp_node, no_networking, uinfo
                    service_existed = True
                    sleep_time = 1
                    max_time_to_wait = 100
                    if plan_exists is not False:
                        wait_for_zombie(self, max_time_to_wait, sleep_time, root, trans, plan_location, xpath_node)
            except Exception as e:
                service_existed = False
                self.log.info("Service instance doesn't exist, continuing dry-run-execution")

            #dryrun_configuration writes diff in xml format to a file (second input parameter)
            cdb_diff = dryrun_configuration(maapi.CONFIG_XML_PRETTY,
                              dry_run_data[1], dry_run_data[2].replace("cdb","dry_run"), uinfo)
            if service_existed == True:
                load_cdb_config_from_file(sock_maapi, dry_run_data[1], input.no_networking, uinfo)
                if input.no_networking:
                    redeploy_reconcile_no_networking(keypath_node)
                else:
                    redeploy_reconcile(keypath_node)
                kp_list = []
                kp_list.append(keypath_node)
                devices_list = compare_config_devices_affected(trans, kp_list, root)
            compare_path = os.path.dirname(dry_run_data[2])
            compare_result, fd = compare_xml(dry_run_data[2], dry_run_data[2].replace("cdb","dry_run"), self.log, compare_path)
            #os.remove(dry_run_data[2].replace("cdb","dry_run"))
            #_close_trans(trans)
            if compare_result == True:
                self.log.info("Comparison of ", dry_run_data[2], " and ",  dry_run_data[2].replace("cdb","dry_run"), " was SUCCESSFUL, no differences found")
                exec_result = exec_result + "Tests successfully passed on executed path: " + compare_path + "\n"
            else:
                self.log.info("Comparison of ", dry_run_data[2], " and ",  dry_run_data[2].replace("cdb","dry_run"), " FAILED, differences found, see ", os.path.dirname(dry_run_data[2]), "/diff_log.html for details")
                exec_result = exec_result + "Test execution found that the xml comparison failed, see " + compare_path+"/diff_log.html for details\n"
        _close_trans(trans)
        output.result = exec_result
