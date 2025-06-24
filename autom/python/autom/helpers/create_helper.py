# -*- mode: python; python-indent: 4 -*-
"""
Autom create_helper
"""
from datetime import datetime
import difflib
import os
import operator
import re
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
from .tools import (config_cli_cleanup,
                             get_config_from_device, save_configuration,
                             write_file, read_file, config_exclude,
                             get_module_name_from_prefix,
                             strip_xpath_prefixes,
                             get_plan_location,
                             xpath_node,
                             xpath_kp,
                             append_to_file)

def dryrun_configuration(conf_type, cdb_config_file, diff_file_xml, uinfo):
    """
    Open a write transaction towards the CDB with uinfo file
    and execute a commit dry-run (outformat xml) of the configuration
    and write it to diff_file_xml (which is a filename)
    """
    trans, thandle, sock_maapi, root = _open_new_wr_trans(uinfo)

    try:
        trans.load_config(conf_type + maapi.CONFIG_MERGE,
                          cdb_config_file)
    except Exception as e:
        raise e
    #try:
    commit_params = ncs.maapi.CommitParams()
    commit_params.dry_run_xml()
    result = trans.apply_params(params=commit_params)

    #if result:
    write_file(
            diff_file_xml,
            """<config xmlns=\"http://tail-f.com/ns/config/1.0\">\n"""
        )

    xml_diff = result['local-node']
    append_to_file(diff_file_xml, xml_diff)
    append_to_file(diff_file_xml, """</config>""")
    #except Exception:
    #    result = None

def write_dry_run_data(folder_path, keypaths, test_in_isolation, pre_config_files, pre_config_devices):
    text =""
    for path in keypaths:
        text = text + path + ";"
    text = text + "\n" + folder_path + "/service_config.xml\n" + folder_path + "/cdb_diff.xml"
    test = text + "\n" + folder_path + "/devices_diff.xml"
    text = text + "\n" + "test_in_isolation: " + str(test_in_isolation)
    for item in pre_config_files:
        text = text + "\n" + folder_path + "/" + str(item) + ".xml"
    for item in pre_config_devices:
        text = text + "\n" + folder_path + "/" + str(item)+"_before.xml"
    write_file(folder_path + "/dry_run_data.txt", text)

def xpath_eval_list_function(x, y, self):
    _, str(x, y)
    self.state_array.append(x, y)

def plan_status_reached(self, uinfo, plan_location):
    with ncs.maapi.Maapi() as m:
        with ncs.maapi.Session(m, uinfo.username, "system"):
            with m.start_read_trans() as tr:
                plan_node = ncs.maagic.get_node(tr, plan_location._path + '/plan/component{ncs:self self}/state{ncs:ready}')
                if plan_node.status == 'reached':
                    return True
                else:
                    return False

def find_xpath_for_keypath(self, keypath, services_xpath):
    return services_xpath.get(str(keypath))

def wait_for_zombie(self, max_time_to_wait, sleep_time, root, trans, plan_location, xpath_node):
    time_spent = 0
    while time_spent < max_time_to_wait:
        time_spent +=1
        if zombie_exists(self, root, trans, plan_location, xpath_node):
            time.sleep(sleep_time)
            continue
        else:
            break
    self.log.info("Time spent waiting for zombie:", time_spent)

def nano_service_ready(self, uinfo, trans, plan_location, sock_maapi, max_time_to_wait, sleep_time):
    """
    For finding out if the nano-service is ready
    Returns True if plan has status reached, False if it is not reached within the max_time_to_wait
    period
    """
    plan_location_node = ncs.maagic.get_node(trans, plan_location)
    plan_reached = plan_status_reached(self, uinfo, plan_location_node)
    retries = max_time_to_wait / sleep_time
    iterations = 1
    while plan_reached is False:
        iterations += 1
        self.log.info("Inside loop of plan_reached, waiting for 0.2s if plan_reached is ", plan_reached)
        time.sleep(sleep_time)
        plan_reached = plan_status_reached(self, uinfo, plan_location_node)
        if plan_reached:
            return True
        if iterations == retries:
            return False
    return False

def recursive_xml(xml_root):
    """
    For removing specific xml elements (private and diff-set)
    Private and diff-set data is encoded data NSO stores for itself
    If you try to load merge config with this data, it will be rejected!

    input self, ElementTree element/root
    """

    if not ET.iselement(xml_root):
        xml_root = xml_root.getroot()
    if len(list(xml_root)) > 0:
        for child in xml_root:
            if "}private" in child.tag or "}diff-set" in child.tag:
                xml_root.remove(child)
            else:
                recursive_xml(child)
        for child in xml_root:
            i = child.tag.find('}')
            if i >= 0:
                child.tag = child.tag[i + 1:]
        i = xml_root.tag.find('}')
        if i >= 0:
            xml_root.tag = xml_root.tag[i + 1:]

def cleanup_xml(xml_file):
    """
    For parsing, manipulation and writing XML based NSO config-data
    Pre-requisite for the removal of private and diff-set elements

    input xmlfile
    """
    xml_root = parse_xmlns(xml_file)
    recursive_xml(xml_root)
    # Write back to file
    # self.fixup_xmlns(xml_root, maps=None)
    write_xmlns(xml_root, xml_file)

def get_services_check_sync_result(self, root):
    """
    Get services check-sync result returns a list of services with
    check sync-result (in_sync boolean) and the path of each (service_id)
    """
    check_sync_input = root.services.check_sync.get_input()
    services_list = root.services.check_sync.request(check_sync_input)

    return services_list

def get_children(self, sock_maapi, trans, path):
    """
    Get children returns a list of child services to a given path (if found)
    otherwise the list [] returned will be empty
    """
    kp_node = ncs.maagic.get_node(trans, maapi.xpath2kpath(sock_maapi,
                            path))
    child_services = []
    if len(kp_node.private.service_list) > 0:
        for service_id in kp_node.private.service_list:
            child_services.append(str(service_id))
    return child_services

def has_children(self, sock_maapi, trans, path):
    """
    Has children returns a boolean True if child services exist to a given
    path (if found) otherwise the False is returned
    """
    kp_node = ncs.maagic.get_node(trans, maapi.xpath2kpath(sock_maapi,
                            path))
    if len(kp_node.private.service_list) > 0:
        return True
    else:
        return False

def get_parent(self, sock_maapi, trans, path, top_level_services, parent_services):
    """
    Get Parent returns the boolean True for a top level service, False if
    a normal parent (mid layer service) together with the parent keypath
    """
    for keypath in parent_services:
        kp_node = ncs.maagic.get_node(trans, keypath)

        for kpath in kp_node.private.service_list:
            path_node = ncs.maagic.get_node(trans, path)
            kpath_node = ncs.maagic.get_node(trans, kpath)

            if kpath_node._path == path_node._path:
                return True, kp_node._path

    for keypath in top_level_services:
        kp_node = ncs.maagic.get_node(trans, keypath)

        for kpath in kp_node.private.service_list:
            path_node = ncs.maagic.get_node(trans, path)
            kpath_node = ncs.maagic.get_node(trans, kpath)

            if kpath_node._path == path_node._path:
                return True, kp_node._path
    return False, None

def get_top_level_parent(self, sock_maapi, trans, path, top_level_services, parent_services):
    """
    Get top level parent calls itself recursively until it finds a top
    level service and not a mid layer parent keypath.
    Returns the keypath only if the parent is a top-level service, otherwise
    None is returned.
    """
    is_top_level, keypath = self.get_parent(sock_maapi,
                                            trans,
                                            path,
                                            top_level_services,
                                            parent_services)
    if is_top_level:
        return keypath
    elif keypath is not None:
        self.get_top_level_parent(sock_maapi, trans, keypath, top_level_services, parent_services)
    else:
        return None

def get_specific_check_sync_result(self, trans, service_instances):
    """
    Retrieve the services from the service instance list filtering out
    check-sync results of False
    """
    services_list = {}
    for item in service_instances:
        kp_node = ncs.maagic.get_node(trans, item)
        check_sync_input = kp_node.check_sync.get_input()
        check_sync_result = kp_node.check_sync(check_sync_input)
        self.log.info("Check-sync of kp_node path: %s" %kp_node._path)
        self.log.info("Result: %s" % str(check_sync_result.in_sync))
        xpath_str = ''
        if 'True' in str(check_sync_result.in_sync):
            xpath_str = xpath(kp_node)
            pair = {kp_node._path:xpath_str}
            services_list.update(pair)
            self.log.info("Appended %s" %pair)
    return services_list

def get_service_keypaths(self, uinfo,
                         services_list, ignore_xpaths):
    """
    Retrieve the service_keypaths based on the service_type input

    Returns the "parent/child/normal/top" services
    if service_point_list used, returns only the kp for the chosen
    service_points

    The output ignores /nso-arc kp
    ignores /service-scheduler:service-scheduler-kickers
    ignores out-of-sync services
    """
    child_services = []
    services_xpath = {}
    parent_services = []
    regular_services = []
    trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
    skip = False
    for item in services_list.sync_result:
        self.log.info("xpath: ", item.service_id)
        if len(ignore_xpaths)>0:
            for keypath_to_ignore in ignore_xpaths:
                if keypath_to_ignore in item.service_id:
                    self.log.info("Removing keypath %s from results" % item.service_id)
                    skip = True
        if skip:
            continue
        kpath = maapi.xpath2kpath(trans.maapi.msock, item.service_id)
        kp_node = ncs.maagic.get_node(trans, kpath)
        path = str(kp_node._path)
        skip = False

        if 'False' in str(item.in_sync):
            # check if boolean returned can be used
            self.log.info(
                "Removing in-sync false service %s from results" %
                str(item.service_id))
            continue

        if len(kp_node.private.service_list) > 0:
            if len(ignore_xpaths)>0:
                for keypath_to_ignore in ignore_xpaths:
                    if keypath_to_ignore in item.service_id:
                        self.log.info("Removing keypath %s from results" % item.service_id)
                        skip = True
            if skip:
                continue
            else:
                for service_id in kp_node.private.service_list:
                    child_services.append(str(service_id))
                parent_services.append(path)
                pair = {path:item.service_id}
                services_xpath.update(pair)
        else:
            if len(ignore_xpaths)>0:
                for keypath_to_ignore in ignore_xpaths:
                    if keypath_to_ignore in item.service_id:
                        self.log.info("Removing keypath %s from results" % item.service_id)
                        skip = True
                if skip:
                    continue
                else:
                    regular_services.append(path)
                    pair = {path:item.service_id}
                    services_xpath.update(pair)
    # Invoking set of child services, in case of multiple entries (shared
    # child services are used)
    unique_child_services = set(child_services)
    # Removing children to parent services from the list of regular services
    regular_services = [item for item in regular_services if item not in list(unique_child_services)]
    # Removing middle layer services in parent_services to create top_level_services
    top_level_services = [item for item in parent_services if item not in list(unique_child_services)]
    parent_services = [item for item in top_level_services if item not in parent_services]

    self.log.info("Regular_services: %s" % regular_services)
    self.log.info("Parent_services: %s" % parent_services)
    self.log.info("Child_services: %s" % list(unique_child_services))
    self.log.info("Top_level_services: %s" % top_level_services)

    return list(unique_child_services), parent_services, regular_services, top_level_services, services_xpath

def cdb_config_capture(self, sock_maapi, thandle, output_folder, phase,
                       config_types, kp_list, index):
    """
    Captures configuration of CDB and writes to file
    """
    if 'pre_config_xpath_xml' in config_types:
        for kp in kp_list:
            extension = 'xml'
            pre_config_file_xml = os.path.join(
                output_folder, "pre_config%d.%s" % (index, extension))
            save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY,
                               kp, pre_config_file_xml, self.log, "w")
            cleanup_xml(pre_config_file_xml)
            cleanup_xml(pre_config_file_xml)
            xml = read_file(pre_config_file_xml)
            xml = re.sub('xmlns:ns0=.+[ ]','',xml)
            write_file(pre_config_file_xml, xml)
    if 'service_config_xml' in config_types:
        iter = 1
        extension = 'xml'
        service_config_file_xml = os.path.join(
                        output_folder, "service_config.%s" % (extension))
        for kp in kp_list:
            if iter == 1:
                save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY,
                               kp, service_config_file_xml, self.log, "w")
                self.log.info(f'Iter {iter} ============================= Writing file {service_config_file_xml}')
            else:
                save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY,
                               kp, service_config_file_xml, self.log, "a")
                self.log.info(f'Iter {iter} ============================= Appending file {service_config_file_xml}')
            iter +=1
        if iter > 1:
            service_config = read_file(service_config_file_xml)
            service_config = re.sub('<\/config><config.*>\n', '', service_config)
            write_file(service_config_file_xml, service_config)
        cleanup_xml(service_config_file_xml)
        cleanup_xml(service_config_file_xml)


    if 'service_config_after_xml' in config_types:
        for kp in kp_list:
            extension = 'xml'
            service_config_file_xml = os.path.join(
                output_folder, "service_config_after.%s" % (extension))
            save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY,
                               kp, service_config_file_xml, self.log, "w")
            cleanup_xml(service_config_file_xml)
            cleanup_xml(service_config_file_xml)

    if 'xml' in config_types:
        for kp in kp_list:
            extension = 'xml'
            config_file_xml = os.path.join(output_folder,
                                       "cdb_%s.%s" % (phase, extension))
            save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY + maapi.CONFIG_WITH_SERVICE_META,
                           '/', config_file_xml, self.log, "w")
            cleanup_xml(config_file_xml)

    if 'cli' in config_types:
        for kp in kp_list:
            extension = 'cli'
            config_file_cli = os.path.join(
                output_folder, "cdb_%s_temp.%s" % (phase, extension))
            config_file_clean_cli = os.path.join(
                output_folder, "cdb_%s.%s" % (phase, extension))
            save_configuration(sock_maapi, thandle, maapi.CONFIG_C_IOS + maapi.CONFIG_WITH_SERVICE_META, '/',
                               config_file_cli, self.log, "w")
            config_cli_cleanup(config_file_cli, config_file_clean_cli)
            os.remove(config_file_cli)

def device_config_capture(self, sock_maapi, trans, thandle, device,
                          output_folder, phase, no_networking):
    """
    Captures configuration of a list of devices and writes to file
    """
    dev_config_file_cli = os.path.join(output_folder,
                                       "%s_%s.cli" % (device, phase))
    dev_config_file_xml = os.path.join(output_folder,
                                       "%s_%s.xml" % (device, phase))

    root = ncs.maagic.get_root(trans)
    device_config_node = root.ncs__devices.ncs__device[device].ncs__config
    save_configuration(sock_maapi, thandle, maapi.CONFIG_XML_PRETTY+maapi.CONFIG_WITH_SERVICE_META,
                       device_config_node._path, dev_config_file_xml,
                       self.log, "w")
    if no_networking:
        save_configuration(sock_maapi, thandle, maapi.CONFIG_C_IOS+maapi.CONFIG_WITH_SERVICE_META,
                           device_config_node._path,
                           dev_config_file_cli, self.log, "w")
    else:
        # not no_networking:
        device_output = get_config_from_device(trans, device)
        device_output = device_output.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')
        write_file(dev_config_file_cli, device_output)

    return dev_config_file_cli

def device_diff_write(device, output_folder, device_config_before_file,
                      device_config_after_file):
    """
    Writes devices_diff to file
    """
    dev_diff_file = os.path.join(output_folder, "%s_diff.cli" % (device))
    device_config_before = read_file(device_config_before_file)
    device_config_after = read_file(device_config_after_file)
    dev_diff = difflib.unified_diff(
        config_exclude(device_config_before.splitlines(keepends=True)),
        config_exclude(device_config_after.splitlines(keepends=True)))
    write_file(dev_diff_file, ''.join(dev_diff))

def capture_modifications(trans, username, keypath_nodes, flag,
                                 devices_diff_file_xml, write_to_file):
    """
    Captures device modifications based on service keypath
    Sets services global-settings collect-forward-diff to true if not
        already set!
    Writes to file (if boolean write_to_file is set to True)
    Returns output
    """
    # Capturing device-modifications
    iter = 0
    for kp_node in keypath_nodes:
        keypath_node = ncs.maagic.get_node(trans, kp_node)
        diff_input = keypath_node.get_modifications.get_input()
        diff_input.outformat = 'xml'
        if flag is None:
            diff_input.outformat = 'xml'
        elif flag == "deep":
            diff_input.deep.create()
        elif flag == "shallow":
            diff_input.shallow.create()
        try:
            diff_output = keypath_node.get_modifications(diff_input)
            if write_to_file:
                write_file(devices_diff_file_xml[iter],
                        '<data>' + diff_output.result_xml.local_node.data + '</data>')
                iter +=1
            else:
                return '<data>' + diff_output.result_xml.local_node.data + '</data>'

        except Exception:
            with ncs.maapi.Maapi() as m, ncs.maapi.Session(
                    m, username, 'system'), m.start_write_trans() as wr_trans:
                root = ncs.maagic.get_root(wr_trans)
                root.ncs__services.global_settings.collect_forward_diff = True
                wr_trans.apply()
                redeploy_input = keypath_node.re_deploy.get_input()
                keypath_node.re_deploy(redeploy_input)
                diff_output = keypath_node.get_modifications(diff_input)
                if write_to_file:
                    write_file(devices_diff_file_xml[iter],
                        '<data>' + diff_output.result_xml.local_node.data + '</data>')
                    iter +=1
                else:
                    return '<data>' + diff_output.result_xml.local_node.data + '</data>'

def get_pre_config_files(self, trans, thandle, sock_maapi, pre_config_xpaths, files):
    pre_config_files = {}
    for idx, xpath in enumerate(pre_config_xpaths,start=1):
        kp_pre_config = ncs.maagic.get_node(trans, maapi.xpath2kpath(
                                        sock_maapi,
                                        xpath))
        cdb_config_capture(self, sock_maapi,
                                thandle,
                                files.output_folder,
                                phase='',
                                config_types=['pre_config_xpath_xml'],
                                kp_list=[kp_pre_config._path],
                                index=idx)
        pre_config_files['pre_config' + str(idx)] = [os.path.join(files.output_folder,
                                        "pre_config%d.xml" % (idx))]
    return pre_config_files

def abspath(path):
    """Return an absolute path."""
    if not isabs(path):
        if isinstance(path, _unicode):
            cwd = os.getcwdu()
        else:
            cwd = os.getcwd()
        path = join(cwd, path)
    return normpath(path)

def zombie_exists(self, t, root, path_node, str_xpath):
    self.log.info("Zombie path_node:", path_node._path)
    node = ncs.maagic.get_node(t, path_node._path)
    zombie = f'/zombies/service[service-path="{strip_xpath_prefixes(xpath(node))}"]'
    self.log.info("Inside loop looking for the zombie at ", zombie)
    if xpath_kp(self.log, root, zombie) is not None:
        self.log.info("Zombie found!")
        return True
    else:
        return False

def xpath_eval_list_function(x, y, self):
    _, str(x, y)
    self.state_array.append(x, y)

def find_xpath_for_keypath(self, keypath, services_xpath):
    return services_xpath.get(str(keypath))

def _open_new_wr_trans(uinfo):

    m = ncs.maapi.Maapi()
    ncs.maapi.Session(m, uinfo.username, 'system')
    trans = m.start_write_trans()
    root = ncs.maagic.get_root(trans)

    return trans, trans.th, trans.maapi.msock, root


def _open_new_trans(uinfo):

    m = ncs.maapi.Maapi()
    ncs.maapi.Session(m, uinfo.username, 'system')
    trans = m.start_read_trans()
    root = ncs.maagic.get_root(trans)

    return trans, trans.th, trans.maapi.msock, root

def _close_trans(trans):
    trans.finish()

def delete_kpath_from_cdb(sock_maapi, kp_node, no_networking, uinfo):
    thandle_rw = maapi.start_trans2(sock_maapi, _ncs.RUNNING,
                                        _ncs.READ_WRITE, uinfo.usid)
    maapi.delete(sock_maapi, thandle_rw, kp_node._path)

    if no_networking:
        maapi.apply_trans_flags(
            sock_maapi,
            thandle_rw,
            False,
            flags=_ncs.maapi.COMMIT_NCS_NO_NETWORKING)
    else:
        # not no_networking:
        maapi.apply_trans(sock_maapi, thandle_rw, keepopen=False)
def load_service_config_from_file(sock_maapi, load_file, no_networking, uinfo):
    try:
        thandle_rw = maapi.start_trans2(sock_maapi, _ncs.RUNNING,
                                           _ncs.READ_WRITE, uinfo.usid)
        maapi.load_config_cmds(
            sock_maapi, thandle_rw,
            maapi.CONFIG_XML_PRETTY + maapi.CONFIG_MERGE,
            load_file, '/')
        if no_networking:
            maapi.apply_trans_flags(
                sock_maapi,
                thandle_rw,
                keepopen=False,
                flags=_ncs.maapi.COMMIT_NCS_NO_NETWORKING)
        else:
            # not no_networking
            maapi.apply_trans(sock_maapi, thandle_rw, False)
    except Exception as e:
        raise e
def load_cdb_config_from_file(sock_maapi, load_file, no_networking, uinfo):
    try:
        thandle_rw = maapi.start_trans2(sock_maapi, _ncs.RUNNING,
                                           _ncs.READ_WRITE, uinfo.usid)
        maapi.load_config(sock_maapi, thandle_rw,
                          maapi.CONFIG_XML_PRETTY + maapi.CONFIG_WITH_SERVICE_META + maapi.CONFIG_MERGE,
                          load_file)
        if no_networking:
            maapi.apply_trans_flags(
                sock_maapi,
                thandle_rw,
                keepopen=False,
                flags=_ncs.maapi.COMMIT_NCS_NO_NETWORKING)
        else:
            maapi.apply_trans(sock_maapi, thandle_rw, False)

    except Exception as e:
        raise e
def redeploy_reconcile_no_networking(keypath_node):
    redeploy_input = keypath_node.re_deploy.get_input()
    redeploy_input.reconcile.create()
    redeploy_input.no_networking.create()
    keypath_node.re_deploy(redeploy_input)

def redeploy_reconcile(keypath_node):
    redeploy_input = keypath_node.re_deploy.get_input()
    redeploy_input.reconcile.create()
    keypath_node.re_deploy(redeploy_input)

def compare_config_devices_affected(trans, kp_input, root):
    devices_list = []
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        devices_path_mod = kp_node._path + "/modified/devices"
        devices_list += ncs.maagic.get_node(
                                    trans, devices_path_mod).as_list()

    for device_name in devices_list:
        root.ncs__devices.ncs__device[
            device_name].compare_config()
    return devices_list

def service_has_plan(self, kpath, xpath, uinfo):
    trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
    self.log.info("Kpath = ", kpath)
    kp_node = ncs.maagic.get_node(trans, kpath)
    #kp_node_oper_data = ncs.maagic.cd(root, kpath)
    plan_location = get_plan_location(self.log, root, kp_node, xpath)
    if plan_location is not None:
        plan_location_node = ncs.maagic.get_node(trans, maapi.xpath2kpath(
                                        sock_maapi,
                                        plan_location))
        self.log.info("Plan Location Node: ", plan_location_node._path)
        _close_trans(trans)
        return (True, plan_location_node)
    else:
        _close_trans(trans)
        return (False, None)

def recursive_xml(xml_root):
    """
    For removing specific xml elements (private and diff-set)
    Private and diff-set data is encoded data NSO stores for itself
    If you try to load merge config with this data, it will be rejected!

    input self, ElementTree element/root
    """

    if not ET.iselement(xml_root):
        xml_root = xml_root.getroot()

    if len(list(xml_root)) > 0:
        for child in xml_root:
            if "}private" in child.tag or "}diff-set" in child.tag:
                xml_root.remove(child)
            else:
                recursive_xml(child)
        for child in xml_root:
            i = child.tag.find('}')
            if i >= 0:
                child.tag = child.tag[i + 1:]
        i = xml_root.tag.find('}')
        if i >= 0:
            xml_root.tag = xml_root.tag[i + 1:]


def get_children(self, sock_maapi, trans, path):
    """
    Get children returns a list of child services to a given path (if found)
    otherwise the list [] returned will be empty
    """
    kp_node = ncs.maagic.get_node(trans, maapi.xpath2kpath(sock_maapi,
                            path))
    child_services = []
    if len(kp_node.private.service_list) > 0:
        for service_id in kp_node.private.service_list:
            child_services.append(str(service_id))
    return child_services

def has_children(self, sock_maapi, trans, path):
    """
    Has children returns a boolean True if child services exist to a given
    path (if found) otherwise the False is returned
    """
    kp_node = ncs.maagic.get_node(trans, maapi.xpath2kpath(sock_maapi,
                            path))
    if len(kp_node.private.service_list) > 0:
        return True
    else:
        return False

def get_parent(self, uinfo, trans, path, services_list):
    """
    Get Parent returns the boolean True for a top level service, False if
    a normal parent (mid layer service) together with the parent keypath
    """
    child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                            uinfo,
                            services_list,
                            [])
    for keypath in parent_services:
        kp_node = ncs.maagic.get_node(trans, keypath)

        for kpath in kp_node.private.service_list:
            path_node = ncs.maagic.get_node(trans, path)
            kpath_node = ncs.maagic.get_node(trans, kpath)

            if kpath_node._path == path_node._path:
                return True, kp_node._path

    for keypath in top_level_services:
        kp_node = ncs.maagic.get_node(trans, keypath)

        for kpath in kp_node.private.service_list:
            path_node = ncs.maagic.get_node(trans, path)
            kpath_node = ncs.maagic.get_node(trans, kpath)

            if kpath_node._path == path_node._path:
                return True, kp_node._path
    return False, None
def get_top_level_parent(self, uinfo, trans, path, services_list):
    """
    Get top level parent calls itself recursively until it finds a top
    level service and not a mid layer parent keypath.
    Returns the keypath only if the parent is a top-level service, otherwise
    None is returned.
    """
    is_top_level, keypath = get_parent(self, uinfo,
                                            trans,
                                            path,
                                            services_list)
    if is_top_level:
        return keypath
    else:
        return None

def is_parent(self, uinfo, trans, path, services_list):
    """
    Is parent returns a boolean True if the path is found in the
    parent_services list, otherwise False is returned
    """
    child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                            uinfo,
                            services_list,
                            [])
    if path in parent_services:
        return True
    else:
        return False

def is_top_level_parent(self, uinfo, trans, path, services_list):
    """
    Is top level parent returns a boolean True if the path is found in the
    top_level_services list, otherwise False is returned
    """
    child_services, parent_services, regular_services, top_level_services, services_xpath = get_service_keypaths(self,
                            uinfo,
                            services_list,
                            [])
    if path in top_level_services:
        return True
    else:
        return False

def device_diff_write(device, output_folder, device_config_before_file,
                      device_config_after_file):
    """
    Writes devices_diff to file
    """
    dev_diff_file = os.path.join(output_folder, "%s_diff.cli" % (device))
    device_config_before = read_file(device_config_before_file)
    device_config_after = read_file(device_config_after_file)
    dev_diff = difflib.unified_diff(
        config_exclude(device_config_before.splitlines(keepends=True)),
        config_exclude(device_config_after.splitlines(keepends=True)))
    write_file(dev_diff_file, ''.join(dev_diff))
