import os
import requests
import subprocess

from packaging.version import Version
from time import sleep

MAILPIT_BINARY = os.getenv('MAILPIT_BINARY', '/usr/local/bin/mailpit')


class MailpitConnector:
    base_url = 'http://localhost:8025'
    already_running = None

    def __init__(self):
        for attempts in range(3):
            try:
                response = self.info()
                self.already_running = attempts == 0
            except requests.exceptions.ConnectionError as e:
                print("\nStarting Mailpit server\n")
                self.process = subprocess.Popen([MAILPIT_BINARY])
                sleep(0.2)
            else:
                assert Version(response['Version']) >= Version('1.21'), "Use Mailpit version 1.21 or later"
                break

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete_all()
        if self.already_running is False:
            print("\nStopping Mailpit server\n")
            self.process.terminate()

    def info(self):
        response = requests.get(f'{self.base_url}/api/v1/info')
        return response.json()


    def all_messages(self, limit=None):
        url = f'{self.base_url}/api/v1/messages'
        if limit:
            url = f'{url}?limit={limit}'
        respose = requests.get(url)
        return respose.json()

    def get_message(self, message_id):
        response = requests.get(f'{self.base_url}/api/v1/message/{message_id}')
        return response.json()

    def get_attachment(self, message_id, partid):
        return requests.get(f'{self.base_url}/api/v1/message/{message_id}/part/{partid}')

    def delete_all(self):
        response = requests.delete(f'{self.base_url}/api/v1/messages')
        assert response.status_code == 200 and response.text == 'ok'
