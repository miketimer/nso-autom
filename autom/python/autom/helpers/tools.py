# -*- mode: python; python-indent: 4 -*-
"""
Autom helper tools
"""
import socket
import re

import _ncs
from _ncs import maapi
import ncs
from .xpath import xpath

PREFIX=re.compile('[^/[\]\'"\s ]+:')

def strip_xpath_prefixes(xpath):
    return re.sub(PREFIX, '', xpath)

def xpath_kp(log, root, xpath):
    trans = ncs.maagic.get_trans(root)
    cursor = trans.query_start(expr=xpath,
        context_node='/', chunk_size=10, initial_offset=0, result_as=1, select = [], sort=[])
    keypaths = [ r[0] for r in ncs.maapi.Maapi().query_result(cursor) ]
    log.debug(f'xpath_kp: xpath {xpath} kp {str(keypaths)}')
    if len(keypaths) == 1:
        return str(keypaths[0])
    assert len(keypaths) < 2, f'xpath {xpath}  yielded {len(keypaths)} results'

def xpath_node(log, root, xpath):
    kp = xpath_kp(log, root, xpath)
    if kp is not None:
        return ncs.maagic.cd(root, kp)

def get_plan_location(log, root, path, str_xpath):
    service = xpath_node(log, root, xpath(path))
    assert hasattr(path, 'plan_location'), f"No plan found at path {path}"
    if service.plan_location is None:
        return None
    else:
        return service.plan_location

def get_module_name_from_prefix(prefix):
    tuple_list = _ncs.get_nslist()
    for item in tuple_list:
        if prefix == item[1]:
            return item[4]

def config_cli_cleanup(filename, newfile):
    """
    Takes two filenames, and remove the private container

    Known Caveat: This will fail if somebody call a variable
                  private in a model
    """
    bad_words = [' private ']

    with open(filename) as oldfile, open(newfile, 'w') as new_file:
        for line in oldfile:
            if not any(bad_word in line for bad_word in bad_words):
                new_file.write(line)
        new_file.close()


def write_file(filename, text):
    """
    Write text to filename
    """
    with open(filename, "w") as fd:
        fd.write(text)


def read_file(filename):
    """
    Returns content of filename as a string
    """
    with open(filename, "r") as fd:
        return str(fd.read())


def append_to_file(filename, text):
    """
    append text to filename
    """
    with open(filename, "a+") as fd:
        fd.write(text)

def save_configuration(sock_maapi, th, conf_type, keypath, config_file,
                       logger, file_open_type):
    """
    Save configuration at keypath
    """
    # Disbling too many arguments pylint
    # pylint: disable=R0913
    save_id = maapi.save_config(sock_maapi, th, conf_type, keypath)
    with open(config_file, file_open_type) as file:
        try:
            ssocket = socket.socket()
            _ncs.stream_connect(sock=ssocket,
                                id=save_id,
                                flags=0,
                                ip='127.0.0.1',
                                port=ncs.NCS_PORT)

            while True:
                config_data = ssocket.recv(32768)
                file.write(config_data.decode('utf-8'))
                if not config_data:
                    break
        except Exception as e:
            logger.info(str(e))
            raise e
        finally:
            ssocket.close()
            file.close()

def get_lstatus_exec_rc_string_for_device(uinfo, device_name):
    """
    For a limited supported type of devices (NED) - read the
    device configuration by remote execution of a given command
    (e.g. any command)
    Currently supports:
      * Cisco IOS (cli NED)
      * Cisco IOS-XR (cli NED)
      * Cisco NX (cli NED)
      * Juniper (NETCONF NED)
    To extend this list, use the rpc request shell execute for netconf devices,
    live-status exec show for CLI based devices. If the device doesn't support
    neither of RPC call for showing the configuration nor live-status execution,
    contact Cisco support to extend the feature set of the NED.

    input: self, transaction, device_name
    returns the actual configuration of the device
    """
    with ncs.maapi.Maapi() as m, ncs.maapi.Session(
            m, uinfo.username, 'system'), m.start_read_trans() as t:
        root = ncs.maagic.get_root(t)
        device = root.devices.device[device_name]
        d_type = device.device_type

        if d_type.cli.ned_id is not None and "cisco-ios-" in d_type.cli.ned_id:
            return ["/live-status/tailf-ned-cisco-ios-stats:exec/show",
                    "<output xmlns='http://tail-f.com/ned/cisco-ios-stats'>",
                    "<show><args>running-config</args></show>"]
        if d_type.cli.ned_id is not None and "cisco-iosxr-" in d_type.cli.ned_id:
            return ["/live-status/tailf-ned-cisco-ios-xr-stats:exec/show",
                    "<output xmlns='http://tail-f.com/ned/cisco-ios-xr-stats'>",
                    "<show><args>running-config</args></show>"]
        if d_type.cli.ned_id is not None and "cisco-nx-" in d_type.cli.ned_id:
            return ["/live-status/tailf-ned-cisco-nx-stats:exec/show",
                    "<output xmlns='http://tail-f.com/ned/cisco-nx/stats'>",
                    "<show><args>running-config</args></show>"]
        if d_type.netconf.ned_id is not None and "juniper-junos-" in d_type.netconf.ned_id:
            return ["/rpc/rpc-request-shell-execute/",
                    "<output xmlns='http://tail-f.com/ned/juniper-junos/rpc'>",
                    "<input><args>cli show running-config</args></input>"]
        if d_type.netconf.ned_id is not None and "cisco-iosxr-nc-" in d_type.netconf.ned_id:
            return ["/rpc/rpc-get-config/get-config",
                    "<output xmlns='http://tail-f.com/ns/ned-id/cisco-iosxr-nc/rpc'>",
                    "<source><running/></source>"]
        return ["Device type is not currently supported"]

def get_config_from_device(trans, device_name):
    """
    For a limited supported type of devices (NED) - read the
    device configuration by remote execution of a given command
    (e.g. any command)
    Currently supports:
      * Cisco IOS (cli NED)
      * Cisco IOS-XR (cli NED)
      * Cisco NX (cli NED)
      * Juniper (NETCONF NED)
    To extend this list, use the rpc request shell execute for netconf devices,
    live-status exec show for CLI based devices. If the device doesn't support
    neither of RPC call for showing the configuration nor live-status execution,
    contact Cisco support to extend the feature set of the NED.

    input: self, transaction, device_name
    returns the actual configuration of the device
    """
    root = ncs.maagic.get_root(trans)
    device = root.devices.device[device_name]
    d_type = device.device_type

    try:
        if d_type.cli.ned_id is not None and "cisco-ios-" in d_type.cli.ned_id:
            command = "any"
            action_input = device.live_status.ios_stats__exec[command].get_input()
            action_input.args = "show running-config".split(' ')
            action_output = device.live_status.ios_stats__exec[command](
                action_input)
            return action_output.result
        if d_type.cli.ned_id is not None and "cisco-iosxr-" in d_type.cli.ned_id:
            command = "any"
            action_input = device.live_status.cisco_ios_xr_stats__exec[
                command].get_input()
            action_input.args = "show running-config".split(' ')
            action_output = device.live_status.cisco_ios_xr_stats__exec[command](
                action_input)
            return action_output.result
        if d_type.cli.ned_id is not None and "cisco-nx-" in d_type.cli.ned_id:
            command = "any"
            action_input = device.live_status.nx_stats__exec[command].get_input()
            action_input.args = "show running-config".split(' ')
            action_output = device.live_status.nx_stats__exec[command](
                action_input)
            return action_output.result
    except:
        # TODO: Return keyerror ['any'] specific messaging when NED is not
        # production grade and fails to do the live-status exec any command,
        # for now, no-networking keyword will be automated instead
        return "Device type is not currently supported"
    try:
        if d_type.netconf.ned_id is not None and "juniper-junos-" in d_type.netconf.ned_id:
            rpc_input = device.rpc.rpc_request_shell_execute.request_shell_execute.get_input()
            rpc_input.command = "cli show running-config"
            rpc_output = device.rpc.rpc_request_shell_execute.request_shell_execute(
                            rpc_input)
            return rpc_output.output
    except:
        return "Device type is not currently supported"
    # if d_type.netconf.ned_id is not None and "router-nc-1.0" in d_type.netconf.ned_id:
    #     rpc_input = device.rpc.rpc_request_shell_execute.request_shell_execute.get_input()
    #     rpc_input.command = "cli show configuration"
    #     rpc_output = device.rpc.rpc_request_shell_execute.request_shell_execute(
    #         rpc_input)
    #     return rpc_output.output
    # if d_type.cli.ned_id is not None and "alu-sr-" in d_type.cli.ned_id:
    #     command = "any"
    #     action_input = device.live_status.alu_sr_stats__exec[
    #          command].get_input()
    #     action_input.args = "FILL IN COMMAND HERE".split(' ')
    #     action_output = device.live_status.alu_sr_stats__exec[command](
    #          action_input)
    #     return action_output.result
    # if d_type.cli.ned_id is not None and "huawei-vrp-" in d_type.cli.ned_id:
    #     command = "any"
    #     action_input = device.live_status.vrp_stats__exec[command].get_input()
    #     action_input.args = "FILL IN COMMAND HERE".split(' ')
    #     action_output = device.live_status.vrp_stats__exec[command](
    #          action_input)
    #     return action_output.result
    # if d_type.cli.ned_id is not None and "redback-se-" in d_type.cli.ned_id:
    #     command = "any"
    #     action_input = device.live_status.redback_se_stats__exec[
    #          command].get_input()
    #     action_input.args = "FILL IN COMMAND HERE".split(' ')
    #     action_output = device.live_status.redback_se_stats__exec[command](
    #          action_input)
    #     return action_output.result

    return "Device type is not currently supported"


def config_exclude(content_list):
    """
    Exludes lines which should not be part of the diff from device config
    Example timestamp:
    Wed Aug 26 10:09:14.832 UTC
    and
    !! Last configuration change at Wed Aug 26 10:09:09 2020 by cisco

    input: self, content_list
    returns list without specific lines which need to be excluded from device config diff
    """
    return list(
        filter(
            lambda k: not re.search(
                r'\w\w\w\s\w\w\w\s[\s\d]\d\s\d\d:\d\d:\d\d', k) and not re.search(
                    r'Last\sconfiguration\schange\sat\s[\s\d]\d:\d\d:\d\d', k
                ) and not re.search(r'Current configuration : \d+ bytes', k),
            content_list))
