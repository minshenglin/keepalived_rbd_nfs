#!/usr/bin/env python

import os
import time
import sys
import logging
import subprocess
import ConfigParser
import json

config_path = '/etc/keepalived/repo.ini'

log_path = '/var/log/keepalived'
logging.basicConfig(level=logging.INFO, filename=log_path,
    format='[%(asctime)s][%(levelname)-5s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

class RepoSetting(object):
    def __init__(self, image=None, path=None, nfs_cidr=None, nfs_option=None):
        self.image = image
        self.path = path
        self.nfs_cidr = nfs_cidr
        self.nfs_option = nfs_option

def start_nfs_server():
    logging.info('Starting NFS server...')
    try:  
        subprocess.check_call(["/bin/systemctl", "restart", "nfs-server"])
    except Exception as e:
        logging.error("Start NFS server failed: %s", e)
        sys.exit(1)

    logging.info('NFS server is running')

def stop_nfs_server():
    logging.info('Stopping NFS server...')
    try:  
        subprocess.check_call(["/bin/systemctl", "stop", "nfs-server"])
    except Exception as e:
        logging.error("Stop NFS server failed: %s", e)
        sys.exit(1)

    logging.info('NFS server is stopped')

def enable_repos():
    logging.info("Starting to enable repos...")

    mapped_images = get_mapped_images()
    config = ConfigParser.ConfigParser()
    config.read(config_path)

    for repo_name in config.sections():
        setting = load_repo_setting(config, repo_name)
        device = mapping(mapped_images, setting.image)
        if device is None:
            continue
        if not mount(device, setting.path):
            continue
        add_export(setting)
 
def disable_repos():
    logging.info("Starting to disable repos...")

    mapped_images = get_mapped_images()

    config = ConfigParser.ConfigParser()
    config.read(config_path)
    for repo_name in config.sections():
        setting = load_repo_setting(config, repo_name)
        remove_export(setting)

        if not umount(setting.path):
            continue
        if not unmapping(mapped_images, setting.image):
            continue

def load_repo_setting(config, name):
    s = dict(config.items(name))
  
    return RepoSetting(image=s["image"], 
                       path=s["path"], 
                       nfs_cidr=s["nfs_cidr"], 
                       nfs_option=s["nfs_option"])

def get_mapped_images():
    images = dict()
    out = subprocess.check_output(["/usr/bin/rbd", "showmapped", "--format", "json"])
    content = json.loads(out)
    for key in content:
        name = content[key]["name"]
        device = content[key]["device"]
        images[name] = device
         
    return images

def is_formatted(device):
    output = None
    try:
        output = subprocess.check_output(["/usr/bin/lsblk", "--output", "FSTYPE", "-n", "-f", device])
    except Exception as e:
        logging.error("Check the filesystem of %s failed: %s", device, e)
        return False

    fs = output.strip()
    if fs == "":
        logging.error("Device %s is unformatted", device)
        return False

    return True

def mount(device, path):
    if os.path.ismount(path):
        logging.info('Mount point %s is mount, skip mount', path)
        return True

    if not is_formatted(device):
        return False

    logging.info('Mount %s to %s', device, path)
    try:  
        rc = subprocess.check_call(["/bin/mount", device , path])
    except Exception as e:
        logging.error("Mount to %s failed: %s", path ,e)
        return False

    logging.info('Device %s is mounted to %s', device, path)
    return True

def umount(path):
    if not os.path.ismount(path):
        logging.info('Mount point %s is not mount, skip umount', path)
        return True
   
    logging.info('Umount %s', path)
    rc = subprocess.check_call(["/usr/sbin/fuser", "-ksm",  path]) # evict user from mount point

    try:  
        rc = subprocess.check_call(["/bin/umount", "-l" , path])
    except Exception as e:
        logging.error("Umount %s failed: %s", path ,e)
        return False

    logging.info('Mount point %s is unmounted', path)
    return True

def is_image_exists(image):
     out = subprocess.check_output(["/usr/bin/rbd", "ls", "--format", "json"])
     content = json.loads(out)
     for key in content:
         if image == key:
             return True

     return False

def mapping(mapped_images, image):
     if not is_image_exists(image):
        logging.error("Map %s failed: image is not exists", image)
        return None

     if image in mapped_images.keys():
        logging.info('RBD image %s is mapped, skip mapping', image)
        return mapped_images[image]

     logging.info('Map RBD image %s', image)
     try:  
        device = subprocess.check_output(["/usr/bin/rbd", "map" , image]).strip()
     except Exception as e:
        logging.error("Map image %s failed: %s", image ,e)
        return None

     logging.info('RBD image %s is mapped on %s', image, device) 
     return device

def unmapping(mapped_images, image):
     if not is_image_exists(image):
        logging.error("Unmap %s failed: image is not exists", image)
        return False
     
     if image not in mapped_images.keys():
        logging.info('RBD image %s is not mapped, skip unmap', image)
        return True

     logging.info('Unmap RBD image %s', image)
     try:  
        rc = subprocess.check_call(["/usr/bin/rbd", "unmap" , image])
     except Exception as e:
        logging.error("Unmap image %s failed: %s", image ,e)
        return False

     logging.info('RBD image %s is unmapped', image)
     return True

def add_export(setting):
     logging.info('Adding NFS export %s', setting.path)
     export = "%s %s(%s)" % (setting.path, setting.nfs_cidr, setting.nfs_option)
     lines = None
     with open('/etc/exports', 'r') as f:
         lines = f.readlines()

     for line in lines:
         if export in line:
             logging.info('NFS export %s has been added, skip', setting.path)
             return

     with open('/etc/exports', 'a') as f:
         f.write(export + '\n')

     logging.info('NFS export %s is added', setting.path)

def remove_export(setting):
     logging.info('Removing NFS export %s', setting.path)
     lines = None
     with open('/etc/exports', 'r') as f:
         lines = f.readlines()

     export = "%s %s(%s)" % (setting.path, setting.nfs_cidr, setting.nfs_option)
     with open('/etc/exports', 'w') as f:
         for line in lines:
             if export in line:
                 continue
             f.write(line.strip() + '\n')

     
     logging.info('NFS export %s has been removed', setting.path)


def has_previous_process(program_name):
    pid = os.getpid()
    output = subprocess.check_output(["/usr/bin/pgrep", "-a", "python"])
    for line in output.split('\n'):
        if str(pid) not in line and program_name in line:
            return True

    return False

def wait_previous_process_done(program_name):
    counter = 60
    while(counter > 0):
        if not has_previous_process(program_name):
            return
        counter -= 1
        time.sleep(1)

    logging.error('Previous process is not over after 60 seconds')
    sys.exit(1)

if __name__ == '__main__':

    if len(sys.argv) < 2:
        print "Usage: %s group state (master/backup/stop/fault)" % sys.argv[0] 
        sys.exit(1)

    if os.geteuid() != 0:
        print "Permission denied, you need to change root or use sudo"
        sys.exit(1)

    wait_previous_process_done(sys.argv[0])

    state = sys.argv[1].lower() 
    logging.info('Change to %s state...' % state)

    if state == 'master':
        enable_repos()
        start_nfs_server()

    if state == 'backup' or state == 'stop':
        stop_nfs_server()
        disable_repos()

    if state == 'fault':
        stop_nfs_server()

    logging.info('Change to %s state done' % state)
    sys.exit(0)
