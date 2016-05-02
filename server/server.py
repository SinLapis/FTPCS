import socket
import select
import errno
import re
import os
import stat
import threading
import random
from server import status

__author__ = 'SinLapis'


class Server():
    def __init__(self):
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cmd_socket.bind(('', 2121))
        self.cmd_socket.listen(1)
        self.cmd_socket.setblocking(0)
        self.cmd_epoll = select.epoll()
        self.cmd_epoll.register(self.cmd_socket.fileno(), select.EPOLLIN)

        self.connections = {}
        self.addresses = {}
        self.messages = {}
        self.login_info = {}
        self.work_path = {}
        self.need_username = set()
        self.need_password = set()
        self.logged_in = set()
        self.transferring = set()

        self.func_key = {
            'user': self.user,
            'pass': self.pw,
            'list': self.ls,
            'size': self.size,
            'retr': self.retr,
        }
        self.user_info = {
            'admin': 'admin',
        }

        self.FTP_ROOT = '/home/sinlapis/ftproot'

    def extract(self, message):
        patten = re.compile(r'(.*) (.*)')
        t = None
        try:
            t = patten.match(message).groups()
        except:
            pass
        return t

    def user(self, username, fd):
        if fd in self.need_username:
            self.login_info[fd] = username
            try:
                self.need_username.remove(fd)
            except:
                pass
            self.need_password.add(fd)
            message = status.need_password
        else:
            message = status.implement_error
        return message

    def pw(self, password, fd):
        if fd in self.need_password:
            username = self.login_info[fd]
            if username in self.user_info:
                if self.user_info[username] == password:
                    message = status.login_success
                    self.logged_in.add(fd)
                    self.work_path[fd] = self.FTP_ROOT + '/'
                else:
                    message = status.login_error
                    self.need_username.add(fd)
            else:
                message = status.login_error
                self.need_username.add(fd)
            try:
                self.need_password.remove(fd)
            except:
                pass
        else:
            message = status.implement_error
        return message

    def ls(self, path, fd):
        if fd in self.logged_in:
            dirs = []
            files = []
            full_path = self.FTP_ROOT + path
            self.work_path[fd] = full_path
            try:
                names = os.listdir(full_path)
                for name in names:
                    if stat.S_ISDIR(os.stat(full_path + name).st_mode):
                        dirs.append(name)
                    else:
                        files.append(name)
                message = status.command_implement
                message += '\ndirs:'
                for dir in dirs:
                    message += '\n\t' + dir
                message += '\nfiles:'
                for file in files:
                    message += '\n\t' + file
            except FileNotFoundError:
                message = status.unavailable_file
        else:
            message = status.need_account
        return message

    def size(self, filename, fd):
        if fd in self.logged_in:
            try:
                message = status.command_implement + '\n'
                message += str(os.stat(self.work_path[fd] + filename).st_size)
            except FileNotFoundError:
                message = status.unavailable_file
        else:
            message = status.need_account
        return message

    def retr(self, filename, fd):
        if fd in self.logged_in:
            self.transferring.add(fd)
            data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = random.randrange(2122, 65535)
            while True:
                try:
                    data_sock.bind(('', port))
                    break
                except socket.error:
                    port = random.randrange(2122, 65535)
            threading.Thread(target=self.retr_transfer,
                             args=(self.work_path[fd] + filename,
                                   data_sock, )).start()
            port = '(' + str(port) + ')'
            message = status.transfer_ready + port
        else:
            message = status.need_account
        return message

    def retr_transfer(self, file_path, data_sock):

        data_sock.listen(1)
        file = open(file_path)
        data_fd, addr = data_sock.accept()
        buf = file.read(1024)
        while buf != '':
            data_fd.send(buf.encode())
            buf = file.read(1024)
        file.close()
        data_fd.close()
        data_sock.close()

    def delete(self, fd):
        try:
            del self.login_info[fd]
            del self.messages[fd]
            del self.connections[fd]
            del self.work_path[fd]
            self.need_username.remove(fd)
            self.need_password.remove(fd)
            self.logged_in.remove(fd)
        except:
            pass

    def write(self, connection, message):
        connection.send(message.encode())

    def read(self, connection, fd):
        message = ''
        while True:
            try:
                buffer = connection.recv(10).decode()
                if not buffer and not message:
                    self.cmd_epoll.unregister(fd)
                    connection.close()
                    self.delete(fd)
                    break
                else:
                    message += buffer
            except socket.error as msg:
                if msg.errno is not errno.EAGAIN:
                    self.cmd_epoll.unregister(fd)
                    connection.close()
                    self.delete(fd)
                    print('Error!' + str(msg) + '\n')
                break
        return message

    def start(self):

        while True:
            epoll_list = self.cmd_epoll.poll()
            for fd, events in epoll_list:
                # connection event
                if fd == self.cmd_socket.fileno():
                    connection, address = self.cmd_socket.accept()
                    connection.setblocking(0)
                    self.write(connection, status.welcome)
                    self.cmd_epoll.register(connection.fileno(),
                                            select.EPOLLIN | select.EPOLLET)
                    self.connections[connection.fileno()] = connection
                    self.addresses[connection.fileno()] = address
                    self.need_username.add(connection.fileno())
                # reading event
                elif events & select.EPOLLIN:
                    message = self.read(self.connections[fd], fd)
                    print(message)
                    if message == 'quit':
                        self.write(self.connections[fd], status.quit)
                        self.cmd_epoll.unregister(fd)
                        self.connections[fd].close()
                        self.delete(fd)
                    # todo transfer status
                    elif (fd in self.transferring) and (message == 'retrc' or
                                                                message == 'storc'):
                        self.transferring.remove(fd)
                        self.messages[fd] = status.transfer_complete
                        try:
                            self.cmd_epoll.modify(fd, select.EPOLLET | select.EPOLLOUT)
                        except:
                            pass
                    else:
                        result = self.extract(message)
                        if result is not None:
                            command, addition = result
                            if command in self.func_key:
                                self.messages[fd] = self.func_key[command](addition, fd)
                            else:
                                self.messages[fd] = status.command_error
                        else:
                            self.messages[fd] = status.command_error
                        # todo complete this block
                        try:
                            self.cmd_epoll.modify(fd, select.EPOLLET | select.EPOLLOUT)
                        except:
                            pass

                # writing event
                elif events & select.EPOLLOUT:
                    self.write(self.connections[fd], self.messages[fd])
                    self.cmd_epoll.modify(fd, select.EPOLLET | select.EPOLLIN)
                else:
                    continue
