# ovirt-vm-hot-backup

Requires Python oVirt SDK
-------------------------

You can install it via easy_install: 

    easy_install ovirt-engine-sdk-python


Operation
---------

oVirt is not able to hot backup a vm out of the box but it can be achieved with the following steps:

1. Create a snapshot of the VM
2. Clone the snapshot in a new VM
3. Optionally delete Snapshot (oVirt >= 3.6)
4. Export new cloned VM
5. Optionally delete the clone

The script automates this procedures for every VM listed in the configuration file.

It also deletes old exports keeping a configurable number of last exports.
