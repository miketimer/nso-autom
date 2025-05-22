# -*- mode: python; python-indent: 4 -*-
"""
AUTOM load_merge_service_action
"""

import socket
import os
import subprocess
import time
import ncs
import _ncs
from _ncs import maapi
from ncs.dp import Action
from ..helpers.tools import config_cli_cleanup, get_config_from_device, write_file, read_file
from ..comparison.config_comparison import compare_xml
from ..helpers.xpath import xpath
from .autom_create_action import AutomCreateAction
from ..helpers.create_helper import dryrun_configuration

def run_command(command):
    return subprocess.getoutput(command)

class LoadMergeServiceConfig(Action):
    """
    LoadMergeServiceConfig class - inherits from ncs.dp.Action
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
        self.log.info(" load_service_action called")
        # Opening socket, connecting to low-level maapi API
        _ncs.dp.action_set_timeout(uinfo, 180)

        sock_maapi = trans.maapi.msock
        thandle = trans.th
        folder_path = input.file_path
        root = ncs.maagic.get_root(trans)
        command = f'find ./{folder_path} -name "service_config.xml"'
        #command = 'ls -ltr'
        command_output = run_command(command)
        self.log.info(command_output)
        test_data_array = []
        file  = command_output.splitlines()
        for item in file:
            if "execution_log" in item:
                continue
            try:
                thandle_write = maapi.start_trans2(sock_maapi, _ncs.RUNNING,
                                    _ncs.READ_WRITE,
                                    uinfo.usid)
                maapi.load_config(sock_maapi, thandle_write,
                        maapi.CONFIG_XML_PRETTY + maapi.CONFIG_MERGE,
                        item)
                maapi.apply_trans(sock_maapi,
                            thandle_write,
                            keepopen=False)

            except Exception as e:
                raise e

        output.result = "Successfully load merged service_config for folder " + folder_path
