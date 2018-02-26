#!/usr/bin/env python

"""
AMQP type test sender shim for qpid-interop-test
"""

#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

import json
import os.path
import signal
import struct
import sys
import traceback
import uuid

import proton
import proton.handlers
import proton.reactor
import _compat

class AmqpTypesTestSender(proton.handlers.MessagingHandler):
    """
    Sender shim for AMQP types test
    This shim receives the AMQP type and a list of test values. Each value is sent in a message body of the appropriate
    AMQP type. There is no returned value.
    """
    def __init__(self, broker_url, queue_name, amqp_type, test_value_list):
        super(AmqpTypesTestSender, self).__init__()
        self.broker_url = broker_url
        self.queue_name = queue_name
        self.amqp_type = amqp_type
        self.test_value_list = test_value_list
        self.sent = 0
        self.confirmed = 0
        self.total = len(test_value_list)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def on_start(self, event):
        """Event callback for when the client starts"""
        connection = event.container.connect(url=self.broker_url, sasl_enabled=False, reconnect=False)
        event.container.create_sender(connection, target=self.queue_name)

    def on_sendable(self, event):
        """Event callback for when send credit is received, allowing the sending of messages"""
        if self.sent == 0:
            for test_value in self.test_value_list:
                if event.sender.credit:
                    message = self.create_message(test_value)
                    if message is not None:
                        event.sender.send(message)
                        self.sent += 1
                    else:
                        event.connection.close()
                        return

    def create_message(self, test_value):
        """
        Creates a single message with the test value translated from its string representation to the appropriate
        AMQP value (set in self.amqp_type).
        """
        if self.amqp_type == 'null':
            return proton.Message(id=(self.sent+1), body=None)
        if self.amqp_type == 'boolean':
            return proton.Message(id=(self.sent+1), body=True if test_value == 'True' else False)
        if self.amqp_type == 'ubyte':
            return proton.Message(id=(self.sent+1), body=proton.ubyte(int(test_value, 16)))
        if self.amqp_type == 'ushort':
            return proton.Message(id=(self.sent+1), body=proton.ushort(int(test_value, 16)))
        if self.amqp_type == 'uint':
            return proton.Message(id=(self.sent+1), body=proton.uint(int(test_value, 16)))
        if self.amqp_type == 'ulong':
            return proton.Message(id=(self.sent+1), body=proton.ulong(int(test_value, 16)))
        if self.amqp_type == 'byte':
            return proton.Message(id=(self.sent+1), body=proton.byte(int(test_value, 16)))
        if self.amqp_type == 'short':
            return proton.Message(id=(self.sent+1), body=proton.short(int(test_value, 16)))
        if self.amqp_type == 'int':
            return proton.Message(id=(self.sent+1), body=proton.int32(int(test_value, 16)))
        if self.amqp_type == 'long':
            return proton.Message(id=(self.sent+1), body=_compat.long(test_value, 16))
        if self.amqp_type == 'float':
            return proton.Message(id=(self.sent+1),
                                  body=proton.float32(struct.unpack('!f', _compat.decode_hex(test_value[2:]))[0]))
        if self.amqp_type == 'double':
            return proton.Message(id=(self.sent+1), body=struct.unpack('!d', _compat.decode_hex(test_value[2:]))[0])
        if self.amqp_type == 'decimal32':
            return proton.Message(id=(self.sent+1), body=proton.decimal32(int(test_value[2:], 16)))
        if self.amqp_type == 'decimal64':
            l64 = _compat.long(test_value[2:], 16)
            return proton.Message(id=(self.sent+1), body=proton.decimal64(l64))
        if self.amqp_type == 'decimal128':
            return proton.Message(id=(self.sent+1), body=proton.decimal128(_compat.decode_hex(test_value[2:])))
        if self.amqp_type == 'char':
            if len(test_value) == 1: # Format 'a'
                return proton.Message(id=(self.sent+1), body=proton.char(test_value))
            val = int(test_value, 16)
            return proton.Message(id=(self.sent+1), body=proton.char(_compat.unichr(val)))
        if self.amqp_type == 'timestamp':
            return proton.Message(id=(self.sent+1), body=proton.timestamp(int(test_value, 16)))
        if self.amqp_type == 'uuid':
            return proton.Message(id=(self.sent+1), body=uuid.UUID(test_value))
        if self.amqp_type == 'binary':
            return proton.Message(id=(self.sent+1), body=test_value.encode('utf-8'))
        if self.amqp_type == 'string':
            return proton.Message(id=(self.sent+1), body=_compat.unicode(test_value))
        if self.amqp_type == 'symbol':
            return proton.Message(id=(self.sent+1), body=proton.symbol(test_value))
        if self.amqp_type == 'list':
            return proton.Message(id=(self.sent+1), body=test_value)
        if self.amqp_type == 'map':
            return proton.Message(id=(self.sent+1), body=test_value)
        print('send: Unsupported AMQP type "%s"' % self.amqp_type)
        return None

    def on_accepted(self, event):
        """Event callback for when a sent message is accepted by the broker"""
        self.confirmed += 1
        if self.confirmed == self.total:
            event.connection.close()

    def on_disconnected(self, event):
        """Event callback for when the broker disconnects with the client"""
        self.sent = self.confirmed

    def on_transport_error(self, event):
        print('Sender: Broker not found at %s' % self.broker_url)

    @staticmethod
    def signal_handler(signal_number, _):
        """Signal handler"""
        if signal_number in [signal.SIGTERM, signal.SIGINT]:
            print('Sender: received signal %d, terminating' % signal_number)
            sys.exit(1)



# --- main ---
# Args: 1: Broker address (ip-addr:port)
#       2: Queue name
#       3: AMQP type
#       4...n: Test value(s) as strings
try:
    SENDER = AmqpTypesTestSender(sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4]))
    proton.reactor.Container(SENDER).run()
except KeyboardInterrupt:
    pass
except Exception as exc:
    print(os.path.basename(sys.argv[0]), 'EXCEPTION:', exc)
    print(traceback.format_exc())
    sys.exit(1)
