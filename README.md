# keepalived_rbd_nfs

## 環境

|                  | Version          |
|------------------|------------------|
| Ceph             | 10.2.9 (Jewel)   |
| OS               | CentOS 7         | 

| Hostname          | IP                | Role                |
| ------------------| ----------------- | --------------------|
| ceph-client-1     | 192.168.15.31     | Keepalived Node     |
| ceph-client-2     | 192.168.15.32     | Keepalived Node     |

## 安裝

* 在 /etc/ceph/ceph.conf 設定 RBD 預設 feature

```
rbd default features = 1
```

* 新增 RBD Image (需要 Ceph admin 權限)

```
rbd create test --size 1G
```

* 確認 RBD Features

```
[root@ceph-admin vagrant]# rbd info test
rbd image 'test':
    size 1024 MB in   256 objects
    order 22   (4096 kB objects)
    block_name_prefix: rbd_data.10212ae8944a
    format: 2
    features: layering
    flags:
```

* 將 RBD Image 格式化為 XFS

```
rbd map test
mkfs.xfs /dev/rbd<x>
rbd unmap test
```

* 安裝 Keepalived 和 nfs server

```
sudo apt-get install keepalived nfs-kernel-server -y
```

* 確認 /etc/ceph 底下有 ceph.conf 和 admin keyring

```
$ ls -l /etc/ceph/
total 12
-rw------- 1 root root 129 Sep 19 11:41 ceph.client.admin.keyring
-rw-r--r-- 1 root root 253 Sep 19 11:41 ceph.conf
-rw-r--r-- 1 root root  92 Jul 13 16:38 rbdmap
-rw------- 1 root root   0 Sep 19 11:41 tmpiMLgCG
```

* 把 ha.py, keepalived.conf 和 repo.ini 放到 ceph-client-1 和 ceph-client-2 的 /etc/keepalived 資料夾下

```
$ ls -l /etc/keepalived/
total 16
-rwxr-xr-x 1 root root 6803 Sep 19 10:15 ha.py
-rw-r--r-- 1 root root  460 Sep 19 06:39 keepalived.conf
-rw-r--r-- 1 root root  320 Sep 19 10:05 repo.ini
```

* 啟動 Keepalived

```
systemctl start keepalived
```

* Log 會寫在 /var/log/keepalived

```
$ cat /var/log/keepalived 
[2017-09-19 10:36:44][INFO ] Change to backup state...
[2017-09-19 10:36:44][INFO ] Stopping NFS server...
[2017-09-19 10:36:44][INFO ] NFS server is stopped
[2017-09-19 10:36:44][INFO ] Starting to disable repos...
[2017-09-19 10:36:49][INFO ] Removing NFS export /gg
[2017-09-19 10:36:49][INFO ] NFS export /gg has been removed
[2017-09-19 10:36:49][INFO ] Mount point /gg is not mount, skip umount
[2017-09-19 10:36:49][ERROR] Unmap test4 failed: image is not exists
[2017-09-19 10:36:49][INFO ] Removing NFS export /mnt
[2017-09-19 10:36:49][INFO ] NFS export /mnt has been removed
[2017-09-19 10:36:49][INFO ] Mount point /mnt is not mount, skip umount
[2017-09-19 10:36:49][INFO ] RBD image test2 is not mapped, skip unmap
[2017-09-19 10:36:49][INFO ] Removing NFS export /ccc
[2017-09-19 10:36:49][INFO ] NFS export /ccc has been removed
[2017-09-19 10:36:49][INFO ] Mount point /ccc is not mount, skip umount
[2017-09-19 10:36:49][INFO ] RBD image test is not mapped, skip unmap
[2017-09-19 10:36:49][INFO ] Change to backup state done
```
