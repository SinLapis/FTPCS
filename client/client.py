import socket

__author__ = 'SinLapis'

class Client():
    def __init__(self):
        self.conn_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # todo exception
        self.server_addr = ("127.0.0.1", 2121)

    def start(self):
        self.conn_fd.connect(self.server_addr)
        print(self.conn_fd.recv(1024).decode())
        while True:
            message = input()
            self.conn_fd.send(message.encode())
            print(self.conn_fd.recv(1024).decode())
            if message == 'quit':
                self.conn_fd.close()
                print('Client has closed the connection.')
                break
