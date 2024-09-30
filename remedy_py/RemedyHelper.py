# /usr/local/lib/python3.9/site-packages/remedy_py/RemedyHelper.py
"""This module extends the RemedyClient class to provide additional functionality for working with Remedy forms.

The RemedyHelper class provides functions for creating, getting, and setting workorders, tasks, people, and incidents in Remedy.
To use the RemedyHelper class, import the RemedyHelper class from the RemedyHelper module.
Initialize the RemedyHelper class with the Remedy hostname, username, and password, the same way you would with the RemedyClient class.
"""

import requests
from accounts.models import Group                                      # type: ignore
from costs.utils import default_compute_rate                           # type: ignore
from infrastructure.models import Server, Disk, Environment            # type: ignore
from orders.models import BlueprintOrderItem,ServerModOrderItem, Order # type: ignore
from portals.models import PortalConfig                                # type: ignore
from remedy_py.RemedyAPIClient import RemedyClient
from remedy_py.RemedyConstants import DEFAULT_TIMEOUT, REQUEST_PREFIX
from resources.models import ResourceType, Resource                    # type: ignore
from servicecatalog.models import ServiceBlueprint                     # type: ignore
from utilities.models import ConnectionInfo                            # type: ignore
from utilities.logger import ThreadLogger                              # type: ignore
# For the file attachment
from os import sep, SEEK_END
from os.path import getsize
import json

logger = ThreadLogger('RemedyHelper')

portal = PortalConfig.objects.last()
CLOUDBOLTORDERURL    = f"https://{portal.domain}/orders"

#TODO - Move these to the CloudBolt settings
REMEDY_API           = ConnectionInfo.objects.get(name='Remedy RestAPI')
REMEDY_COMPANY       = 'University of Kansas Hospital'
REMEDY_SUPPORT_GROUP = "Servers and Storage"
REMEDY_SUPPORT_ORG   = "HITS - IT Infrastructure"
REMEDY_DOMAINNAME    = "ukha-smartit.onbmc.com"
FUNDING_APPROVER_ID  = "byoung"
TEMPLATE_LIST = {
    "Build_Server": "IDGAA5V0F2IWUAPH3YCVPG73D772NR",
    "Modify_Server": "IDGAA5V0F2BJ9APPV3A8POYHQ1BJB4",
}

class RemedyHelper(RemedyClient):
    """
    This class extends the RemedyClient class to provide additional functionality for working with Remedy forms.
    """

    def __init__(self, host, username, password, port=None, verify=True, proxies={}):
        """
        Initialize the RemedyHelper class
        :param host: The Remedy hostname
        :param username: The Remedy username
        :param password: The Remedy password
        """
        super().__init__(host, username, password, port, verify, proxies, timeout=DEFAULT_TIMEOUT, prefix=REQUEST_PREFIX)
        self.support_company = REMEDY_COMPANY

    class FakeServer:
        def __init__(self):
            self.hostname = 'None'
            self.quantity = 0
            self.os_build = "None"
            self.cpu_cnt = 0
            self.mem_size = 0
            self.disk_size = 0
            self.ukhs_cost_center = 'N/A'
            self.ukhs_funding_source = 'N/A'
            self.ukhs_serverorder_notes = 'N/A'
            self.ukhs_patch_group = 'N/A'
            self.ukhs_impact = 'N/A'
            self.ukhs_urgency = 'N/A'
            self.ukhs_dr_tier = 'N/A'


    def submit_workorder(self, values):
        """Submit a values formatted as a Workorder to Remedy.

        This function submits a values dictionary to the Remedy Workorder API, and returns the Workorer JSON.

        :param values: A dictionary of values to set on the workorder. Use the function get_workorder_form_fields() to get the field names.
        :type values: dict
        :return: The workorder values
        :type: dict
        """

        form = "WOI:WorkOrderInterface_Create"
        try:
            workorder = self.create_form_entry(form_name=form, values=values, return_values=['WorkOrder_ID'])
            logger.debug(f"Workorder created: {workorder[0]['values']['WorkOrder_ID']}")
        except Exception as e:
            return f"Error creating workorder: {e}"

        return workorder[0]['values']


    def create_workorder(self, order, description=None, template_id=TEMPLATE_LIST["Build_Server"]):
        """Transform a CMP Order into content for Remedy Workorder, then submit it.

        This function contains logic to create a Workorder in Remedy based on the order type.
        Supported order types are: BlueprintOrderItem, ServerModOrderItem.

        :param order: The order item to create the workorder for
        :type order: OrderItem
        :return: The Workorder values
        :type: dict
        """

        if isinstance(order.orderitem_set.first().cast(), BlueprintOrderItem):
            values = self.create_build_workorder(order, description, template_id)
        elif isinstance(order.orderitem_set.first().cast(), ServerModOrderItem):
            values = self.create_modification_workorder(order, description, template_id)
        else:
            return "Error: Order item is not a valid type"

        return self.submit_workorder(values)


    def get_workorder(self,workorder_id):
        form = "WOI:WorkOrderInterface"
        query = f"?q='Work Order ID'=\"{workorder_id}\""
        try:
            workorder = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting workorder: {e}"
        return workorder[0]['entries'][0]


    def get_workorder_tasks(self,workorder_id):
        # Invoke the RemedyAPI.get_form_entry function
        form  = "TMS:Task"
        query = f"?q='RootRequestID'=\"{workorder_id}\""
        try:
            tasks = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting workorder tasks: {e}"
        return tasks[0]['entries']


    def set_workorder_task(self,task_id,values):
        # Invoke the RemedyAPI.set_form_entry function
        form = "TMS:Task"
        try:
            task = self.update_form_entry(form_name=form,req_id=task_id,values=values)
        except Exception as e:
            return f"Error setting workorder task: {e}"
        return task[0]['values']


    def get_person_by_username(self,username):
        # Invoke the RemedyAPI.get_form_entry function
        form = "CTM:People"
        query = f"?q='Remedy Login ID'=\"{username}\""
        try:
            person = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting person: {e}"
        return person[0]['entries'][0]


    def get_incident(self,incident_id):
        # Invoke the RemedyAPI.get_form_entry function
        form = "HPD:Help Desk"
        query = f"?q='Incident ID'=\"{incident_id}\""
        try:
            incident = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting incident: {e}"
        return incident[0]['entries'][0]


    def get_incident_notes(self,incident_id):
        # Invoke the RemedyAPI.get_form_entry function
        form = "HPD:Help Desk"
        query = f"?q='Incident ID'=\"{incident_id}\""
        try:
            notes = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting incident notes: {e}"
        return notes[0]['entries']


    def create_workorder_note(self,workorder_id,note):
        # Invoke the RemedyAPI.create_form_entry function
        form = "WOI:WorkInfo"
        values = {
            'Work Order ID': workorder_id,
            'Detailed Description': note,
            'Work Log Submitter': self.username,
            'Work Log Type': 'General Information',
            'Work Log Date': self.get_current_date(),
            'View Access': 'Internal', # or Public
            'Secure Work Log': 'Yes',
        }
        try:
            result = self.create_form_entry(form_name=form,values=values)
        except Exception as e:
            return f"Error creating workorder note: {e}"
        return result


    def create_build_workorder(self, order, description=None, template_id=TEMPLATE_LIST["Build_Server"]):
        """Create a build workorder in Remedy

        :param order: The order item to create the workorder for
        :type orders.model.Order: OrderItem
        :return: The workorder values
        :type: dict
        """

        order_item = order.orderitem_set.first()
        if not isinstance(order_item.cast(), BlueprintOrderItem):
            return "Error: Order item is not a BlueprintOrderItem"

        # Template ID
        if TEMPLATE_LIST.get(template_id):
            template_id = TEMPLATE_LIST[template_id]
        elif not template_id.startswith("IDGAA"):
            return "Error: Invalid template ID"

        owner = order.owner.user
        try:
            server      = order_item.server
            hostname    = server.hostname
            environment = server.environment
            os_build    = server.os_build.name
            capacity    = self.get_environment_capacity(environment)
        except AttributeError:
            server      = self.FakeServer()
            hostname    = order.name
            environment = ''
            os_build    = ''
            capacity    = ''

        try:
            quotedcost = order_item.get_rate_display()
            hwcost     = self.get_server_rate_hardware_breakdown(order)
        except AttributeError:
            quotedcost = ''
            hwcost     = ''

        recipient = f"{order.recipient.full_name} ({order.recipient.user.email})" if order.recipient else ''

        if not description:
            # Build the description if it wasn't passed in
            description = f'''
    Once this workorder is "In Progress" and the funding process has been marked "Success", CloudBolt will proceed with the server build.
    -OR-
    View, Edit, Approve or Deny the order here:
    {CLOUDBOLTORDERURL}/{order.id}

    Server Name:\t {server.hostname}
    Quantity:\t {server.quantity}
    Requestor:\t {owner.username}
    On Behalf of:\t {recipient}
    Group:\t {order.group.parent.name} \ {order.group.name}
    Quoted Total Cost:\t {quotedcost}
    Project #:\t {server.ukhs_cost_center}
    Funding Source:\t {server.ukhs_funding_source}

    --HARDWARE--
    Share of Blade Cost:\t ${638.46 * server.quantity}
    OS:\t\t\t {os_build}
    CPU Cores:\t {server.cpu_cnt} (${float(hwcost['CPUs'])})
    Memory GB:\t {str(server.mem_size)} (${float(hwcost['Mem Size'])})
    Disk 1 GB:\t {server.disk_size} (${float(hwcost['Disk Size'])} (all disks included))
    '''

            # disk size attributes exist even if the value is None
            if server.disk_1_size:
                description += f'  Disk 2 GB:\t {server.disk_1_size}\n'
            if server.disk_2_size:
                description += f'  Disk 3 GB:\t {server.disk_2_size}\n'
            if server.disk_3_size:
                description += f'  Disk 4 GB:\t {server.disk_3_size}\n'

            description += f'  NIC 1 VLAN:\t {server.sc_nic_0.name}\n'
            if hasattr(server.sc_nic_1,"name"):
                description += f'  NIC 2 VLAN:\t {server.sc_nic_1.name}\n'
            if hasattr(server.sc_nic_2,"name"):
                description += f'  NIC 3 VLAN:\t {server.sc_nic_2.name}\n'

            description += f'''
        Environment:\t {environment.name} / {environment.vmware_cluster}
        Datastore:\t {environment.vmware_datastore.name}
        Environment Available Capacity:
        \tCPU:\t\t {capacity['cpu_available']}
        \tMemory GB:\t {capacity['mem_available']}
        \tDisk GB:\t\t {capacity['disk_available']}
        \tVM Count:\t {capacity['vm_count']}

        --ATTRIBUTES--
        Tech Doc URL:\t {server.ukhs_technicaldoc_url}
        Application:\t {server.ukhs_application_name}
        App Vendor:\t {server.ukhs_app_vendor}
        Environment:\t {server.ukhs_environment}
        Contact(s):\t {'; '.join(server.ukhs_server_contact)}
        Description:\t {server.ukhs_server_description}
        Patch Group:\t {server.ukhs_patch_group}
        AD OU:\t {server.ukhs_organizational_unit}
        FDA 5010K:\t {server.ukhs_fda510k}
        '''

        values = {
            'Summary': f"SRV - Build - CMP Order {order.id} - {hostname}",
            'Detailed Description': description,
            "Customer First Name":  owner.first_name,
            "Customer Last Name":   owner.last_name,
            "RequesterLoginID":     owner.username,
            "First Name":           owner.first_name,
            "Last Name":            owner.last_name,
            "Support Group Name":   REMEDY_SUPPORT_GROUP,
            "Support Organization": REMEDY_SUPPORT_ORG,
            "Support Company":      REMEDY_COMPANY,
            "Location Company":     REMEDY_COMPANY,
            "Company":              REMEDY_COMPANY,
            "Submitter":            REMEDY_API.username,
            "Priority":             "Low",
            "Status":               "Assigned",
            "Automation Status":    "Automated",
            "WO Type Field 01":     "Build",
            "WO Type Field 02":     f"CMP OrderID {order.id}",
            "WO Type Field 03":     server.ukhs_funding_source,
            "WO Type Field 04":     server.ukhs_serverorder_notes,
            "WO Type Field 05 Label": "CloudBolt Status",
            "WO Type Field 05":     "Pending Approval",
            "WO Type Field 14":     server.ukhs_patch_group,
            "WO Type Field 16":     server.ukhs_impact,
            "WO Type Field 17":     server.ukhs_urgency,
            "WO Type Field 18":     server.ukhs_dr_tier,
            "TemplateID":           template_id,
            "z1D_Action":           "CREATE"
        }

        return values


    def create_modification_workorder(self, order, description=None, template_id=TEMPLATE_LIST["Modify_Server"]):
        """Create a modification workorder in Remedy

        :param order: The order item to create the workorder for
        :type order.models.Order: Order
        :return: The Remedy Workorder values
        """

        order_item = order.orderitem_set.first()
        if not isinstance(order_item.cast(), ServerModOrderItem):
            return "Error: Order item is not a ServerModOrderItem"

        owner  = order.owner.user
        oic    = order_item.cast()
        server = Server.objects.get(hostname=oic.server.hostname)
        environment = Environment.objects.get(id=oic.environment_id)

        # Template ID
        if TEMPLATE_LIST.get(template_id):
            template_id = TEMPLATE_LIST[template_id]
        elif not template_id.startswith("IDGAA"):
            return "Error: Invalid template ID"

        if not description:
            # Build the description if it wasn't passed in
            description = f"""
    Once this workorder is "In Progress" and the funding process has been marked "Success", CloudBolt will proceed with the server modification.
    -OR-
    View, Edit, Approve or Deny the order here:
    {CLOUDBOLTORDERURL}/{order.id}

    Server Name:\t {server.hostname}
    Quantity:\t {order.mod_server_count()}
    Requester:\t {owner.username}
    Group:\t {order.group.parent.name} \ {order.group.name}
    Total Quoted Cost:\t {order.get_rate_display()}
    Funding Source:\t {server.ukhs_funding_source}

    --MODIFICATION--
"""
            for mod_item, mod_change in oic.delta().items():
                description += f"{mod_item}: {mod_change}\n"

        values = {
            'Summary': f"SRV - Modify - CMP Order {order.id} - {server.hostname}",
            'Detailed Description': description,
            "Customer First Name":  owner.first_name,
            "Customer Last Name":   owner.last_name,
            "RequesterLoginID":     owner.username,
            "First Name":           owner.first_name,
            "Last Name":            owner.last_name,
            "Support Group Name":   REMEDY_SUPPORT_GROUP,
            "Support Organization": REMEDY_SUPPORT_ORG,
            "Support Company":      REMEDY_COMPANY,
            "Location Company":     REMEDY_COMPANY,
            "Company":              REMEDY_COMPANY,
            "Submitter":            REMEDY_API.username,
            "Priority":             "Low",
            "Status":               "Assigned",
            "Automation Status":    "Automated",
            "WO Type Field 01":     "Modify",
            "WO Type Field 02":     f"CMP OrderID {order.id}",
            "WO Type Field 03":     server.ukhs_funding_source,
            "WO Type Field 04":     server.ukhs_serverorder_notes,
            "WO Type Field 05 Label": "CloudBolt Status",
            "WO Type Field 05":     "Pending Approval",
            "TemplateID":           template_id,
            "z1D_Action":           "CREATE"
        }

        return values


    def import_workorder(self,workorder_id,cmp_order_id=None,group='CMP Dev'):
        try:
            workorder = self.get_workorder(workorder_id)
        except Exception as e:
            return f"Error importing workorder: {e}"

        blueprint = ServiceBlueprint.objects.get(name='Remedy Workorder')
        owner = None
        res_type = ResourceType.objects.get(name='remedyworkorder')

        if cmp_order_id:
            order = Order.objects.get(id=cmp_order_id)
            blueprint = order.blueprint
            group = order.group.name
            owner = order.owner

        try:
            group_obj = Group.objects.get(name=group)
        except Group.DoesNotExist:
            return f"Error importing workorder: Group {group} not found"

        res = Resource.objects.create(
            resource_type = res_type,
            name=workorder['values']['Work Order ID'],
            blueprint_id = blueprint.id,
            group = group_obj,
            owner = owner,
            lifecycle = 'PENDING',
        )

        res.bmc_workorder_status = workorder['values']['Status']
        res.bmc_workorder_href   = f"https://{REMEDY_DOMAINNAME}/smartit/app/#/workorder/{workorder['values']['InstanceId']}"
        if cmp_order_id:
            res.order = cmp_order_id
        res.save()
        return True


    def get_form_fields(self,form_name,field_ids=''):
        # Invoke the RemedyAPI.get_form_fields function
        # PowerSHell example:  Invoke-BMCApiRequest -Method GET -URI "$SmartITApi/arsys/v1.0/fields/$Form/$FieldIDs"
        """
        get_form_fields is a member function used to gather form data
        based on a form name and request ID
        The function returns: a tuple with the response content as json and the http status code.

        :param form_name: name of the form to query
        :type form_name: str
        :param req_id: the request ID of the desired entry
        :type req_id: str
        :return: the response content and http status code as a tuple
        :rtype: tuple(json, int)
        """
        url = self.base_url + '/arsys/v1.0/fields' + "/{}/{}".format(form_name, field_ids)
        response = requests.request("GET", url, headers=self.reqHeaders, verify=self.verify,
                                    proxies=self.proxies, timeout=self.timeout)
        response.raise_for_status()

        return response.json(), response.status_code


    def get_environment_capacity(environment):
        """
        Return the available quota limits for the VMware environment.
        """

        quota_set = environment.quota_set

        capacity = {
            'disk_available': float(quota_set.disk_size.available),
            'cpu_available': float(quota_set.cpu_cnt.available),
            'mem_available': float(quota_set.mem_size.available),
            'vm_count': float(quota_set.vm_cnt.used)
        }

        return capacity


    def get_server_rate_hardware_breakdown(order):

        boi = order.orderitem_set.first().cast()
        bia = boi.blueprintitemarguments_set.first() # Arguments for Server

        disk_spec = [Disk(name="Hard disk 1", disk_size=bia.disk_size)]
        # Add additional disks if they exist
        if bia.disk_1_size:
            disk_spec.append(Disk(name="Hard disk 2", disk_size=bia.disk_1_size))
        if bia.disk_2_size:
            disk_spec.append(Disk(name="Hard disk 3", disk_size=bia.disk_2_size))
        if bia.disk_3_size:
            disk_spec.append(Disk(name="Hard disk 4", disk_size=bia.disk_3_size))

        rate_dict = default_compute_rate(
            group               = order.group,
            environment         = bia.environment,
            resource_technology = bia.environment.resource_handler.resource_technology,
            cfvs                = bia.custom_field_values.all(),
            pcvss               = bia.environment.preconfigurations.all(),
            os_build            = bia.os_build,
            apps                = bia.applications.all(),
            quantity            = bia.quantity,
            disks               = disk_spec,
            server=None
        )

        return rate_dict['Hardware']


    def attach_file_to_workorder(self,workorder_id, filepath, filename, details=None, view_access='Public', content_type='application/octet-stream'):
        # Invoke the RemedyAPI.create_form_entry function
        form_name = "WOI:WorkOrderInterface"
        workorder = self.get_workorder(workorder_id)
        req_id = workorder['values']['Request ID']
        values = {
            "z1D_Details": "{}".format(details if details is not None else "No details entered"),
            "z1D_View_Access": "{}".format(view_access if view_access is not None else "Public"),
            "z1D_Action": "MODIFY",
            "z1D_Activity Type*": "General Information",
            "z1D_Secure_Log": "Yes",
            "z2AF_Act_Attachment_1": "{}".format(filename)
        }

        # Create the files multipart submission

        # Cannot send files larger than 10MB (10*1024*1024)
        #   If larger, send the bottom 10MB (where incident issues will likely be)
        try:
            size = getsize(filepath+sep+filename)
            with open(f'{filepath+sep+filename}', 'rb') as file:
                # Do not read more than 10MB of the file
                if size >= 10000000 :
                    # File is bigger than 10MB, so read the last 10MB
                    file.seek(-10000000, SEEK_END)  # Note minus sign
                # Read the remaining of the file (or all of it)
                content = file.read()
        # bare except to avoid errors and put something on the content. Otherwise meaningless.
        except:
            content = 'File {} could not be read'.format(filepath+sep+filename)

        # Add json to the multipart form request
        files = {}
        # None in the first part will not show a filename.
        # need to use json.dumps with the encode. str(values) will not work.
        files['entry'] = (None, json.dumps({'values': values}).encode('utf-8'), 'application/json')
        files['attach-z2AF_Act_Attachment_1'] = (filename, content, content_type)

        url = self.base_url + self.prefix + "/{}/{}".format(form_name, req_id)

        # Send only the authorization header for content-type to be set as multipart by the requests module
        reqHeaders = {'Authorization': self.reqHeaders['Authorization']}
        response = requests.request("PUT", url, data=None, files=files, headers=reqHeaders, verify=self.verify,
                                    proxies=self.proxies, timeout=self.timeout)

        response.raise_for_status()

        # Remedy returns an empty 204 for form updates.
        # get the updated incident and return it with the update status code
        status_code = response.status_code
        updated_incident, _ = self.get_form_entry(form_name, req_id)

        return updated_incident, status_code