import copy
import datetime
import json
from os import path
import requests
import time
from urllib.parse import urljoin


class HealtCheck:
    def __init__(self, user_info=path.expanduser('~/.config/datahub/config.json'),
                        base_url='https://api.datahub.io'):
        self.base_url = base_url
        self.user_info = user_info
        if isinstance(user_info, str):
            self.user_info = json.loads(open(user_info).read())
        self.jwt = self.user_info.get('token')
        self.owner_id = self.user_info['profile'].get('id')
        self.email = self.user_info['profile'].get('email')
        self.username = self.user_info['profile'].get('username')
        self.now = datetime.datetime.now()
        self.health_report = {}

    @staticmethod
    def check_status(resp, report_name, status=200):
        success = resp.status_code == status
        report = {
            'success': success,
            'errors': 'Unexpected status code: Expected %s, but Recieved %s' % (
                                    resp.status_code, status) if not success else None,
            'name': report_name
        }
        return report

    @staticmethod
    def check_body(body, key, exp_value, report_name):
        success = body.get(key) == exp_value
        report = {
            'success': success,
            'errors': 'Unexpected key/value in body: Expected {%s:%s}, but Recieved {%s:%s}' % (
                    key, exp_value, key, body.get(key)) if not success else None,
            'name': report_name
        }
        return report

    @staticmethod
    def check_message(actual_error, expected_error, report_name):
        success = actual_error == expected_error
        report = {
            'success': success,
            'errors': 'Unexpected error message: Expected "%s", but Recieved "%s"' % (
                    expected_error, actual_error) if not success else None,
            'name': report_name
        }
        return report

    @staticmethod
    def check_numbers(low_number, high_number, report_name, equal=False):
        success = low_number < high_number
        condition = 'greather than'
        if equal:
            success = low_number == high_number
            condition = 'equal to'
        report = {
            'success': success,
            'errors': 'Expected %s %s, but Received %s' % (
                            condition, low_number, high_number) if not success else None,
            'name': report_name
        }
        return report

    def check_flowmanager(self, prefix='source', dataset_id = 'basic-csv', valid_content=None):
        info = {
            'prefix': prefix,
            'owner': self.username,
            'ownerid':self.owner_id,
            'dataset_id': dataset_id,
            'revision': 'latest'
        }
        flowmanager_report = []

        if valid_content is None:
            valid_content = json.loads(open('content.json').read() % info)
        api_url = urljoin(self.base_url, prefix)
        info_endpoint = urljoin(api_url, '{prefix}/{ownerid}/{dataset_id}/{revision}')
        upload_endpoint = urljoin(api_url, '{prefix}/upload'.format(prefix=prefix))

        resp = requests.post(upload_endpoint)
        rep = HealtCheck.check_status(resp, 'Upload without content: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload without content: success is false')
        flowmanager_report.append(rep)
        message = 'Received empty contents (make sure your content-type is correct)'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload without content: error message is correct')
        flowmanager_report.append(rep)

        content = {}
        resp = requests.post(upload_endpoint, json=content)
        rep = HealtCheck.check_status(resp, 'Upload without owner: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload without owner: success is false')
        flowmanager_report.append(rep)
        message = 'Missing owner in spec'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload without owner: error message is correct')
        flowmanager_report.append(rep)

        content = {'meta': {'ownerid': 'non-existing-owner'}}
        resp = requests.post(upload_endpoint, json=content)
        rep = HealtCheck.check_status(resp, 'Upload with invalid owner: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload with invalid owner: success is false')
        flowmanager_report.append(rep)
        message = 'No token or token not authorised for owner'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload with invalid owner: error message is correct')
        flowmanager_report.append(rep)

        content = valid_content
        resp = requests.post(upload_endpoint, json=content)
        rep = HealtCheck.check_status(resp, 'Upload with no JWT: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload with no JWT: success is false')
        flowmanager_report.append(rep)
        message = 'No token or token not authorised for owner'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload with no JWT: error message is correct')
        flowmanager_report.append(rep)

        content = copy.deepcopy(valid_content)
        content['meta']['dataset'] = 'new-basic-csv'
        resp = requests.post(upload_endpoint, json=content, headers={'auth-token': self.get_token('source')})
        rep = HealtCheck.check_status(resp, 'Upload exeeding limits: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload exeeding limits: success is false')
        flowmanager_report.append(rep)
        message = 'Max datasets for user exceeded plan limit (2)'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload exeeding limits: error message is correct')
        flowmanager_report.append(rep)

        content = copy.deepcopy(valid_content)
        content['inputs'][0]['kind'] = 'invalid'
        resp = requests.post(upload_endpoint, json=content, headers={'auth-token': self.get_token('source')})
        rep = HealtCheck.check_status(resp, 'Upload with invalid input: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload with invalid input: success is false')
        flowmanager_report.append(rep)
        message = 'Unexpected error: Only supporting datapackage inputs atm'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload with invalid input: error message is correct')
        flowmanager_report.append(rep)

        content = copy.deepcopy(valid_content)
        content['schedule'] = 'every 1k'
        resp = requests.post(upload_endpoint, json=content, headers={'auth-token': self.get_token('source')})
        rep = HealtCheck.check_status(resp, 'Upload with invalid schedule unit: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload with invalid schedule unit: success is false')
        flowmanager_report.append(rep)
        message = 'Bad time unit for schedule, only s/m/h/d/w are allowed'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload with invalid schedule unit: error message is correct')
        flowmanager_report.append(rep)

        content = copy.deepcopy(valid_content)
        content['schedule'] = 'every 1s'
        resp = requests.post(upload_endpoint, json=content, headers={'auth-token': self.get_token('source')})
        rep = HealtCheck.check_status(resp, 'Upload with invalid schedule time: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Upload with invalid schedule time: success is false')
        flowmanager_report.append(rep)
        message = 'Can\'t schedule tasks for less than one minute'
        rep = HealtCheck.check_message(body.get('errors', [''])[0], message,
                                'Upload with invalid schedule time: error message is correct')
        flowmanager_report.append(rep)

        resp = requests.get(info_endpoint.format(**info))
        rep = HealtCheck.check_status(resp, 'Latest revision: status 200', 200)
        flowmanager_report.append(rep)
        latest_revision = int(resp.json().get('id', '').split('/')[-1])
        content = valid_content
        resp = requests.post(upload_endpoint, json=content, headers={'auth-token': self.get_token('source')})
        rep = HealtCheck.check_status(resp, 'Upload valid data: status 200', 200)
        flowmanager_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', True, 'Upload valid data: success is true')
        flowmanager_report.append(rep)
        time.sleep(90)

        resp = requests.get(info_endpoint.format(**info))
        new_latest_revision = int(resp.json().get('id', '').split('/')[-1])
        rep = HealtCheck.check_numbers(latest_revision, new_latest_revision, 'New revision processed')
        flowmanager_report.append(rep)

        body = resp.json()
        rep = HealtCheck.check_body(body, 'state', 'SUCCEEDED', 'New revision succeeded')
        flowmanager_report.append(rep)

        info['revision'] = 'successful'
        resp = requests.get(info_endpoint.format(**info))
        successful_revision = int(resp.json().get('id', '').split('/')[-1])
        rep = HealtCheck.check_status(resp, 'New revision succeeded', 200)
        flowmanager_report.append(rep)
        rep = HealtCheck.check_numbers(new_latest_revision, successful_revision, 'Successful and latest revision match', equal=True)
        flowmanager_report.append(rep)

        info['revision'] = str(successful_revision)
        resp = requests.get(info_endpoint.format(**info))
        successful_revision = int(resp.json().get('id', '').split('/')[-1])
        rep = HealtCheck.check_status(resp, 'Able to get with revision number', 200)
        flowmanager_report.append(rep)

        info['revision'] = str(successful_revision + 1)
        resp = requests.get(info_endpoint.format(**info))
        rep = HealtCheck.check_status(resp, 'Get invalid revision number: status 404', 404)
        flowmanager_report.append(rep)

        info['revision'] = 'invalid'
        resp = requests.get(info_endpoint.format(**info))
        rep = HealtCheck.check_status(resp, 'Get invalid revision word: status 404', 404)
        flowmanager_report.append(rep)
        self.health_report['flowmanager_report'] = flowmanager_report

    def check_auth(self, prefix='auth'):
        auth_check = urljoin(self.base_url, path.join(prefix, 'check?jwt={jwt}'))
        auth_authorize = urljoin(self.base_url, path.join(prefix, 'authorize?jwt={jwt}&service={service}' ))
        auth_update = urljoin(self.base_url, path.join(prefix, 'update?jwt={jwt}&username={username}'))
        auth_public_key = urljoin(self.base_url, path.join(prefix, 'public-key' ))
        auth_resolver = urljoin(self.base_url, path.join(prefix, 'resolve?username={username}' ))
        auth_profile = urljoin(self.base_url, path.join(prefix, 'profile' ))

        auth_report = []

        resp = requests.get(auth_check.format(jwt='wrong'))
        rep = HealtCheck.check_status(resp, 'Auth Check not authenticate: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'authenticated', False, 'Auth check not authenticate: success is false')
        auth_report.append(rep)

        resp = requests.get(auth_check.format(jwt=self.jwt))
        rep = HealtCheck.check_status(resp, 'Auth Check authenticated: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'authenticated', True, 'Auth Check authenticated: success is true')
        auth_report.append(rep)

        resp = requests.get(auth_authorize.format(jwt='wrong', service='service'))
        rep = HealtCheck.check_status(resp, 'Auth authorize invalid jwt: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'permissions', {}, 'Auth authorize invalid jwt: no pemissions')
        auth_report.append(rep)

        resp = requests.get(auth_authorize.format(jwt=self.jwt, service='service'))
        rep = HealtCheck.check_status(resp, 'Auth authorize invalid service: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'permissions', {}, 'Auth authorize invalid service: no pemissions')
        auth_report.append(rep)

        resp = requests.get(auth_authorize.format(jwt=self.jwt, service='source'))
        rep = HealtCheck.check_status(resp, 'Auth authorize success for source: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'permissions', {'max_dataset_num': 2}, 'Auth authorize success: pemissions there')
        auth_report.append(rep)

        resp = requests.get(auth_authorize.format(jwt=self.jwt, service='source'))
        rep = HealtCheck.check_status(resp, 'Auth authorize success for source service: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'permissions', {'max_dataset_num': 2}, 'Auth authorize success for rawstore service: pemissions there')
        auth_report.append(rep)

        resp = requests.get(auth_authorize.format(jwt=self.jwt, service='rawstore'))
        rep = HealtCheck.check_status(resp, 'Auth authorize success for source service: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'permissions', {'max_dataset_num': 2}, 'Auth authorize success for rawstore service: pemissions there')
        auth_report.append(rep)

        resp = requests.post(auth_update.format(jwt='invalid', username='tester'))
        rep = HealtCheck.check_status(resp, 'Auth update invalid jwt: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Auth update invalid jwt: success false')
        auth_report.append(rep)
        rep = HealtCheck.check_message(body.get('error', ''), 'Not authenticated', 'Auth update invalid jwt: Error message is incorrect')
        auth_report.append(rep)

        resp = requests.post(auth_update.format(jwt=self.jwt, username='tester'))
        rep = HealtCheck.check_status(resp, 'Auth update valid jwt: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'success', False, 'Auth update valid jwt: success false')
        auth_report.append(rep)
        message = 'Cannot modify username, already set'
        rep = HealtCheck.check_message(body.get('error', ''), message, 'Auth update valid jwt: Error message is incorrect')
        auth_report.append(rep)

        resp = requests.get(auth_public_key)
        rep = HealtCheck.check_status(resp, 'Auth public key: status 200', 200)
        auth_report.append(rep)

        resp = requests.get(auth_resolver.format(username=self.username))
        rep = HealtCheck.check_status(resp, 'Auth resolve valid username: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'userid', self.owner_id, 'Auth resolve valid username: coorect username')
        auth_report.append(rep)

        resp = requests.get(auth_resolver.format(username='invalid'))
        rep = HealtCheck.check_status(resp, 'Auth resolve invalid username: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'userid', None, 'Auth resolve valid username: username null')
        auth_report.append(rep)

        resp = requests.get(authprofile.format(username=self.username))
        rep = HealtCheck.check_status(resp, 'Auth profile valid username: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'userid', self.owner_id, 'Auth profile valid username: coorect username')
        auth_report.append(rep)

        resp = requests.get(authprofile.format(username='invalid'))
        rep = HealtCheck.check_status(resp, 'Auth profile invalid username: status 200', 200)
        auth_report.append(rep)
        body = resp.json()
        rep = HealtCheck.check_body(body, 'userid', None, 'Auth profile invalid username: username null')
        auth_report.append(rep)

        self.health_report['auth_report'] = auth_report

    def get_report(self):
        return self.health_report

    def get_token(self, service):
        resp = requests.get(urljoin(self.base_url, 'auth/authorize?jwt=%s&service=%s' % (self.jwt, service)))
        return resp.json().get('token')
