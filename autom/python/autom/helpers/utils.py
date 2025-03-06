'''
    AUTOM helpers utils Folders class
    This class is responsible for creating the output folder structure for the test results
'''
import os

class Trans():
    def __init__(self, t, thandle, sock, uinfo):
        self.t = t
        self.thandle = thandle
        self.sock = sock
        self.uinfo = uinfo

class Folders():
    def __init__(self, folder_path, keypath_node, kp_input, trans):
        self.folder_path = folder_path
        self.keypath_node = keypath_node
        self.kp_input = kp_input
        self.t = trans
        self.node_name = keypath_node._name
        self.output_folder = ""
        self.config_before_test_in_isolation_file_xml = ""
        self.cdb_diff_file_cli = ""
        self.config_before_file_clean_cli = ""
        self.config_after_file_clean_cli = ""
        self.cdb_diff_file_xml = ""
        self.devices_diff_file_xml = ""
        self.config_after_file_xml = ""
        self.config_before_file_xml = ""
        self.service_config_file_xml = ""
        self.test_folder = None

    def get_key_params(self):
        split_string = self.keypath_node._path.rsplit('{', 1)
        key_params = split_string[1].rstrip('}')
        return key_params.replace(' ', '_').replace('/', '%2f')

    def generate_xml_files(self):
        extension = 'xml'
        self.service_config_file_xml = os.path.join(self.output_folder,
                                               "service_config.%s" % extension)
        self.config_after_file_xml = os.path.join(self.output_folder,
                                             "cdb_after.%s" % extension)
        self.config_before_file_xml = os.path.join(self.output_folder,
                                              "cdb_before.%s" % extension)
        self.devices_diff_file_xml = []
        self.cdb_diff_file_xml = os.path.join(self.output_folder,
                                            "cdb_diff.%s" % extension)
        if len(self.kp_input)>1:
            iter =1
            for item in self.kp_input:
                self.devices_diff_file_xml.append(os.path.join(self.output_folder,
                                     "devices_diff%d.%s" % (iter, extension)))

                iter +=1
        else:
            self.devices_diff_file_xml.append(os.path.join(self.output_folder,
                                                 "devices_diff.%s" % extension))

    def generate_cli_files(self):
        extension = 'cli'
        self.config_after_file_clean_cli = os.path.join(self.output_folder,
                                                   "cdb_after.%s" % extension)
        self.config_before_file_clean_cli = os.path.join(
            self.output_folder, "cdb_before.%s" % extension)
        self.cdb_diff_file_cli = os.path.join(self.output_folder,
                                         "cdb_diff.%s" % extension)
        self.config_before_test_in_isolation_file_xml = os.path.join(
            self.output_folder, "cdb_before_test_in_isolation.xml")

    def create_folder_env(self, use_date_time, current_date_time):
        # Grabbing the key parameters for creating the output folder structure
        key_params = self.get_key_params()
        if use_date_time:
            self.output_folder = os.path.join(self.folder_path, self.node_name, "test", key_params, "execution_log", current_date_time)
        else:
            self.output_folder = os.path.join(self.folder_path, self.node_name, "test", key_params)
        self.test_folder = os.path.join(self.folder_path, self.node_name, "test")
        self.compare_folder = os.path.join(self.folder_path, self.node_name, "test", key_params)
        os.makedirs(self.output_folder, exist_ok=True)
        self.folder_path = self.output_folder
        
        #Generating the xml files
        self.generate_xml_files()

        #Generating the cli files
        self.generate_cli_files()
