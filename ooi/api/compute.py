# -*- coding: utf-8 -*-

# Copyright 2015 Spanish National Research Council
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json

import ooi.api
import ooi.api.base
from ooi.occi.core import collection
from ooi.occi.infrastructure import compute
from ooi.openstack import helpers
from ooi.openstack import templates


class Controller(ooi.api.base.Controller):
    def _get_compute_resources(self, servers):
        occi_compute_resources = []
        if servers:
            for s in servers:
                s = compute.ComputeResource(title=s["name"], id=s["id"])
                occi_compute_resources.append(s)

        return occi_compute_resources

    def _get_compute_ids(self, req):
        tenant_id = req.environ["keystone.token_auth"].user.project_id
        req = self._get_req(req,
                            path="/%s/servers" % tenant_id,
                            method="GET")
        response = req.get_response(self.app)
        return [s["id"] for s in self.get_from_response(response,
                                                        "servers", [])]

    def _delete(self, req, ids):
        tenant_id = req.environ["keystone.token_auth"].user.project_id
        for id in ids:
            req = self._get_req(req,
                                path="/%s/servers/%s" % (tenant_id,
                                                         id),
                                method="DELETE")
            response = req.get_response(self.app)
            if response.status_int not in [204]:
                raise ooi.api.base.exception_from_response(response)
        return []

    def index(self, req):
        tenant_id = req.environ["keystone.token_auth"].user.project_id
        req = self._get_req(req, path="/%s/servers" % tenant_id)
        response = req.get_response(self.app)
        servers = self.get_from_response(response, "servers", [])
        occi_compute_resources = self._get_compute_resources(servers)

        return collection.Collection(resources=occi_compute_resources)

    @ooi.api.parse
    @ooi.api.validate("kind",
                      {"http://schemas.ogf.org/occi/infrastructure#": 1},
                      term="compute")
    @ooi.api.validate("mixin",
                      {"http://schemas.openstack.org/template/resource#": 1,
                       "http://schemas.openstack.org/template/os#": 1})
    def create(self, req, headers, params, body):
        tenant_id = req.environ["keystone.token_auth"].user.project_id
        req = self._get_req(req,
                            path="/%s/servers" % tenant_id,
                            content_type="application/json",
                            body=json.dumps({
                                "server": {
                                    "name": params["/occi/infrastructure"],
                                    "imageRef": params["/template/os"],
                                    "flavorRef": params["/template/resource"]
                                }}))
        response = req.get_response(self.app)
        # We only get one server
        server = self.get_from_response(response, "server", {})

        # The returned JSON does not contain the server name
        server["name"] = params["/occi/infrastructure"]
        occi_compute_resources = self._get_compute_resources([server])

        return collection.Collection(resources=occi_compute_resources)

    def show(self, req, id):
        tenant_id = req.environ["keystone.token_auth"].user.project_id

        # get info from server
        req = self._get_req(req, path="/%s/servers/%s" % (tenant_id, id))
        response = req.get_response(self.app)
        s = self.get_from_response(response, "server", {})

        # get info from flavor
        req = self._get_req(req, path="/%s/flavors/%s" % (tenant_id,
                                                          s["flavor"]["id"]))
        response = req.get_response(self.app)
        flavor = self.get_from_response(response, "flavor", {})
        res_tpl = templates.OpenStackResourceTemplate(flavor["name"],
                                                      flavor["vcpus"],
                                                      flavor["ram"],
                                                      flavor["disk"])

        # get info from image
        req = self._get_req(req, path="/%s/images/%s" % (tenant_id,
                                                         s["image"]["id"]))
        response = req.get_response(self.app)
        image = self.get_from_response(response, "image", {})
        os_tpl = templates.OpenStackOSTemplate(image["id"],
                                               image["name"])

        # build the compute object
        # TODO(enolfc): link to network + storage
        comp = compute.ComputeResource(title=s["name"], id=s["id"],
                                       cores=flavor["vcpus"],
                                       hostname=s["name"],
                                       memory=flavor["ram"],
                                       state=helpers.occi_state(s["status"]),
                                       mixins=[os_tpl, res_tpl])
        return [comp]

    def delete(self, req, id):
        return self._delete(req, [id])

    def delete_all(self, req):
        return self._delete(req, self._get_compute_ids(req))
