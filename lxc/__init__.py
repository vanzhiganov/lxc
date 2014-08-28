import subprocess
import logging
import threading
import select
import pty
import os
import signal


class ContainerAlreadyExists(Exception):
    pass


class ContainerAlreadyRunning(Exception):
    pass


class ContainerNotExists(Exception):
    pass


class lxc():
    def __init__(self):
        logging.debug("")

    def list(self, status=None):
        """
        :return: ['container_first', 'container_second']
        """
        if status in ['active', 'frozen', 'running', 'stopped', 'nesting']:
            path = "--%s" % status
        else:
            path = ""

        cmd = ['lxc-ls', path]
        out = subprocess.check_output(cmd).splitlines()
        # print out
        return out

    def exists(self, name):
        """
        checks if a given container is defined or not
        """
        if name in self.list():
            return True
        return False

    def start(self, name, config_file=None):
        """
        starts a container in daemon mode
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)

        if name in self.list("running"):
            raise ContainerAlreadyRunning('The container %s is already started!' % name)

        cmd = ['lxc-start', '-n', name, '-d']
        if config_file:
            cmd += ['-f', config_file]

        return subprocess.check_call(cmd)

    def stop(self, name):
        """
        stops a container
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)

        cmd = ['lxc-stop', '-n', name]

        return subprocess.check_call(cmd)

    def destroy(self, name):
        """
        removes a container [stops a container if it's running and]
        raises ContainerNotExists exception if the specified name is not created
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)

        # todo: check status. If status not STOPPED - run method self.stop(name)
        # todo: add condition
        self.stop(name)

        cmd = ['lxc-destroy', '-f', '-n', name]

        return subprocess.check_call(cmd)

    def info(self, name):
        """
        returns info dict about the specified container
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)

        cmd = ['lxc-info', '-n', name, "-H"]
        out = subprocess.check_output(cmd).splitlines()
        clean = []
        info = {}

        for line in out:
            # print line
            if line not in clean:
                clean.append(line)

        for line in clean:
            key, value = line.split(":")

            # strip
            key = key.lstrip()
            value = value.lstrip()

            key = key.replace(" ", "_")

            info[key.lower()] = value

        return info

    def freeze(self, name):
        """
        freezes the container
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)
        cmd = ['lxc-freeze', '-n', name]
        subprocess.check_call(cmd)

    def unfreeze(self, name):
        """
        unfreezes the container
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)
        cmd = ['lxc-unfreeze', '-n', name]
        subprocess.check_call(cmd)

    def notify(self, name, states, callback):
        """
        executes the callback function with no parameters when the container reaches the specified state or states
        states can be or-ed or and-ed
            notify('test', 'STOPPED', letmeknow)

            notify('test', 'STOPPED|RUNNING', letmeknow)
        """
        if not self.exists(name):
            raise ContainerNotExists("The container (%s) does not exist!" % name)

        cmd = ['lxc-wait', '-n', name, '-s', states]
        def th():
            subprocess.check_call(cmd)
            callback()
        _logger.info("Waiting on states %s for container %s", states, name)
        threading.Thread(target=th).start()

    def checkconfig(self):
        """
        returns the output of lxc-checkconfig
        """
        cmd = ['lxc-checkconfig']
        return subprocess.check_output(cmd).replace('[1;32m', '').replace('[1;33m', '').replace('[0;39m', '').replace('[1;32m', '').replace(' ', '').split('\n')

    def create(self, name, config_file=None, template=None, backing_store=None, template_options=None):
        """
        Create a new container
        raises ContainerAlreadyExists exception if the container name is reserved already.

        :param template_options: Options passed to the specified template
        :type template_options: list or None
        """
        if self.exists(name):
            raise ContainerAlreadyExists("The Container %s is already created!" % name)
        cmd = 'lxc-create -n %s' % name

        if config_file:
            cmd += ' -f %s' % config_file
        if template:
            cmd += ' -t %s' % template
        if backing_store:
            cmd += ' -B %s' % backing_store
        if template_options:
            cmd += '-- %s' % template_options

        if subprocess.check_call('%s >> /dev/null' % cmd, shell=True) == 0:
            if not self.exists(name):
                _logger.critical("The Container %s doesn't seem to be created! (options: %s)", name, cmd[3:])
                raise ContainerNotExists("The container (%s) does not exist!" % name)

            _logger.info("Container %s has been created with options %s", name, cmd[3:])
            return False
        else:
            return True

    def reset_password(self, container_name, username, password):
        call = [
            'echo "%s:${PASSWORD:-%s}" | chroot /var/lib/lxc/%s/rootfs/ chpasswd' % (username, password, container_name)
        ]
        subprocess.check_call(call)
        return True
