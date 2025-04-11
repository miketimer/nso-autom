# -*- mode: python; python-indent: 4 -*-
"""
Autom capture_config
"""
from datetime import datetime
import difflib
import os
import operator
import re
import json
import socket
import xml.etree.ElementTree as ET
import time
import shutil


import _ncs
from _ncs import maapi
import ncs
from ncs import maagic
from ncs.dp import Action
from .xmlns_parser import parse_xmlns, write_xmlns
from .xpath import xpath
from ..helpers.utils import Folders, Trans
from ..helpers.create_helper import (dryrun_configuration,
                            write_dry_run_data, 
                            find_xpath_for_keypath,
                            service_has_plan, nano_service_ready,
                            get_top_level_parent, 
                            cdb_config_capture, device_config_capture,
                            device_diff_write, capture_modifications,
                            get_pre_config_files,
                            _open_new_trans, delete_kpath_from_cdb,
                            load_cdb_config_from_file, compare_config_devices_affected,
                            wait_for_zombie)

def capture_config(self, uinfo, folder_path, packages_folder_path, service_keypath,
                   current_date_time, no_networking,
                   test_in_isolation, include_children, parent_services,
                   regular_services, child_services, top_level_services,
                   services_list, services_xpath, pre_config_devices,
                   pre_config_xpaths, files_to_load_merge, use_date_time, no_dry_run_data):
    """
    input: self, uinfo, folder_path, packages_folder_path, service_keypath,
           current_date_time, no_networking,
           test_in_isolation, include_children, parent_services,
           regular_services, child_services, top_level_services,
           services_list, services_xpath, pre_config_devices,
           pre_config_xpaths, files_to_load_merge
    Returns result, boolean True and service_config_file_xml (os file path)
    """
    # ignorning R0913 too-many-arguments for capture_config
    # pylint: disable = R0913
    trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
    #sock_maapi = trans.maapi.msock
    # Find the keypath node using maagic
    keypath_node = ncs.maagic.get_node(trans, service_keypath)
    kp_input = [keypath_node._path]
    devices = []
    for kp_node in kp_input:
        keypath_node = ncs.maagic.get_node(trans, kp_node)
        devices_path = keypath_node._path + "/modified/devices"

        devices += ncs.maagic.get_node(trans, devices_path).as_list()
    self.log.info("Devices: ", str(devices))
    if len(files_to_load_merge) > 0:
        for file in files_to_load_merge:
            load_cdb_config_from_file(sock_maapi, file, no_networking, uinfo) 
    # Creating the Folders object and using create_folder_env to setup the files
    files = Folders(packages_folder_path, keypath_node, kp_input, trans)
    files.create_folder_env(use_date_time, current_date_time)
    output_path = files.test_folder
    mod = capture_modifications(trans, uinfo.username, kp_input,
                                              None, files.devices_diff_file_xml,
                                              write_to_file=True)
    #Capturing pre-config for each xpath and getting pre_config_files dict
    pre_config_files = get_pre_config_files(self, trans, thandle, sock_maapi,
                                                pre_config_xpaths, files)
    
    services_keypaths_to_remove = top_level_services + regular_services
    kp_input = [keypath_node._path]
    if "True" in str(test_in_isolation):
        # Test in isolation flow is as follows:
        # 1 Capture Configuration for full backup (completed above)
        # 2 Delete all service instances keypaths except the current one
        # 3 Capture normal after, before, usual diff set files
        # 4 Restore complete before Configuration
        # 5 Re-deploy Reconcile all services (ignoring the current keypath)
        # Saving configuration of service and CDB

        cdb_config_capture(self,
                            sock_maapi,
                            thandle,
                            files.output_folder,
                            phase='before_test_in_isolation',
                            config_types=['xml'],
                            kp_list=kp_input,
                            index=0)

        if len(services_keypaths_to_remove)>0 and keypath_node._path in services_keypaths_to_remove:
            services_keypaths_to_remove.remove(keypath_node._path)
            for path in services_keypaths_to_remove:
                plan_xpath = None
                path_node = ncs.maagic.get_node(trans, path)
                xpath_node = find_xpath_for_keypath(self, keypath_node._path, services_xpath)
                plan_exists, plan_location = service_has_plan(self, path_node._path, xpath_node, uinfo)
                if plan_exists is not False:
                    plan_xpath = xpath(plan_location)
                delete_kpath_from_cdb(sock_maapi, path_node, no_networking, uinfo)
                self.log.info("Path deleted: ", str(path_node._path))
                if plan_exists is not False:
                    max_time_to_wait = 100
                    sleep_time = 1
                    wait_for_zombie(self, max_time_to_wait, sleep_time, root, trans, plan_location, xpath_node)

        else:
            self.log.info("All services could be children, please check input")
            function_result = "The option test-in-isolation doesn't work with only child services as input"
            return function_result, files.service_config_file_xml, files

   
    plan_xpath = None
    # Saving configuration of service and CDB
    cdb_config_capture(self,
                        sock_maapi,
                        thandle,
                        files.output_folder,
                        phase='after',
                        config_types=['service_config_xml', 'cli', 'xml'],
                        kp_list=kp_input,
                        index=0)
    for device in devices:
        dev_config_after_file_cli = device_config_capture(self,
                                            sock_maapi,
                                            trans,
                                            thandle,
                                            device,
                                            files.output_folder,
                                            phase='after',
                                            no_networking=no_networking)

    # Deleting service from CDB, applying transaction
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        xpath_node = find_xpath_for_keypath(self, kp_node._path, services_xpath)
        plan_exists, plan_location = service_has_plan(self, kp_node._path, xpath_node, uinfo)
        if plan_exists is not False:
            plan_xpath = xpath(plan_location)
        delete_kpath_from_cdb(sock_maapi, kp_node, no_networking, uinfo)
        if plan_exists is not False:
            max_time_to_wait = 100
            sleep_time = 1
            wait_for_zombie(self, max_time_to_wait, sleep_time, root, trans, plan_location, xpath_node)


    cdb_config_capture(self,
                        sock_maapi,
                        thandle,
                        files.output_folder,
                        phase='before',
                        config_types=['cli', 'xml'],
                        kp_list=kp_input,
                        index=0)


    # Looping over devices and writing the diff file (comparing before
    #    and after)
    for device in devices:
        dev_config_before_file_cli = device_config_capture(self,
                                        sock_maapi,
                                        trans,
                                        thandle,
                                        device,
                                        files.output_folder,
                                        phase='before',
                                        no_networking=no_networking)
        dev_config_after_file_cli = os.path.join(
            files.output_folder, "%s_after.cli" % (device))
        device_diff_write(device, files.output_folder,
                                        dev_config_before_file_cli,
                                        dev_config_after_file_cli)

    dryrun_configuration(maapi.CONFIG_XML_PRETTY,
                            files.service_config_file_xml, files.cdb_diff_file_xml,
                            uinfo)
    if "True" in str(test_in_isolation):
        load_file = files.config_before_test_in_isolation_file_xml
    else:
        # not test_in_isolation
        load_file = files.config_after_file_xml
    load_cdb_config_from_file(sock_maapi, load_file, no_networking, uinfo)
    devices_list = compare_config_devices_affected(trans, kp_input, root)
    for device in pre_config_devices:
        if device in devices_list:
            break
        else:
            pre_config_devices.remove(device)
    if no_dry_run_data == True:
        self.log.info("Skipping dry-run data for exec")
    else:
        write_dry_run_data(files.folder_path, kp_input, test_in_isolation, pre_config_files, pre_config_devices)
    
    if "True" in str(test_in_isolation):
        os.remove(files.config_before_test_in_isolation_file_xml)
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        if no_networking:
            redeploy_input = kp_node.re_deploy.get_input()
            redeploy_input.reconcile.create()
            redeploy_input.no_networking.create()
            kp_node.re_deploy(redeploy_input)
            for device in devices:
                root.ncs__devices.ncs__device[device].compare_config()
        else:
            redeploy_input = kp_node.re_deploy.get_input()
            redeploy_input.reconcile.create()
            kp_node.re_deploy(redeploy_input)

    for path in services_keypaths_to_remove:
        path_node = ncs.maagic.get_node(trans, path)
        redeploy_input = path_node.re_deploy.get_input()
        redeploy_input.reconcile.create()
        path_node.re_deploy(redeploy_input)
        if no_networking:
            devices_path_mod = path_node._path + "/modified/devices"
            devices_list = ncs.maagic.get_node(
                trans, devices_path_mod).as_list()
            for device_name in devices_list:
                root.ncs__devices.ncs__device[
                    device_name].compare_config()
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        if include_children:
            path = get_top_level_parent(self, uinfo, trans,
                                        kp_node._path,
                                        services_list)

            self.log.info("Top Level svc Path: %s " % path)
            if path is not None:
                k_node = ncs.maagic.get_node(trans, path)
                redeploy_input = k_node.re_deploy.get_input()
                redeploy_input.reconcile.create()
                redeploy_input.no_networking.create()
                k_node.re_deploy(redeploy_input)
                k_node.re_deploy(redeploy_input)
                self.log.info("Re-deploy reconcile no-networking has been performed twice on the parent node: %s " % path)
    devices_diff_list = {}
    for device in devices:
        devices_diff_list[device] = [os.path.join(files.output_folder,
                                        "%s_before.cli" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_after.cli" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_before.xml" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_after.xml" % (device))]
    iter = 0
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        xpath_node = find_xpath_for_keypath(self, kp_node._path, services_xpath)
        plan_exists, plan_location = service_has_plan(self, kp_node._path, xpath_node, uinfo)
        if plan_exists is not False:
            plan_xpath = xpath(plan_location)
        if plan_exists is not False:
            max_time_to_wait = 300
            sleep_time = 1
            plan_ready = nano_service_ready(self, uinfo, trans, plan_location, sock_maapi, max_time_to_wait, sleep_time)
        # TODO: Add service test case here
        iter +=1
    # Service Modify flow below, store service config, CDB and device config
    # Before first, After when modified configuration has been applied
    
    function_result = True
    return function_result, files.service_config_file_xml, files
