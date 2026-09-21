# See LICENSE file for full copyright and licensing details.

import json
from hashlib import md5

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

URL = "webservice.php"


class ResCompany(models.Model):
    _inherit = "res.company"

    access_key = fields.Char()
    vtiger_server = fields.Char()
    user_name = fields.Char()
    last_sync_date = fields.Datetime(string="Last Synced Time")

    def get_vtiger_server_url(self):
        self.ensure_one()
        server = (self.vtiger_server or "").strip().rstrip("/")
        return "%s/%s" % (server, URL)

    def get_vtiger_access_key(self):
        """Get the token using 'getchallenge' operation"""
        self.ensure_one()
        url = self.get_vtiger_server_url()
        try:
            response = requests.get(
                url,
                params={"operation": "getchallenge", "username": self.user_name},
                timeout=20,
            )
            response.raise_for_status()
            token = response.json()["result"]["token"]
        except (requests.RequestException, json.JSONDecodeError, KeyError) as error:
            raise UserError(
                _("Unable to get the VTiger access token for company %s.")
                % self.display_name
            ) from error
        # Use the TOKEN + ACCESSKEY to create the tokenized accessKey
        tokenized_access_key = md5(
            token.encode("utf-8") + self.access_key.encode("utf-8")
        )
        return tokenized_access_key.hexdigest()

    def vtiger_login(self, access_key):
        """Using AccessKey tokenized, perform a login operation."""
        self.ensure_one()
        values = {
            "operation": "login",
            "username": self.user_name,
            "accessKey": access_key,
        }
        url = self.get_vtiger_server_url()
        try:
            response = requests.post(url=url, data=values, timeout=20)
            response.raise_for_status()
            response_data = response.json()
            session_name = response_data["result"]["sessionName"]
        except (requests.RequestException, json.JSONDecodeError, KeyError) as error:
            raise UserError(
                _("Unable to login to VTiger for company %s.") % self.display_name
            ) from error
        # Return sessionName
        return session_name

    @api.model
    def sync_vtiger(self):
        companies = self.search(
            [
                ("user_name", "!=", False),
                ("access_key", "!=", False),
                ("vtiger_server", "!=", False),
            ]
        )
        return companies.action_sync_vtiger()

    def action_sync_vtiger(self):
        # TODO: If we need multi-company, here we have to update code.
        self.write({"last_sync_date": fields.Datetime.now()})
        return True
