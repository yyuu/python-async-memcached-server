import struct
from twisted.internet import protocol
from logger import log


class Memcached(protocol.Protocol):
    HEADER_STRUCT = ''.join([
        '!',  # big-endian
        'B',  # Magic
        'B',  # Command
        'H',  # Key length
        'B',  # Extras length
        'B',  # Data type
        'H',  # Status
        'L',  # Body length
        'L',  # Opaque
        'Q',  # CAS
    ])

    HEADER_SIZE = 24

    MAGIC = {
        'request': 0x80,
        'response': 0x81
    }

    # All structures will be appended to HEADER_STRUCT
    COMMANDS = {
        # Struct key name
        'get': {'command': 0x00, 'struct': '%ds'},
        # Struct flags|expiry time|key|value
        'set': {'command': 0x01, 'struct': '!LL%ds%ds'},
        'add': {'command': 0x02, 'struct': '!LL%ds%ds'},
        'replace': {'command': 0x03, 'struct': '!LL%ds%ds'},
        'delete': {'command': 0x04, 'struct': '%ds'},
        #'incr': {'command': 0x05, 'struct': '!QQL%ds'},
        #'decr': {'command': 0x06, 'struct': '!QQL%ds'},
        #'flush': {'command': 0x08, 'struct': 'I'},
        #'auth_negotiation': {'command': 0x20},
        #'auth_request': {'command': 0x21, 'struct': '%ds%ds'}
        'version': {'command': 0x0b},
    }

    STATUSES = {
        'success': {'code': 0x00, 'message': ''},
        'key_not_found': {'code': 0x01, 'message': 'Not found'},
        'key_exists': {'code': 0x02, 'message': 'Data exists for key.'},
        'value_too_large': {'code': 0x03, 'message': ''},
        'invalid_arguments': {'code': 0x04, 'message': 'Invalid arguments'},
        'item_not_stored': {'code': 0x05, 'message': ''},
        'non_numeric': {'code': 0x06, 'message': ''},
        'unknown_command': {'code': 0x81, 'message': 'Unknown command'},
        'out_of_memory': {'code': 0x82, 'message': ''},
    }

    MEMCACHED_VERSION = "1.4.13"

    def __init__(self, factory):
        self.factory = factory

    def connectionMade(self):
        log.msg('Yay one client!')

    def sendMessage(self, command, keyLength, extLength, status, opaque, cas,
        extra=None, body=None):
        bodyLength = 0
        if body:
            bodyLength = len(body) + 4  # flags
        else:
            bodyLength = len(status['message'])
        log.msg('Sending message: %s' % \
            status['message'] if not body else body)

        args = [self.HEADER_STRUCT + '%ds' % bodyLength,
                    self.MAGIC['response'],
                    command,
                    keyLength,
                    extLength,
                    0x00,
                    status['code'],
                    bodyLength,
                    opaque,
                    cas]

        if not body:
            args.append(status['message'])
        else:
            args += ['%s%s' % (struct.pack('!L', extra), body)]

        bin = struct.pack(*args)

        self.transport.write(bin)

    def handleCommand(self, magic, command, keyLength, extLength, dataType,
        status, bodyLength, opaque, cas, extra):
        log.msg('Trying to handle command 0x%0.2x' % command)
        commands = dict([(c[1]['command'], c[0]) for c in \
            self.COMMANDS.items()])

        if command not in commands.keys():
            self.sendMessage(command, 0, 0,
                self.STATUSES['unknown_command'], 0, 0)
            return False

        log.msg('Handling %s' % commands[command])

        commandName = 'handle%sCommand' % commands[command].capitalize()
        if hasattr(self, commandName):
            getattr(self, commandName)(magic, command, keyLength, extLength,
            dataType, status, bodyLength, opaque, cas, extra)
            return

    def _handleSetAddReplaceCommand(self, magic, command, keyLength,
        extLength, dataType, status, bodyLength, opaque, cas, extra):
        contentLength = bodyLength - keyLength - extLength
        (flags, expiry, key, value) = struct.unpack(
            self.COMMANDS['set']['struct']  % (keyLength, contentLength),
            extra)

        if command == self.COMMANDS['add']['command'] and \
            key in self.factory.storage:
            self.sendMessage(command, 0, 0, self.STATUSES['key_exists'], 0, 0)
            return

        if command == self.COMMANDS['replace']['command'] and \
            key not in self.factory.storage:
            self.sendMessage(command, 0, 0, self.STATUSES['key_not_found'], 0, 0)
            return

        self.factory.storage[key] = {'flags': flags, 'expiry': expiry,
            'value': value}

        self.sendMessage(command, 0, 0, self.STATUSES['success'], 0, 0)

    def handleSetCommand(self, magic, command, keyLength, extLength, dataType,
        status, bodyLength, opaque, cas, extra):
        return self._handleSetAddReplaceCommand(magic, command, keyLength,
            extLength, dataType, status, bodyLength, opaque, cas, extra)

    def handleAddCommand(self, magic, command, keyLength, extLength, dataType,
        status, bodyLength, opaque, cas, extra):
        return self._handleSetAddReplaceCommand(magic, command, keyLength,
            extLength, dataType, status, bodyLength, opaque, cas, extra)

    def handleReplaceCommand(self, magic, command, keyLength, extLength,
        dataType, status, bodyLength, opaque, cas, extra):
        return self._handleSetAddReplaceCommand(magic, command, keyLength,
            extLength, dataType, status, bodyLength, opaque, cas, extra)

    def handleGetCommand(self, magic, command, keyLength, extLength, dataType,
        status, bodyLength, opaque, cas, extra):
        key = struct.unpack(self.COMMANDS['get']['struct'] % keyLength,
            extra)

        try:
            value = self.factory.storage[key[0]]

            self.sendMessage(command, 0, 4, self.STATUSES['success'],
            0, 1, value['flags'], value['value'])
        except KeyError:
            self.sendMessage(command, len(key[0]), 0,
                self.STATUSES['key_not_found'], 0, 0)

    def handleDeleteCommand(self, magic, command, keyLength, extLength, dataType,
        status, bodyLength, opaque, cas, extra):
        key = struct.unpack(self.COMMANDS['delete']['struct'] % keyLength,
            extra)[0]
        try:
            del self.factory.storage[key]
            self.sendMessage(command, 0, 0, self.STATUSES['success'], 0, 0)
        except KeyError:
             self.sendMessage(command, 0, 0, self.STATUSES['key_not_found'], 0, 0)

    def handleVersionCommand(self, magic, command, keyLength, extLength, dateType,
        status, bodyLength, opaque, cas, extra):
        self.sendMessage(command, 0, 0, self.STATUSES['success'], 0, 0, None, self.MEMCACHED_VERSION)

    def _handleIncrDecrCommand(self, magic, command, keyLength, extLength,
        dataType, status, bodyLength, opaque, cas, extra):
        (delta, initial, expiry, key) = struct.unpack(self.COMMANDS['incr']['struct'] % keyLength, extra)
        if key in self.factory.storage:
            try:
                value = self.factory.storage[key]
                self.factory.storage[key] = {
                    'expiry': expiry,
                    'value': value['value'] + delta,
                }
            except TypeError:
                self.factory.storage[key] = {
                    'expiry': expiry,
                    'value': initial
                }
        else:
            self.factory.storage[key] = {
                    'expiry': expiry,
                    'value': initial
                }

        self.sendMessage(command, 0, 0, self.STATUSES['success'], 0, 0, None,
            self.factory.storage[key])

    def handleIncrCommand(self, *args):
        return self._handleIncrDecrCommand(*args)

    def handleHeader(self, header):
        if len(header) != self.HEADER_SIZE:
            log.msg('Invalid header')
            return False

        (magic, command, keyLength, extLength, dataType, status, bodyLength,
            opaque, cas) = struct.unpack(self.HEADER_STRUCT, header)

        if magic != self.MAGIC['request']:
            log.msg('Invalid magic code 0x%0.2x' % magic)
            return False

        return (magic, command, keyLength, extLength, dataType, status,
            bodyLength, opaque, cas)

    def handleData(self, data):
        header = self.handleHeader(data[:self.HEADER_SIZE])
        if header:
            header = list(header)
            header.append(data[self.HEADER_SIZE:])
            self.handleCommand(*header)

    def dataReceived(self, data):
        self.transport.write(self.handleData(data))


class MemcachedFactory(protocol.Factory):
    protocol = Memcached

    def __init__(self, storage):
        self.storage = storage

    def buildProtocol(self, addr):
        return self.protocol(self)
