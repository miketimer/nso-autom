# -*- mode: python; python-indent: 4 -*-
"""
AUTOM autom_execute_action
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
from ..helpers.create_helper import _open_new_trans, _open_new_wr_trans, _close_trans, compare_config_devices_affected, is_top_level_parent
from ..helpers.create_helper import load_cdb_config_from_file, compare_config_devices_affected, get_service_keypaths, get_services_check_sync_result
from ..helpers.create_helper import redeploy_reconcile_no_networking, redeploy_reconcile
from ..helpers.capture_config import capture_config

def run_command(command):
    return subprocess.getoutput(command)

class AutomExecuteAction(Action):
    """
    AutomExecuteAction class - inherits from ncs.dp.Action
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
        now = datetime.now()
        result = False
        current_date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        trans, thandle, sock_maapi, root = _open_new_wr_trans(uinfo)
        folder_path = input.packages_folder_path
        command = f'find {folder_path} -name "dry_run_data.txt"'
        command_output = run_command(command)
        self.log.info(command_output)
        test_data_array = []
        file_lines = command_output.splitlines()
        self.log.info(file_lines)
        exec_result =""
        ignore_xpaths = input.ignore_xpaths
        services_list = get_services_check_sync_result(self, root)
        child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                                     uinfo,
                                     services_list,
                                     ignore_xpaths)
        compare_results, all_tests_passed, exec_result = self.process_dry_run_files(
            file_lines, uinfo, input, trans, current_date_time,
            parent_services, regular_services, child_services, top_level_services,
            services_list, services_xpath, sock_maapi
        )
        _close_trans(trans)
        if input.store_test_log:
            exec_log_file = read_file(os.path.join(folder_path, "autom","python","autom","comparison", "test_execution_log.html"))
            exec_log_file.replace("<!-- REPLACEME -->", str(compare_results))
            if os.path.exists(os.path.join(folder_path, "../", "tests")):
                write_file(os.path.join(folder_path, "../", "tests", current_date_time + "_execution_log.html"), exec_log_file)
            else:
                os.makedirs(os.path.join(folder_path, "../", "tests"), exist_ok=True)
                write_file(os.path.join(folder_path, "../", "tests", current_date_time + "_execution_log.html"), exec_log_file)
        if False in all_tests_passed:
            output.result = exec_result + str(compare_results)
        else:
            output.result = "All tests passed, no differences found in the compared files"

        #output.result = compare_results
    def process_dry_run_files(
            self, file_lines, uinfo, input, trans, current_date_time,
            parent_services, regular_services, child_services, top_level_services,
            services_list, services_xpath, sock_maapi):
        compare_results = []
        all_tests_passed = []
        exec_result = ""
        for line in file_lines:
            dry_run_data = read_file(line).splitlines()
            files_to_load_merge = []
            try:
                if len(str(dry_run_data[0].split(";")[0])) > 0:
                    keypath_node = ncs.maagic.get_node(trans, dry_run_data[0].split(";")[0])
                    xpath_node = xpath(keypath_node)
                    service_existed = True
                    self.log.info("Service is present")
                else:
                    break
            except:
                service_existed = False
                self.log.info("Service is not present, loading service config")
                load_cdb_config_from_file(sock_maapi, dry_run_data[1], input.no_networking, uinfo)
                keypath_node = ncs.maagic.get_node(trans, dry_run_data[0].split(";")[0])
                xpath_node = xpath(keypath_node)
            test_in_isolation = dry_run_data[3].split(": ")[1]
            self.log.info("Test In Isolation var == ", test_in_isolation.strip())
            for item in dry_run_data:
                if "_before.xml" in item:
                    files_to_load_merge.append(item)
                if "pre_config" in item:
                    files_to_load_merge.append(item)
            self.log.info("Files to load merge: ", files_to_load_merge)
            result, service_config_file_xml, files = capture_config(
                self, uinfo, input.packages_folder_path, input.packages_folder_path, keypath_node,
                current_date_time, input.no_networking, test_in_isolation, False, parent_services,
                regular_services, child_services, top_level_services, services_list, services_xpath,
                [], [], files_to_load_merge, True, True
            )
            if "True" in str(result):
                compare_path = files.compare_folder
                compare_result, fd = compare_xml(
                    os.path.join(compare_path, "cdb_diff.xml"),
                    os.path.join(files.output_folder, "cdb_diff.xml"),
                    self.log, "cdb_diff_log", files.output_folder
                )
                if compare_result is True:
                    result_string = (
                        "Service instance ", keypath_node, "\nComparison of ",
                        os.path.join(compare_path, "cdb_diff.xml"), " and ",
                        os.path.join(files.output_folder, "cdb_diff.xml"),
                        " was SUCCESSFUL, no differences found\n"
                    )
                    self.log.info(result_string)
                    exec_result += "Tests successfully passed on executed path: " + str(compare_path) + "\n"
                    compare_results.append(result_string)
                    all_tests_passed.append(True)
                else:
                    result_string = (
                        "Service instance ", keypath_node, "\nComparison of ",
                        os.path.join(compare_path, "cdb_diff.xml"), " and ",
                        os.path.join(files.output_folder, "cdb_diff.xml"),
                        " FAILED, differences found, see ",
                        os.path.join(compare_path, "cdb_diff_log.html"), " for details\n"
                    )
                    self.log.info(result_string)
                    exec_result += (
                        "Test execution found that the xml comparison failed, see "
                        + str(os.path.join(files.output_folder, "cdb_diff_log.html")) + " for details\n"
                    )
                    compare_results.append(result_string)
                    all_tests_passed.append(False)
                compare_path = files.compare_folder
                compare_result_get_modif, fd = compare_xml(
                    os.path.join(compare_path, "devices_diff.xml"),
                    os.path.join(files.output_folder, "devices_diff.xml"),
                    self.log, "get_modifications_log", files.output_folder
                )
                if compare_result_get_modif is True:
                    result_string += (
                        "\nService instance ", keypath_node, "\nComparison of ",
                        os.path.join(compare_path, "devices_diff.xml"), " and ",
                        os.path.join(files.output_folder, "devices_diff.xml"),
                        " was SUCCESSFUL, no differences found\n"
                    )
                    self.log.info(result_string)
                    exec_result += "Tests successfully passed on executed path: " + str(compare_path) + "\n"
                    compare_results.append(result_string)
                    all_tests_passed.append(True)
                else:
                    result_string += (
                        "\nService instance ", keypath_node, "\nComparison of ",
                        os.path.join(compare_path, "devices_diff.xml"), " and ",
                        os.path.join(files.output_folder, "devices_diff.xml"),
                        " FAILED, differences found, see ",
                        os.path.join(compare_path, "get_modifications_log.html"), " for details\n"
                    )
                    self.log.info(result_string)
                    exec_result += (
                        "Test execution found that the xml comparison failed, see "
                        + str(os.path.join(files.output_folder, "get_modifications_log.html")) + " for details\n"
                    )
                    compare_results.append(result_string)
                    all_tests_passed.append(False)
            else:
                continue
        return compare_results, all_tests_passed, exec_result
