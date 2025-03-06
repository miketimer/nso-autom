"""
AUTOM Main Entry Point
"""
# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
#from .actions.actiontesting_action import ActionTestingAction
from .actions.autom_create_action import AutomCreateAction
#rom .actions.getdeviceconfig_action import GetDeviceConfigAction
#from .actions.getinstancekeypaths_action import GetInstanceKeypathsAction
#from .actions.getmodifications_action import GetModificationsAction
from .actions.dry_run_execute_action import AutomDryRunExecute
from .actions.autom_execute_action import AutomExecuteAction
from .actions.load_merge_service_config_action import LoadMergeServiceConfig

# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    """
    NCS Application for AUTOM package
    """
    def setup(self):
        """
        The application class sets up logging for us. It is accessible through
        'self.log' and is a ncs.log.Log instance.

        :return: None
        """
        self.log.info('Main RUNNING')

        # Registering Actions
        self.register_action('autom-action-create', AutomCreateAction)
        self.register_action('autom-dry-run-execute', AutomDryRunExecute)
        self.register_action('autom-execute-action', AutomExecuteAction)
        self.register_action('load-merge-service-config', LoadMergeServiceConfig)
    def teardown(self):
        """
        When the application is finished (which would happen if NCS went down,
        packages were reloaded or some error occurred) this teardown method will be called.

        :return: None
        """
        self.log.info('Main FINISHED')

