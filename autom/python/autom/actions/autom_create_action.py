# -*- mode: python; python-indent: 4 -*-
"""
Autom_create_action
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
from ..helpers.capture_config import capture_config
from ..helpers.xmlns_parser import parse_xmlns, write_xmlns
from ..helpers.xpath import xpath
from ..helpers.tools import (config_cli_cleanup, get_config_from_device,
                             save_configuration,
                             write_file, read_file, config_exclude,
                             get_module_name_from_prefix,
                             strip_xpath_prefixes,
                             get_plan_location,
                             xpath_node,
                             xpath_kp)
from ..helpers.utils import Folders, Trans
from ..helpers.create_helper import (get_services_check_sync_result,
                            get_service_keypaths, _open_new_trans, _close_trans)


class AutomCreateAction(Action):
    """
    AutomCreateAction
    """

    # Action MAIN code
    # Uses maapi object with low-level API _ncs as well as the very high level
    #     Maagic functionality
    # See inline comments for what is being accomplished
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        """
        [TODO:description]

        :param self [TODO:type]: [TODO:description]
        :param uinfo [TODO:type]: [TODO:description]
        :param name [TODO:type]: [TODO:description]
        :param kp [TODO:type]: [TODO:description]
        :param input [TODO:type]: [TODO:description]
        :param output [TODO:type]: [TODO:description]
        :param trans [TODO:type]: [TODO:description]
        """
        _ncs.dp.action_set_timeout(uinfo, 6000)
        trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
        # Generating date-time for folder names
        now = datetime.now()
        result = False
        current_date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        folder_path = os.path.dirname(__file__)
        child_services = []
        mod_pos_p_list = {}
        mod_neg_p_list = {}
        all_services = []
        child_svc = []
        parent_svc = []
        regular_svc = []
        top_level_svc = []
        no_networking = False
        test_in_isolation = False
        if input.no_networking:
            no_networking = True
        if input.test_in_isolation:
            test_in_isolation = True
        dry_run = False
        if input.dry_run:
            dry_run = True
        services_list = get_services_check_sync_result(self, root)
        index = 1
        # If specific service instance keypaths is chosen as the
        #     input (list):
        parent_services = []
        child_services = []
        regular_services = []
        top_level_services = []
        if len(input.service_instance) > 0:
             child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                                     uinfo,
                                     services_list, input.ignore_xpaths)
             self.log.info("All Parent services : %s " % parent_services)
             self.log.info("All Child services : %s " % child_services)
             self.log.info("All Regular services: %s " % regular_services)
             for path in input.service_instance:
                 keypath_node = ncs.maagic.get_node(trans, path)
                 if keypath_node._path in child_services:
                     child_svc.append(keypath_node._path)
                 if keypath_node._path in parent_services:
                     parent_svc.append(keypath_node._path)
                 if keypath_node._path in regular_services:
                     regular_svc.append(keypath_node._path)
                 if keypath_node._path in top_level_services:
                     top_level_svc.append(keypath_node._path)

             child_services = child_svc
             parent_services = parent_svc
             regular_services = regular_svc
             top_level_services = top_level_svc
             
        # Below code handles both ALL service instances and
        # specific chosen servicepoints services check-sync
        # returns a list of all service instances with their xpath
        else:
            child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                                    uinfo,
                                    services_list, input.ignore_xpaths)
        # By default (boolean exclude-children) the child services of
        # stacked services will be removed from testing separately.
        # To add these for testing, the include-children must be set
        use_test = True
        self.log.info("All_services: %s " % all_services)
      
        if input.include_children:
            all_services = top_level_services + parent_services + regular_services + child_services
        else:
            all_services = top_level_services + regular_services
        if not all_services:
            self.log.info("Input does not include children (add include_children keyword)")
            result = False
            output.result = str(
                result
            ) + ":: Failed at generating any files, input does not include children (add include_children keyword)\nWARNING: testing of child services of stacked parent services will result in unexpected errors"
            return result


        if test_in_isolation==True:
            for service_keypath in top_level_services:
                result, service_config_file_xml, files = capture_config(self,
                    uinfo, folder_path, input.packages_folder_path,
                    service_keypath, current_date_time, no_networking,
                    True, input.include_children, parent_services,
                    regular_services, child_services, top_level_services,
                    services_list, services_xpath, input.pre_config_devices,
                    input.pre_config_cdb, [], False, False)
            for service_keypath in regular_services:
                result, service_config_file_xml, files = capture_config(self,
                    uinfo, folder_path, input.packages_folder_path,
                    service_keypath, current_date_time, no_networking,
                    True, input.include_children, parent_services,
                    regular_services, child_services, top_level_services,
                    services_list, services_xpath, input.pre_config_devices,
                    input.pre_config_cdb, [], False, False)
        else:
            for service_keypath in all_services:
                result, service_config_file_xml, files = capture_config(self,
                    uinfo, folder_path, input.packages_folder_path,
                    service_keypath, current_date_time, no_networking,
                    False, input.include_children, parent_services,
                    regular_services, child_services, top_level_services,
                    services_list, services_xpath, input.pre_config_devices,
                    input.pre_config_cdb, [], False, False)              
        if result == True:
            output.result = str(
                        result
                        ) + " :: Successfully generated and wrote all files to the specified path"
        else:
            output.result = str(
                        result
                        ) + ":: Failed at generating any files, please check input parameters"
