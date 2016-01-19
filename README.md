# ovirt-vm-hot-backup

## Requirement

#### Python oVirt SDK

You can install it via easy_install: 

    easy_install ovirt-engine-sdk-python


#### oVirt version >= 3.6

Required to delete temporary snapshot without shutting down the VM.



## Operation

oVirt is not able to hot backup a vm out of the box but it can be achieved with the following steps:

1. Create a snapshot of the VM
2. Clone the snapshot in a new VM
3. Delete cloned snapshot (oVirt >= 3.6)
4. Export new cloned VM
5. Delete the exported clone
6. Delete old exports

The script automates this procedures for every VM listed in the configuration file.

It also deletes old exports keeping a configurable number of last exports.
