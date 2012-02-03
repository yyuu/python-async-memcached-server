import struct
from twisted.trial import unittest
from twisted.test import proto_helpers
from pmemcached.storages.memory import Storage
from pmemcached.server import MemcachedFactory


class ServerTests(unittest.TestCase):
    HEADER_STRUCT = '!BBHBBHLLQ'
    HEADER_SIZE = 24

    MAGIC = {
        'request': 0x80,
        'response': 0x81
    }

    # All structures will be appended to HEADER_STRUCT
    COMMANDS = {
        'get': {'command': 0x00, 'struct': '%ds'},
        'set': {'command': 0x01, 'struct': 'LL%ds%ds'},
        'add': {'command': 0x02, 'struct': 'LL%ds%ds'},
        'replace': {'command': 0x03, 'struct': 'LL%ds%ds'},
        'delete': {'command': 0x04, 'struct': '%ds'},
        'incr': {'command': 0x05, 'struct': 'QQL%ds'},
        'decr': {'command': 0x06, 'struct': 'QQL%ds'},
        'flush': {'command': 0x08, 'struct': 'I'},
        'stat': {'command': 0x10},
        'auth_negotiation': {'command': 0x20},
        'auth_request': {'command': 0x21, 'struct': '%ds%ds'}
    }

    STATUS = {
        'success': 0x00,
        'key_not_found': 0x01,
        'key_exists': 0x02,
        'auth_error': 0x08,
        'unknown_command': 0x81
    }

    FLAGS = {
        'pickle': 1 << 0,
        'integer': 1 << 1,
        'long': 1 << 2,
        'compressed': 1 << 3
    }

    def setUp(self):
        storage = Storage()
        factory = MemcachedFactory(storage)
        self.protocol = factory.buildProtocol(('127.0.0.1', 0))
        self.tr = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.tr)


    def testSet(self):
        key = 'foo'
        value = 'bar'

        flags = 0
        time = 1000
        self.protocol.dataReceived(struct.pack(self.HEADER_STRUCT + \
            self.COMMANDS['set']['struct'] % (len(key), len(value)),
            self.MAGIC['request'],
            self.COMMANDS['set']['command'],
            len(key),
            8, 0, 0, len(key) + len(value) + 8, 0, 0, flags, time, key, value))

        ret = self.protocol.dataReceived(struct.pack(self.HEADER_STRUCT + \
            self.COMMANDS['get']['struct'] % (len(key)),
            self.MAGIC['request'],
            self.COMMANDS['get']['command'],
            len(key), 0, 0, 0, len(key), 0, 0, key))

        self.assertTrue(False)
