#!/usr/bin/python

import sys
import time
import datetime
import re
import ConfigParser
import os
from operator import attrgetter

scriptdir = os.path.abspath(os.path.dirname(sys.argv[0]))
conffile = scriptdir + "/ovirt-vm-rolling-snapshot.conf"

Config = ConfigParser.ConfigParser()

if not os.path.isfile(conffile):
    print "Config file %s does not exists. Exiting." % conffile
    sys.exit(1)

Config.read(conffile)

if len(Config.sections()) < 1:
    print "Config file is not valid. Exiting."
    sys.exit(1)

basetime = datetime.datetime.now()

for vmname in Config.sections():

    starttime = time.time()

    try:

        etime_to_keep = int(Config.get(vmname, 'etime_to_keep'))
        hourly_to_keep = int(Config.get(vmname, 'hourly_to_keep'))
        daily_to_keep = int(Config.get(vmname, 'daily_to_keep'))
        weekly_to_keep = int(Config.get(vmname, 'weekly_to_keep'))
        monthly_to_keep = int(Config.get(vmname, 'monthly_to_keep'))

        time_hours = "%02d" % int(Config.get(vmname, 'time_hours'))
        time_minutes = "%02d" % int(Config.get(vmname, 'time_minutes'))
        time_weekday = "%d" % int(Config.get(vmname, 'time_weekday'))
        time_monthweek = int(Config.get(vmname, 'time_monthweek'))

        if time_monthweek < 1 or time_monthweek > 5:
            time_monthweek = 1

        if time_weekday == "7":
            time_weekday = "0"

        last_to_keep = {"____": etime_to_keep, "H___": hourly_to_keep, "HD__": daily_to_keep, "HDW_": weekly_to_keep,
                        "HDWM": monthly_to_keep}

        hpos = dpos = wpos = mpos = "_"

        if basetime.strftime("%M") == time_minutes:  # minutes is 00
            hpos = "H"

            if basetime.strftime("%H") == time_hours:  # hour is 00
                dpos = "D"

                if basetime.strftime("%w") == time_weekday:  # day of week is sunday
                    wpos = "W"

                    if (int(basetime.strftime("%d")) <= (7 * time_monthweek)) and (
                        int(basetime.strftime("%d")) > (7 * (time_monthweek - 1))):  # is the first week of month
                        mpos = "M"

        snap_time_id = hpos + dpos + wpos + mpos

        deleteonly = ''
        if len(sys.argv) > 1:
            snap_time_id = sys.argv[1]
            if not last_to_keep[snap_time_id]:
                last_to_keep[snap_time_id] = 1
            if len(sys.argv) > 2:
                deleteonly = sys.argv[2]

        if last_to_keep[snap_time_id]:

            print
            print "------------------------------------------------------------"
            print "VM name: " + vmname

            try:
                ovirtsdk
            except:
                import ovirtsdk.api
                from ovirtsdk.xml import params

            api = ovirtsdk.api.API(
                url=Config.get(vmname, 'server'),
                username=Config.get(vmname, 'username'),
                password=Config.get(vmname, 'password'),
                insecure=True,
                debug=False
            )

            vm = api.vms.get(vmname)

            print "Begin backup of VM '%s' at %s" % (vmname, datetime.datetime.now().isoformat(" "))
            print "VM status: %s" % str(vm.get_status().state)

            if deleteonly == 'deleteonly':

                print "Skipping snapshot creation."

            else:

                snap_description = "Rolling snapshot " + snap_time_id + " at " + datetime.datetime.now().isoformat(" ")
                print "Creating Snapshot '" + snap_description + "'"

                snapcreation = vm.snapshots.add(params.Snapshot(description=snap_description))

                snaptoclone = ""
                snap_status = ""
                sys.stdout.write( "Snapshot in progress..." )
                sys.stdout.flush()
                while True:
                    snaptoclone = vm.snapshots.get(id=snapcreation.get_id())
                    snap_status = snaptoclone.get_snapshot_status()
                    if snap_status == "locked":
                        time.sleep(5)
                        sys.stdout.write('.')
                        sys.stdout.flush()

                    else:
                        print
                        break

                for snapi in vm.get_snapshots().list():
                    snapi_id = snapi.get_id()
                    if vm.snapshots.get(id=snapi_id).description == snap_description:
                        snap_status = "ok"
                        break
                    else:
                        snap_status = "error"

                if snap_status != "ok":
                    print "Snapshot creation ERROR!!!"
                    continue

                print "Snapshot done"
                time.sleep(1)

                snapshots_param = params.Snapshots(snapshot=[params.Snapshot(id=snaptoclone.get_id())])


            snaptodel = []
            for snapi in vm.get_snapshots().list():
                snapi_id = snapi.get_id()
                snapi_descr = vm.snapshots.get(id=snapi_id).description
                snapi_time_match = re.match('^Rolling snapshot ' + snap_time_id + ' at', snapi_descr)
                if snapi_time_match:
                    snaptodel.append(snapi)
            snaptodel = sorted(snaptodel, key=attrgetter('creation_time'))

            if last_to_keep[snap_time_id] > 0:
                del snaptodel[-last_to_keep[snap_time_id]:]

            for snapitodel in snaptodel:
                print "Deleting old snapshot '" + snapitodel.description + "'"

                snapitodel.delete(async=False)

                oldsndelstatus = sndelstatus = ''
                while True:

                    try:
                        sndelstatus = vm.snapshots.get(id=snapitodel.get_id()).get_snapshot_status()
                    except Exception, e:
                        break

                    if sndelstatus == oldsndelstatus:
                        sys.stdout.write('.')
                    else:
                        if sndelstatus == 'ok':
                            break
                        sys.stdout.write( "Delete snapshot in progress..." )
                        oldsndelstatus = sndelstatus

                    sys.stdout.flush()
                    time.sleep(5)

                print
                if sndelstatus == 'ok':
                    print "Delete snapshot ERROR!!!"
                else:
                    print "Delete snapshot done."

            eltime = time.time() - starttime
            print "Finished backup of VM '%s' at %s. %d seconds." % (vmname,
                                                                     datetime.datetime.now().isoformat(" "),
                                                                     eltime)
            print

    except Exception, e:
        print e
        print "Backup ERROR!!!"
