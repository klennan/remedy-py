# RemedyHelper.py
"""This module extends the RemedyClient class to provide additional functionality for working with Remedy forms.

The RemedyHelper class provides functions for creating, getting, and setting workorders, tasks, people, and incidents in Remedy.
To use the RemedyHelper class, import the RemedyHelper class from the RemedyHelper module.
Initialize the RemedyHelper class with the Remedy hostname, username, and password, the same way you would with the RemedyClient class.
"""

import requests
from remedy_py.RemedyAPIClient import RemedyClient

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
        super().__init__(host, username, password, port, verify, proxies)

    def __del__(self):
        """
        Destructor for the RemedyHelper class
        """
        self.logout()

    def create_workorder(self,values):
        """Create a workorder in Remedy

        Parameters
        ----------
        values : dict
            A dictionary of values to set on the workorder. Use the function get_workorder_form_fields() to get the field names.

        Returns
        -------
        dict
            The workorder values
        """
        form = "WOI:WorkOrderInterface"
        try:
            workorder = self.create_form_entry(form_name=form,values=values)
        except Exception as e:
            return f"Error creating workorder: {e}"
        return workorder[0]['values']

    def get_workorder(self,workorder_id):
        # Invoke the RemedyAPI.get_form_entry function
        form = "WOI:WorkOrderInterface"
        query = f"?q='Work Order ID'=\"{workorder_id}\""
        try:
            workorder = self.get_form_entry(form_name=form,req_id=query)
        except Exception as e:
            return f"Error getting workorder: {e}"
        return workorder[0]['entries'][0]

    def set_workorder(self,workorder_id,values):
        # Invoke the RemedyAPI.set_form_entry function
        form = "WOI:WorkOrderInterface"
        try:
            workorder = self.set_form_entry(form_name=form,req_id=workorder_id,values=values)
        except Exception as e:
            return f"Error setting workorder: {e}"
        return workorder[0]['values']

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
