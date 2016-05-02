import socket
import re

__author__ = 'SinLapis'

class Client():
    def __init__(self):
        self.conn_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # todo exception
        self.server_addr = ('127.0.0.1', 2121)
        self.DOWNLOAD_PATH = './download/'

    def extract_code(self, receive):
        return receive[0:3]

    def extract_message(self, message):
        patten = re.compile(r'(.*) (.*)')
        result = patten.match(message)
        if result is not None:
            command, addition = result.groups()
        else:
            command, addition = ('', '')
        return command, addition

    def extract_address(self, receive):
        patten = re.compile(r'.*\((.*)\)')
        result = patten.match(receive).groups()[0]
        port = int(result)
        return ('127.0.0.1', port)

    def start(self):
        self.conn_fd.connect(self.server_addr)
        print(self.conn_fd.recv(1024).decode())
        while True:
            message = input()
            self.conn_fd.send(message.encode())
            receive = self.conn_fd.recv(1024).decode()
            print(receive)
            if message == 'quit':
                self.conn_fd.close()
                print('<client>Client has closed the connection.')
                break
            return_code = self.extract_code(receive)
            command, addition = self.extract_message(message)
            if return_code == '150':
                data_addr = self.extract_address(receive)
                data_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if command == 'retr':
                    file = open(self.DOWNLOAD_PATH + addition, 'w')
                    data_fd.connect(data_addr)
                    while True:
                        buf = data_fd.recv(1024)
                        if(len(buf)!=0):
                            file.write(buf.decode())
                        else:
                            data_fd.close()
                            break
                    file.close()
                    self.conn_fd.send('retrc'.encode())
                    print(self.conn_fd.recv(1024).decode())
                    print('<client>' + addition + ' has been downloaded.')
                elif command == 'stor':
                    file = open(addition)
                    data_fd.connect(data_addr)
                    buf = file.read(1024)
                    while buf != '':
                        data_fd.send(buf)
                        buf = file.read(1024)
                    data_fd.close()
                    file.close()
                    self.conn_fd.send('storc')
                    print(self.conn_fd.recv(1024).decode())
                    print('<client>' + addition + ' has been uploaded.')






