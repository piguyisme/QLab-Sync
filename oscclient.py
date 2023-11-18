from time import sleep
from typing import Literal, get_args
from pythonosc import osc_message_builder
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import UDPClient
from pythonosc.osc_server import BlockingOSCUDPServer
from json import loads
import atexit

CueType = Literal["audio", "mic", "video", "camera", "text", "light", "fade", "network", "midi", "midi file", "timecode", "group", "start", "stop", "pause", "load", "reset", "devamp", "goto", "target", "arm", "disarm", "wait", "memo", "script", "list", "cuelist", "cue list", "cart", "cuecart", "cue cart"]

class Cue():
    def __init__(self, id: str, type: CueType, client) -> None:
        self.id = id
        self.type = type
        self.client = client

    def _send_cue_message(self, address: str, *args):
        return self.client.send_message(f"/cue_id/{self.id}" + address, *args)


    def get_name(self) -> str:
        return self._send_cue_message(f"/name")
    def set_name(self, name: str):
        self._send_cue_message(f"/name", name)
        return self
    
    def move_cue(self, new_index: int, parent_id: str):
        self.client.send_message(f"/move/{self.id}", new_index, parent_id)
        return self
    
    def set_number(self, number: str):
        self._send_cue_message('/number', number)
        return self

class NetworkCue(Cue):
    def set_param(self, param: str, value: any):
        self._send_cue_message(f'/parameterValue/{param}', value)
        return self
    def get_parameter_values(self):
        return self._send_cue_message(f'/parameterValues')

    def set_patch_name(self, name: str):
        self._send_cue_message(f'/networkPatchName', name)
        return self
    def get_patch_name(self):
        return self._send_cue_message('/networkPatchName')
    def set_patch_number(self, number: int):
        self._send_cue_message('/networkPatchNumber', number)
        return self
    def get_patch_number(self):
        return self._send_cue_message('/networkPatchNumber')
    
class GroupCue(Cue):
    def collapse(self):
        self._send_cue_message('/collapse')
        return self

cue_type_classes = {
    "network": NetworkCue,
    "group": GroupCue
}

class OSCClient:
    def __init__(self) -> None:
        self.address = '127.0.0.1'
        self.port = 53000
        self.receiving_port = 53001
        self.passcode = None

    def connect(self, address: str, port: int, receiving_port: int, passcode=None):
        if address: self.address = address
        if port: self.port = port
        if receiving_port: self.receiving_port = receiving_port
        if passcode: self.passcode = passcode
        self.udp_client = UDPClient(self.address, self.port)
        self.replies: dict[str, any] = {}
        
        dispatcher = Dispatcher()
        dispatcher.map('*', self._handle_reply)

        self.server = BlockingOSCUDPServer(("127.0.0.1", self.receiving_port), dispatcher)
        self.server.handle_timeout = self._handle_timeout

        # self.send_message('/disconnect')
        # print(self.send_message('/connect', self.passcode))
        self.send_message('/alwaysReply', "1")
        self.send_message('/forgetMeNot', True)
        atexit.register(self._handle_exit)

    def _handle_timeout():
        print('Timed out!')

    def send_message(self, message: str, *args: str):
        msg = osc_message_builder.OscMessageBuilder(message)
        for arg in args:
            if arg: msg.add_arg(arg)
        self.udp_client.send(msg.build())
        self.server.handle_request()
        while(True):
            reply: dict = self.replies.pop(message, None)
            if reply:
                if reply["status"] == "error":
                    raise Exception(str(reply) + f'\nAddress: {message}; Args: {args}')
                return reply.get('data')
            self.server.handle_request()
            sleep(0.1)
    
    def _handle_reply(self, address: str, *args):
        address = address[6:]
        # print(f'Received {address} [Args]: {args}')
        self.replies[address] = loads(args[0])

    def _handle_exit(self):
        self.send_message('/forgetMeNot', False)
        self.send_message('/disconnect')
        print('Disconnected')

    """Creates a cue andd returns a cue object based on type"""
    def create_cue(self, type: CueType):
        assert type in get_args(CueType), f"Cue type invalid"
        cue_id = self.send_message("/new", type)
        if type in cue_type_classes:
            return cue_type_classes[type](cue_id, type, self)
        return Cue(cue_id, type, self)
    def create_group_cue(self) -> GroupCue:
        return self.create_cue("group")
    def create_network_cue(self) -> NetworkCue:
        return self.create_cue("network")

    def get_cue(self, number):
        cue_type = self.send_message(f'/cue/{number}/type')
        cue_id = self.send_message(f'/cue/{number}/uniqueID')
        return Cue(cue_id, cue_type, self)
    
    def get_cue_lists(self):
        return self.send_message(f'/selectedCues/')