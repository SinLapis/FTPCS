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

        self.exit_flag = False
        self.MAX_CONN = 1
        self.conn_count = 0
        self.ban_mode = False
        self.is_black_list = False

        self.func_key = {
            'user': self.user,
            'pass': self.pw,
            'list': self.ls,
            'size': self.size,
            'retr': self.retr,
            'stor': self.stor,
        }
        self.user_info = {
            'admin': 'admin',
        }
        self.black_list = []
        self.white_list = []

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
            try:
                file = open(self.work_path[fd] + filename, 'rb')
                threading.Thread(target=self.retr_transfer,
                                 args=(file, data_sock,)).start()
                port = '(' + str(port) + ')'
                message = status.transfer_ready + port
            except FileNotFoundError:
                message = status.unavailable_file
        else:
            message = status.need_account
        return message

    def retr_transfer(self, file, data_sock):

        data_sock.listen(1)
        data_fd, addr = data_sock.accept()
        buf = file.read(1024)
        while len(buf) != 0:
            data_fd.send(buf)
            buf = file.read(1024)
        file.close()
        data_fd.close()
        data_sock.close()

    def stor(self, full_path, fd):
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
            store_path = self.work_path[fd] + os.path.basename(full_path)
            file = open(store_path, 'wb')
            threading.Thread(target=self.stor_transfer,
                             args=(file, data_sock,)).start()
            port = '(' + str(port) + ')'
            message = status.transfer_ready + port
        else:
            message = status.need_account
        return message

    def stor_transfer(self, file, data_sock):
        data_sock.listen(1)
        data_fd, addr = data_sock.accept()
        while True:
            buf = data_fd.recv(1024)
            if len(buf) != 0:
                file.write(buf)
            else:
                break
        file.close()
        data_fd.close()
        data_sock.close()

    def delete(self, fd):
        try:
            del self.login_info[fd]
        except KeyError:
            pass
        try:
            del self.messages[fd]
        except KeyError:
            pass
        try:
            del self.connections[fd]
        except KeyError:
            pass
        try:
            del self.work_path[fd]
        except KeyError:
            pass
        try:
            del self.addresses[fd]
        except KeyError:
            pass
        try:
            self.need_username.remove(fd)
        except KeyError:
            pass
        try:
            self.need_password.remove(fd)
        except KeyError:
            pass
        try:
            self.logged_in.remove(fd)
        except KeyError:
            pass
        self.conn_count -= 1

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

    def console(self):
        server_thread = threading.Thread(target=self.start)
        server_thread.daemon = True
        server_thread.start()
        while True:
            command = input()
            if command == 'clients':
                print('<status>')
                for fd in self.addresses:
                    print(str(self.addresses[fd]))
            elif command == 'exit':
                print('<status> Close the server.')
                self.exit_flag = True
                return 0
            elif command[0:3] == 'max':
                try:
                    self.max_conn = int(command[4:])
                except ValueError:
                    print('<console> Addition error.')
            elif command[0:4] == 'mode':
                choice = command[5:]
                if choice == 'black':
                    self.ban_mode = True
                    self.is_black_list = True
                elif choice == 'white':
                    self.ban_mode = True
                elif choice == 'none':
                    self.ban_mode = False
                else:
                    print('<console> Addition error.')

            else:
                print('<status> There is no command like \'' + command + '\'.')

    def start(self):
        while not self.exit_flag:
            epoll_list = self.cmd_epoll.poll()
            for fd, events in epoll_list:
                # connection event
                if fd == self.cmd_socket.fileno():
                    connection, address = self.cmd_socket.accept()
                    connection.setblocking(0)
                    in_black_list = address[0] in self.black_list
                    in_white_list = address[0] in self.white_list
                    banned_flag = (self.ban_mode and
                                   (self.is_black_list and in_black_list) or
                                   ((not self.is_black_list) and in_white_list))
                    if self.conn_count < self.MAX_CONN and not banned_flag:
                        self.write(connection, status.welcome)
                        self.cmd_epoll.register(connection.fileno(),
                                                select.EPOLLIN | select.EPOLLET)
                        self.connections[connection.fileno()] = connection
                        self.addresses[connection.fileno()] = address
                        self.need_username.add(connection.fileno())
                        print('<server> ' + str(address) + ' connected')
                        self.conn_count += 1
                    else:
                        connection.send(status.deny_service.encode())
                        connection.close()
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
                    elif fd in self.transferring and (message == 'retrc' or
                                                              message == 'storc'):
                        self.transferring.remove(fd)
                        self.messages[fd] = status.transfer_complete
                        try:
                            self.cmd_epoll.modify(fd, select.EPOLLET |
                                                  select.EPOLLOUT)
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
