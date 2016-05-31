#!/usr/bin/python

import sys
import ovirtsdk.api
import time
import datetime
import re
from ovirtsdk.xml import params
import ConfigParser
import os
from operator import attrgetter

scriptdir = os.path.abspath(os.path.dirname(sys.argv[0]))
conffile  = scriptdir + "/ovirt-vm-rolling-snapshot.conf"

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

        etime_to_keep   = int(Config.get(vmname, 'etime_to_keep'))
        hourly_to_keep  = int(Config.get(vmname, 'hourly_to_keep'))
        daily_to_keep   = int(Config.get(vmname, 'daily_to_keep'))
        weekly_to_keep  = int(Config.get(vmname, 'weekly_to_keep'))
        monthly_to_keep = int(Config.get(vmname, 'monthly_to_keep'))

        time_hours      = "%02d" % int(Config.get(vmname, 'time_hours'))
        time_minutes    = "%02d" % int(Config.get(vmname, 'time_minutes'))
        time_weekday    = "%d"   % int(Config.get(vmname, 'time_weekday'))
        time_monthweek  = int(Config.get(vmname, 'time_monthweek'))

        if time_monthweek < 1 or time_monthweek > 5:
            time_monthweek = 1

        if time_weekday == "7":
            time_weekday = "0"

        last_to_keep = { "____":etime_to_keep, "H___":hourly_to_keep, "HD__":daily_to_keep, "HDW_":weekly_to_keep, "HDWM":monthly_to_keep }

        print "%s %s %s %s" % ( time_minutes, time_hours, time_weekday, time_monthweek )
        print time.strftime("%M %H %w %d")

        hpos = dpos = wpos = mpos = "_"

        if time.strftime("%M") == time_minutes: # minutes is 00
            hpos = "H"

            if time.strftime("%H") == time_hours: # hour is 00
                dpos = "D"

                if time.strftime("%w") == time_weekday: # day of week is sunday
                    wpos = "W"

                    if int( time.strftime("%d") ) <= ( 7 * time_monthweek ) and \
                       int( time.strftime("%d") ) > ( 7 * ( time_monthweek - 1 ) ): # is the first week of month
                        mpos = "M"


        snap_time_id = hpos + dpos + wpos + mpos

        snap_description = "Rolling snapshot " + snap_time_id + " at " + datetime.datetime.now().isoformat(" ")

        vm = api.vms.get(vmname)

        print ""
        print "VM name: " + vm.get_name()
        print "Begin backup of VM '%s' at %s" % ( vmname, datetime.datetime.now().isoformat(" ") )
        print "VM status: %s" % str( vm.get_status().state )

        if last_to_keep[snap_time_id]:

            print "Creating Snapshot " + snap_description

            snapcreation = vm.snapshots.add( params.Snapshot(description=snap_description) )

            snaptoclone = ""
            snap_status = ""
            while True:
                time.sleep(5)
                snaptoclone = vm.snapshots.get(id=snapcreation.get_id())
                snap_status = snaptoclone.get_snapshot_status()
                if snap_status != "locked":
                    break
                #print "Snapshot in progress (" + snap_status + ") ..."

            if snap_status != "ok":
                print "Snapshot creation failed. Status: " + snap_status
                sys.exit(1)

            print "Snapshot done"
            time.sleep(1)

            snapshots_param = params.Snapshots( snapshot=[params.Snapshot( id= snaptoclone.get_id())] )

        print "Launch delete snapshot..."
        snaptodel = []
        for snapi in vm.get_snapshots().list():
            snapi_id = snapi.get_id()
            snapi_descr = vm.snapshots.get(id=snapi_id).description
            snapi_time_match = re.match('^Rolling snapshot ' + snap_time_id + ' at', snapi_descr)
            if snapi_time_match:
                snaptodel.append( snapi )
        snaptodel = sorted(snaptodel, key=attrgetter('creation_time') )
        for snapitodel in snaptodel:
            print "Snapshot: " + snapitodel.description

        print

        if last_to_keep[snap_time_id] > 0:
            del snaptodel[-last_to_keep[snap_time_id]:]

        for snapitodel in snaptodel:
            print "Deleting snapshot " + snapitodel.description
            snapitodel.delete(async=False)
            while vm.snapshots.get(id=snapitodel.get_id()):
                time.sleep(5)
                #print "Snapshot in progress (" + snap_status + ") ..."
            print "Delete snapshot done"


    except Exception, e:
        print e
        print "Backup ERROR!!!"

    eltime = time.time() - starttime
    print "Finished backup of VM '%s' at %s. %d seconds." % ( vmname, datetime.datetime.now().isoformat(" "), eltime )

print ""
print "All done."

