# This is a script to claim a number of devices into Dashboard, create a network for them and bind 
#  the network to a pre-existing template. Optionally you can also claim a license key. Switch networks
#  must be eligible for auto-bind (Auto-bind is not valid unless the switch template has at least
#  one profile and has at most one profile per switch model.)
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python deploydevices.py -k <key> -o <org> -s <sn> -n <netw> -c <cfg_tmpl> [-t <tags>] [-a <addr>] [-m ignore_error]
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-07-05

import sys, getopt, requests, json

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

def printhelp():
    #prints help text

    printusertext('This is a script to claim MR, MS and MX devices into Dashboard, create a new network for them')
    printusertext(' and bind the network to a pre-existing template. The script can also claim license capacity.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext('python deploydevices.py -k <key> -o <org> -s <sn> -n <netw> -c <cfg_tmpl> [-t <tags>] [-a <addr>] [-m ignore_error]')
    printusertext('')
    printusertext('<key>: Your Meraki Dashboard API key')
    printusertext('<org>: Name of the Meraki Dashboard Organization to modify')
    printusertext('<sn>: Serial number of the devices to claim. Use double quotes and spaces to enter')
    printusertext('       multiple serial numbers. Example: -s "AAAA-BBBB-CCCC DDDD-EEEE-FFFF"')
    printusertext('       You can also enter a license key as a serial number to claim along with devices')
    printusertext('<netw>: Name the new network will have')
    printusertext('<cfg_template>: Name of the config template the new network will bound to')
    printusertext('-t <tags>: Optional parameter. If defined, network will be tagged with the given tags')
    printusertext('-a <addr>: Optional parameter. If defined, devices will be moved to given street address')
    printusertext('-m ignore_error: Optional parameter. If defined, the script will not stop if network exists')
    printusertext('')
    printusertext('Example:')
    printusertext('python deploydevices.py -k 1234 -o MyCustomer -s XXXX-YYYY-ZZZZ -n "SF Branch" -c MyCfgTemplate')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
    
def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')
    
def getshardurl(p_apikey, p_orgid):
    #Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
    # when making API calls with API accounts that can access multiple orgs.
    #On failure returns 'null'
    
    r = requests.get('https://dashboard.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()

    return(rjson['hostname'])
    
def getnwid(p_apikey, p_shardurl, p_orgid, p_nwname):
    #looks up network id for a network name
    #on failure returns 'null'

    r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_nwname:
            return record['id']
    return('null') 
    
def createnw(p_apikey, p_shardurl, p_dstorg, p_nwdata):
    #creates network if one does not already exist with the same name
    
    #check if network exists
    getnwresult = getnwid(p_apikey, p_shardurl, p_dstorg, p_nwdata['name'])
    if getnwresult != 'null':
        printusertext('WARNING: Skipping network "%s" (Already exists)' % p_nwdata['name'])
        return('null')
    
    if p_nwdata['type'] == 'combined':
        #find actual device types
        nwtype = 'wireless switch appliance'
    else:
        nwtype = p_nwdata['type']
    if nwtype != 'systems manager':
        r = requests.post('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_dstorg), data=json.dumps({'timeZone': p_nwdata['timeZone'], 'tags': p_nwdata['tags'], 'name': p_nwdata['name'], 'organizationId': p_dstorg, 'type': nwtype}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    else:
        printusertext('WARNING: Skipping network "%s" (Cannot create SM networks)' % p_nwdata['name'])
        return('null')
        
    return('ok')
    
def gettemplateid(p_apikey, p_shardurl, p_orgid, p_tname):
    #looks up config template id for a config template name
    #on failure returns 'null'

    r = requests.get('https://%s/api/v0/organizations/%s/configTemplates' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_tname:
            return record['id']
    return('null') 
    
def bindnw(p_apikey, p_shardurl, p_nwid, p_templateid, p_autobind):
    #binds a network to a template
    
    if p_autobind:
        autobindvalue = 'true'
    else:
        autobindvalue = 'false'
    
    r = requests.post('https://%s/api/v0/networks/%s/bind' % (p_shardurl, p_nwid), data=json.dumps({'configTemplateId': p_templateid, 'autoBind': autobindvalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
        
    if r.status_code != requests.codes.ok:
        return 'null'
        
    return('ok')
    
def claimdeviceorg(p_apikey, p_shardurl, p_orgid, p_devserial):
    #claims a device into an org without adding to a network
    
    r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardurl, p_orgid), data=json.dumps({'serial': p_devserial}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    return(0)
    
def claimlicenseorg(p_apikey, p_shardurl, p_orgid, p_licensekey):
    #claims a license key into an org
    
    r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardurl, p_orgid), data=json.dumps({'licenseKey': p_licensekey, 'licenseMode': 'addDevices'}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    return(0)
    
def claimdevice(p_apikey, p_shardurl, p_nwid, p_devserial):
	#claims a device into a network
	
	r = requests.post('https://%s/api/v0/networks/%s/devices/claim' % (p_shardurl, p_nwid), data=json.dumps({'serial': p_devserial}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	return(0)
    
def getdeviceinfo(p_apikey, p_shardurl, p_nwid, p_serial):
    #returns info for a single device
    #on failure returns lone device record, with serial number 'null'

    r = requests.get('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_serial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue = {'serial':'null', 'model':'null'}
        return(returnvalue)
    
    rjson = r.json()
    
    return(rjson) 
    
def setdevicedata(p_apikey, p_shardurl, p_nwid, p_devserial, p_field, p_value, p_movemarker):
    #modifies value of device record. Returns the new value
    #on failure returns one device record, with all values 'null'
    #p_movemarker is boolean: True/False
    
    movevalue = "false"
    if p_movemarker:
        movevalue = "true"
    
    r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_devserial), data=json.dumps({p_field: p_value, 'moveMapMarker': movevalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')

def getorgdeviceinfo (p_apikey, p_shardurl, p_orgid, p_devserial):
    #gets basic device info from org inventory. device does not need to be part of a network
    
    r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    returnvalue = {}
    if r.status_code != requests.codes.ok:
        returnvalue = {'serial':'null', 'model':'null'}
        return(returnvalue)
    
    rjson = r.json()
    
    foundserial = False
    for record in rjson:
        if record['serial'] == p_devserial:
            foundserial = True
            returnvalue = {'mac': record['mac'], 'serial': record['serial'], 'networkId': record['networkId'], 'model': record['model'], 'claimedAt': record['claimedAt'], 'publicIp': record['publicIp']}
                
    if not foundserial:
        returnvalue = {'serial':'null', 'model':'null'}
    return(returnvalue) 
    
def main(argv):
    #set default values for command line arguments
    arg_apikey = 'null'
    arg_orgname = 'null'
    arg_serial = 'null'
    arg_nwname = 'null'
    arg_template = 'null'
    arg_modexisting = 'null'
    arg_address = 'null'
    arg_nwtags = 'null'
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:s:n:c:m:a:t:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey = arg
        elif opt == '-o':
            arg_orgname = arg
        elif opt == '-s':
            arg_serial = arg
        elif opt == '-n':
            arg_nwname = arg
        elif opt == '-c':
            arg_template = arg
        elif opt == '-m':
            arg_modexisting = arg
        elif opt == '-a':
            arg_address = arg
        elif opt == '-t':
            arg_nwtags = arg
                
    #check if all parameters are required parameters have been given
    if arg_apikey == 'null' or arg_orgname == 'null' or arg_serial == 'null' or    arg_nwname == 'null' or arg_template == 'null':
        printhelp()
        sys.exit(2)
    
    #set optional flag to ignore error if network already exists
    stoponerror = True
    if arg_modexisting == 'ignore_error':
        stoponerror = False
    
    #get organization id corresponding to org name provided by user
    orgid = getorgid(arg_apikey, arg_orgname)
    if orgid == 'null':
        printusertext('ERROR: Fetching organization failed')
        sys.exit(2)
    
    #get shard URL where Org is stored
    shardurl = getshardurl(arg_apikey, orgid)
    if shardurl == 'null':
        printusertext('ERROR: Fetching Meraki cloud shard URL failed')
        sys.exit(2)
        
    #make sure that a network does not already exist with the same name    
    nwid = getnwid(arg_apikey, shardurl, orgid, arg_nwname)
    if nwid != 'null' and stoponerror:
        printusertext('ERROR: Network with that name already exists')
        sys.exit(2)    
        
    #get template ID for template name argument
    templateid = gettemplateid(arg_apikey, shardurl, orgid, arg_template)
    if templateid == 'null':
        printusertext('ERROR: Unable to find template: ' + arg_template)
        sys.exit(2)    
        
    #get serial numbers from parameter -s
    devicelist = {}
    devicelist['serial'] = arg_serial.split(" ")
    devicelist['model'] = []
    
    for i in range (0, len(devicelist['serial']) ):
        claimdeviceorg(arg_apikey, shardurl, orgid, devicelist['serial'][i])
        
        #check if device has been claimed successfully
        deviceinfo = getorgdeviceinfo (arg_apikey, shardurl, orgid, devicelist['serial'][i])
        if deviceinfo['serial'] == 'null':
            printusertext('INFO: Serial number %s is a license or unsupported device' % devicelist['serial'][i])
            claimlicenseorg(arg_apikey, shardurl, orgid, devicelist['serial'][i])
        devicelist['model'].append(deviceinfo['model'])
        
    #compile list of different product types in order to create correct type of network
    devicetypes = {'mx': False, 'ms': False, 'mr': False}
    for record in devicelist['model']:
        if record [:2] == 'MX' or record [:2] == 'Z1':
            devicetypes['mx'] = True
        elif record [:2] == 'MS':
            devicetypes['ms'] = True
        elif record [:2] == 'MR':
            devicetypes['mr'] = True
            
    #build network type string for network creation
    nwtypestring = ''
    if devicetypes['mr']:
        nwtypestring += 'wireless'
    if len(nwtypestring) > 0:
        nwtypestring += ' '
    if devicetypes['ms']:
        nwtypestring += 'switch'
    if len(nwtypestring) > 0:
        nwtypestring += ' '
    if devicetypes['mx']:
        nwtypestring += 'appliance'
                
    #compile parameters to create network
    nwtags = ''
    if arg_nwtags != 'null':
        nwtags = arg_nwtags
    ### NOTE THAT TIMEZONE IS HARDCODED IN THIS SCRIPT. EDIT THE LINE BELOW TO MODIFY ###
    nwparams = {'name': arg_nwname, 'timeZone': 'Europe/Helsinki', 'tags': nwtags, 'organizationId': orgid, 'type': nwtypestring}
        
    #create network and get its ID
    if nwid == 'null':
        createstatus = createnw (arg_apikey, shardurl, orgid, nwparams)
        if createstatus == 'null':
            printusertext('ERROR: Unable to create network')
            sys.exit(2)
        nwid = getnwid(arg_apikey, shardurl, orgid, arg_nwname)
        if nwid == 'null':
            printusertext('ERROR: Unable to get ID for new network')
            sys.exit(2)    
    
    #clean up serials list to filter out licenses, MVs, etc
    validserials = []
    for i in range (0, len(devicelist['serial']) ):
        if devicelist['model'][i] == 'mr' or devicelist['model'][i] == 'ms' or devicelist['model'][i] == 'mx':
            validserials.append(devicelist['serial'][i])
    
    for devserial in validserials:
        #claim device into newly created network
        claimdevice(arg_apikey, shardurl, nwid, devserial)
    
        #check if device has been claimed successfully
        deviceinfo = getdeviceinfo(arg_apikey, shardurl, nwid, devserial)
        if deviceinfo['serial'] == 'null':
            printusertext('ERROR: Claiming or moving device unsuccessful')
            sys.exit(2)
            
        #set device hostname
        hostname = deviceinfo['model'] + '_' + devserial
        setdevicedata(arg_apikey, shardurl, nwid, devserial, 'name', hostname, False)
    
        #if street address is given as a parameter, set device location
        if arg_address != 'null':
            setdevicedata(arg_apikey, shardurl, nwid, devserial, 'address', arg_address, True)
        
    #bind network to template. If switches in template, attempt to autobind them
    bindstatus = bindnw(arg_apikey, shardurl, nwid, templateid, devicetypes['ms'])
    if bindstatus == 'null' and stoponerror:
        printusertext('ERROR: Unable to bind network to template')
        sys.exit(2)
    
    printusertext('End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])