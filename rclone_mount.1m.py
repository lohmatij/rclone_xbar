#!/usr/bin/env PYTHONIOENCODING=UTF-8 /usr/bin/python3

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

# Metadata allows your plugin to show up in the app, and website.
#
#  <xbar.title>rclone mount</xbar.title>
#  <xbar.version>v0.1</xbar.version>
#  <xbar.author>Andrey Valentsov</xbar.author>
#  <xbar.author.github>lohmatij</xbar.author.github>
#  <xbar.desc>Mount rclone-remotes</xbar.desc>
#  <xbar.image>http://www.hosted-somewhere/pluginimage</xbar.image>
#  <xbar.dependencies>python,rclone, macfuse</xbar.dependencies>
#  <xbar.abouturl>https://github.com/lohmatij/rclone_xbar/</xbar.abouturl>

# Variables become preferences in the app:
#
#  <xbar.var>string(VAR_MOUNT_PATH="~/clouds"): Default path for mounts.</xbar.var>
#  <xbar.var>number(VAR_REMOTE_PORT=5575): Custom port for remote control of rclone, in case rclone remote is already running on standart port</xbar.var>
#  <xbar.var>select(VAR_CACHE_MODE="full"): Cashing level for mounted filesystem.https://rclone.org/commands/rclone_mount/#vfs-file-caching [off, minimal, writes, full]</xbar.var>
#  <xbar.var>boolean(VAR_VERBOSE=true): Whether to be verbose or not. (not implemented.</xbar.var>

DEFAULT_MOUNT_PATH = "~/clouds"
DEFAULT_REMOTE_PORT = 5575  # custom port in case rclone remote is already started
CACHE_MODE = 'full'  # Cashing level for mounted filesystem. https://rclone.org/commands/rclone_mount/#vfs-file-caching

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def add_line_to_xbar(text, submenu=0, **keys):
    line_output = submenu * "--" + text
    for key, value in keys.items():
        line_output += f' | {key}="{value}"'
    print(line_output)


class Remote:
    def __init__(self, name):
        self.name = name
        self.volume = str()  # Volume name of mounted remote
        self.mount_path = Path()
        self.type = str()
        self.is_mounted = False


class Remotes(dict):
    # example usage: ['dropbox'].volume = "Dropbox Home"
    pass


class Rclone:

    @staticmethod
    def check_dependencies():
        if shutil.which('rclone') is None:
            print('Rclone is not installed.')
            exit()

    def __init__(self):
        self.mounted_remotes = None
        self.active = None
        self.speed = None
        os.environ['PATH'] += ':/usr/local/bin'
        self.check_dependencies()

    def __enter__(self):
        self.default_path = Path(
            os.environ['VAR_MOUNT_PATH'] if 'VAR_MOUNT_PATH' in os.environ else DEFAULT_MOUNT_PATH).expanduser()
        self.default_path.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(['rclone', 'rcd', '--rc-no-auth', f'--rc-addr=localhost:{DEFAULT_REMOTE_PORT}'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    def mounted_remotes_list():

        rclone_list_of_mounts_output = subprocess.run(
            ['rclone',
             'rc',
             'vfs/list',
             f'--url=localhost:{DEFAULT_REMOTE_PORT}'],
            capture_output=True)
        rclone_list_of_mounts = json.loads(rclone_list_of_mounts_output.stdout)
        return rclone_list_of_mounts['vfses']

    def check_status(self):
        self.mounted_remotes = self.mounted_remotes_list()

        rclone_stats_output = subprocess.run(['rclone', 'rc', 'core/stats', f'--url=localhost:{DEFAULT_REMOTE_PORT}'],
            capture_output=True)
        rclone_stats = json.loads(rclone_stats_output.stdout)

        self.active = True if len(self.mounted_remotes) > 0 else False

        self.speed = rclone_stats['speed']

    def get_config(self) -> Remotes:

        rclone_config_output = subprocess.run(
            ['rclone',
             'rc',
             'config/dump',
             f'--url=localhost:{DEFAULT_REMOTE_PORT}'],
            capture_output=True)
        rclone_config = json.loads(rclone_config_output.stdout)

        mounted_remotes_list = self.mounted_remotes_list()
        # mounted_remotes = self.mounted_remotes

        remotes = Remotes()
        for name, settings in rclone_config.items():
            if settings['type'] == 'local':
                continue

            remotes[name] = Remote(name)
            remotes[name].volume = settings['volume_name'] if 'volume_name' in settings else name
            remotes[name].mount_path = self.default_path.joinpath(name)

            remotes[name].is_mounted = (name + ":") in mounted_remotes_list
        return remotes

    @staticmethod
    def get_unmount_command(remote):
        cmd = dict()
        cmd['shell'] = os.path.abspath(__file__)  # run same script reversely
        cmd['param1'] = 'unmount'
        cmd['param2'] = remote.mount_path
        cmd['refresh'] = 'true'
        return cmd

    @staticmethod
    def get_mount_command(remote: Remote):
        cmd = dict()
        cmd['shell'] = os.path.abspath(__file__)  # run same script reversely
        cmd['param1'] = 'mount'
        cmd['param2'] = remote.name
        cmd['param3'] = remote.mount_path
        cmd['param4'] = remote.volume
        cmd['refresh'] = 'true'
        return cmd


def notify(title, text):
    os.system("""
              osascript -e 'display alert "{}" message "{}"'
              """.format(title, text))


def mount(remote_name, mount_path, volume_name):
    os.environ['PATH'] += ':/usr/local/bin'

    mount_path = Path(mount_path)
    mount_path.mkdir(exist_ok=True)
    vfs_opt = 'vfsOpt={"CacheMode": "%s"}' % CACHE_MODE
    mount_opt = 'mountOpt={"VolumeName": "%s"}' % volume_name

    subprocess.run(['rclone',
                    'rc',
                    'mount/mount',
                    f'--url=localhost:{DEFAULT_REMOTE_PORT}',
                    f'fs={remote_name}:',
                    f'mountPoint={mount_path}',
                    vfs_opt,
                    mount_opt, ])


def unmount(mount_path):
    os.environ['PATH'] += ':/usr/local/bin'

    subprocess.run(
        ['rclone',
         'rc',
         'mount/unmount',
         f'--url=localhost:{DEFAULT_REMOTE_PORT}',
         f'mountPoint={mount_path}'])
    os.rmdir(mount_path)


if __name__ == '__main__':

    if len(sys.argv) > 1:
        if sys.argv[1] == 'mount':
            mount(*sys.argv[2:])
            pass
        if sys.argv[1] == 'unmount':
            unmount(*sys.argv[2:])
            pass
        exit()

    with Rclone() as rclone:

        remotes = rclone.get_config()
        add_line_to_xbar(f"{len(remotes)} remotes")
        add_line_to_xbar("---")
        for remote in remotes.values():
            if remote.is_mounted:
                # add_line_to_xbar(remote.status)
                add_line_to_xbar(f"Open {remote.volume}", shell=f"open", param1=remote.mount_path, refresh=False)
                """for file in remote.active_files:
                    add_line_to_xbar(file.name, submenu=1)
                    add_line_to_xbar(file.name, submenu=1)  # percentage, speed, eta"""

                unmount_command = rclone.get_unmount_command(remote)
                add_line_to_xbar(f'Unmount {remote.volume}', alternate=True, **unmount_command)
            else:
                mount_command = rclone.get_mount_command(remote)
                add_line_to_xbar(f'Mount {remote.volume}',
                                 **mount_command)
                #add_line_to_xbar(f'Rename {remote.volume}', alternate=True, rclone.get_rename_command)