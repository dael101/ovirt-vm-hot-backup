#!/usr/bin/python

import sys
import ovirtsdk.api
import time
import datetime
import re
from ovirtsdk.xml import params
import ConfigParser
import os

scriptdir = os.path.abspath(os.path.dirname(sys.argv[0]))
conffile  = scriptdir + "/ovirt-vm-hot-backup.conf"

Config = ConfigParser.ConfigParser()

if not os.path.isfile( conffile ):
    print "Config file %s does not exists. Exiting." % ( conffile )
    sys.exit(1)

Config.read( conffile )

if len( Config.sections() ) < 1:
    print "Config file is not valid. Exiting." 
    sys.exit(1)

for vmname in Config.sections():

    starttime = time.time()

    try:

        api = ovirtsdk.api.API(
                url=Config.get(vmname, 'server'),
                username=Config.get(vmname, 'username'),
                password=Config.get(vmname, 'password'),
                insecure=True,
                debug=False
        )
        export_domain = Config.get(vmname, 'export_domain')

        exporttokeep = int( Config.get(vmname, 'exports_to_keep') )
        if not exporttokeep > 0:
            exporttokeep = 1

        timestr = '_' + time.strftime("%y") + chr( 64 + int(time.strftime("%m")) ) + time.strftime("%d") + chr( 65 + int(time.strftime("%H") ))
        vmbkname = vmname[:8] + timestr

        snap_description = "Cloning to " + vmbkname

        vm = api.vms.get(vmname)

        print ""
        print "VM name:         " + vm.get_name()
        print "Exports to keep: " + str(exporttokeep)
        print "Export domain:   " + api.storagedomains.get(export_domain).get_name()
        print "Begin backup of VM '%s' at %s" % ( vmname, datetime.datetime.now().isoformat(" ") )
        print "VM status: %s" % str( vm.get_status().state )

        print "Creating Snapshot " + snap_description
        snapcreation = vm.snapshots.add( params.Snapshot(description=snap_description) )

        snaptoclone = ""
        snap_status = ""
        while True:
            time.sleep(3)
            snaptoclone = vm.snapshots.get(id=snapcreation.get_id())
            snap_status = snaptoclone.get_snapshot_status()
            if snap_status != "locked":
                break
            # print "Snapshot in progress (" + snap_status + ") ..."

        if snap_status != "ok":
            print "Snapshot creation failed. Status: " + snap_status
            sys.exit(1)

        print "Snapshot done"
        time.sleep(10)

        snapshots_param = params.Snapshots( snapshot=[params.Snapshot( id= snaptoclone.get_id())] )

        print "Creating Clone (%s)" % ( vmbkname )
        vmclone = api.vms.add(params.VM( name=vmbkname,
                                         memory=vm.get_memory(),
                                         cluster=vm.get_cluster(),
                                         snapshots=snapshots_param,
                                         delete_protected=False,
                                         # disks=params.Disks(clone=True),
                                        ))

        clone_status = ""
        while True:
            time.sleep(3)
            clone_status = str( api.vms.get(id=vmclone.get_id()).get_status().state )
            if clone_status != "image_locked":
                break
            # print "Clone in progress (" + clone_status + ")..."
        if clone_status != "down":
            print "Clone failed. Status: " + clone_status
            sys.exit(1)
        print "Clone done"
        time.sleep(10)

        print "Launch delete snapshot..."
        snaptoclone.delete(async=False)
        print "Delete snapshot done"
        time.sleep(10)

        print "Launch export..."
        vmclone.export(params.Action(exclusive=True,force=True,async=False,storage_domain=api.storagedomains.get( export_domain )))
        clone_status = ""
        while True:
            time.sleep(3)
            clone_status = str( api.vms.get(id=vmclone.get_id()).get_status().state )
            if clone_status != "image_locked":
                break
            # print "Export in progress (" + clone_status + ")..."
        if clone_status != "down":
            print "Export failed. Status: " + clone_status
            sys.exit(1)
        print "Export done"
        time.sleep(10)

        expstodel = []
        print "Purge old export"
        exported_vms = api.storagedomains.get(export_domain).vms.list()
        for i in exported_vms:
            expvmid = i.get_id()
            #print 'scanning ' + str( i.get_name() )
            if re.match('^'+vmname[:8]+'_\d\d[A-L]\d\d[A-Y]$', str( i.get_name() ) ):
                #print 'adding to delete ' + str( i.get_name() )
                expstodel.append( expvmid )

        expstodel.sort()
        del expstodel[-exporttokeep:]
        for expidtodel in expstodel:
            exptodel = api.storagedomains.get(export_domain).vms.get(id=expidtodel)
            print "Deleting export " + str( exptodel.get_name() ) + "..."
            exptodel.delete(async=False)
            print "Delete export done"

        print "Purge old export done"
        time.sleep(10)


        print "Launch delete clone..."
        vmclone.delete(async=False)
        print "Delete clone done"
        time.sleep(10)

        api.disconnect()

    except Exception, e:
        print e
        print "Backup ERROR!!!"

    eltime = time.time() - starttime
    print "Finished backup of VM '%s' at %s. %d seconds." % ( vmname, datetime.datetime.now().isoformat(" "), eltime )

print ""
print "All done."

