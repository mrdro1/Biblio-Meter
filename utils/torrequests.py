# Module from https://github.com/erdiaker/torrequest/blob/master/torrequest.py
import requests
import time
#
import stem
from stem.control import Controller
from stem.process import launch_tor_with_config


class TorRequest(object):
    """ Provides a connection to the TOP network """
    def __init__(self, proxy_port=9050, ctrl_port=9051, password=None, tor_app = None):
        self.proxy_port = proxy_port
        self.ctrl_port = ctrl_port
        self._tor_proc = None
        self.tor_cmd = tor_app
        if not self._tor_process_exists():
            self._tor_proc = self._launch_tor()
        self.ctrl = Controller.from_port(port=self.ctrl_port)
        self.ctrl.authenticate(password=password)
        self.session = requests.Session()
        self.session.proxies.update({
            'http': 'socks5://localhost:%d' % self.proxy_port,
            'https': 'socks5://localhost:%d' % self.proxy_port,
        })


    def _tor_process_exists(self):
        try:
            ctrl = Controller.from_port(port=self.ctrl_port)
            ctrl.close()
            return True
        except Exception as error:
            return False


    def _launch_tor(self):
        return launch_tor_with_config(
            config={
            'SocksPort': str(self.proxy_port),
            'ControlPort': str(self.ctrl_port)
            },
            tor_cmd=self.tor_cmd,
            take_ownership=True)


    def close(self):
        try: 
            self.session.close()
        except: pass
        try: 
            self.ctrl.close()
        except: pass
        if self._tor_proc:
            self._tor_proc.terminate()


    def reset_identity_async(self):
        self.ctrl.signal(stem.Signal.NEWNYM)


    def reset_identity(self):
        self.reset_identity_async()
        time.sleep(self.ctrl.get_newnym_wait())


    def get(self, *args, **kwargs):
        return self.session.get(*args, **kwargs)


    def post(self, *args, **kwargs):
        return self.session.post(*args, **kwargs)


    def put(self, *args, **kwargs):
        return self.session.put(*args, **kwargs)


    def patch(self, *args, **kwargs):
        return self.session.patch(*args, **kwargs)
    

    def delete(self, *args, **kwargs):
        return self.session.delete(*args, **kwargs)


    def __enter__(self):
        return self


    def __exit__(self, *args):
        self.close()