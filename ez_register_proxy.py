#!/usr/bin/env python

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging

# convert dictionary string to dictionary
# using json.loads()
import json

# read input from excel sheet
import xlrd

# write output to the excel sheet
import xlwt

# call sleep before retrieving smart license status
import time

if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    args = parser.parse_args()

    # log debug messages if verbose argument specified
    if args.verbose:
        logger = logging.getLogger("SLR")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(("%(asctime)s - %(name)s - "
                                      "%(levelname)s - %(message)s"))
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Initialize output file
    wb_output = xlwt.Workbook()
    sheet_output = wb_output.add_sheet('output')
    sheet_output.write(0, 0, "Hostname")
    sheet_output.write(0, 1, "Username")
    sheet_output.write(0, 2, "SL Registration Status")

    # Read the excel sheet
    print("================================")
    print("Reading the excel sheet")
    print("================================")
    input_file = args.input_file
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    hostname = ""
    for i in range(1, sheet.nrows):
        licenses = {}
        if sheet.cell_value(i, 0) == "":
           break
        else:
           print("Retrieving data of " + str(i) + " st/nd/th node" )
       	   hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)
           smart_account = sheet.cell_value(i, 3)
           virtual_account = sheet.cell_value(i, 4)
           fcm = sheet.cell_value(i, 5)
           description = sheet.cell_value(i, 6)
           expires_after_days = sheet.cell_value(i, 7)
           export_controlled = sheet.cell_value(i, 8)
           proxy_address = str(sheet.cell_value(i, 9))
           port_number = str(int(sheet.cell_value(i, 10)))
           client_id = sheet.cell_value(i, 11)
           client_secret = sheet.cell_value(i, 12)

         # connect to the devices
        print("================================")
        print("connecting to the node")
        print("================================")
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        # check initial registration status
        initial_license_status = device.send_command("show license status")
        if "Status: REGISTERED" in initial_license_status:
            if "Smart Account: " + smart_account in initial_license_status and "Virtual Account: " + virtual_account in initial_license_status:
                continue
            else:
                deregister = device.send_command("license smart deregister ")
                print(deregister)
                
        # configure call-home
        print("====================================================================")
        print("Configuring Call Home")
        print("====================================================================")
        config_commands = ['call-home',
        'http-proxy ' + proxy_address + ' port ' + port_number,
        'profile CiscoTAC-1',
        'destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
        'commit', 'end']
        output = device.send_config_set(config_commands)
        print(output)

        print("=================================================")
        print("Creating access token to securely connect CSSM")
        print("=================================================")
        url = "https://cloudsso.cisco.com/as/token.oauth2"
        params = {
            'grant_type': "client_credentials",
            'client_id': client_id,
            'client_secret': client_secret
        }
        response = requests.request("POST", url,  params=params)
        print(response.text)
        # using json.loads()
        # convert dictionary string to dictionary
        bearer = json.loads(response.text)
        access_token = bearer["access_token"]

        # Constructing Retrieve Existing Tokens Rest API
        print("=============================================")
        print("Constructing Retrieve Existing Tokens Rest API")
        print("=============================================")
        tokens_url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
        headers = {
             'Authorization': ' '.join(('Bearer',access_token)),
             'Content-Type':'application/json',
             #'Content-Type':'application/x-www-form-urlencoded',
             'Accept':'application/json'
        }

        print("====================================================================================")
        print("Executing SL REST API to Retrieve Existing Tokens in CSSM")
        print("====================================================================================")
        existing_tokens = requests.request("GET", tokens_url, headers=headers)
        print(response.text)
        # using json.loads()
        # convert dictionary string to dictionary
        tokens = json.loads(existing_tokens.text)
        if len(tokens['tokens']) != 0:
           idtoken = tokens['tokens'][0]['token']
        else:
           print("There are no existing token available")
           # Contructing Create New Token Rest API
           print("=============================================")
           print("Constructing Create New token REST API")
           print("=============================================")
           url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
           headers = {
	        'Authorization': ' '.join(('Bearer',access_token)),
                'Content-Type':'application/json',
                #'Content-Type':'application/x-www-form-urlencoded',
                'Accept':'application/json'
	   }

           data = {}
           data["description"] = description
           data["expiresAfterDays"] = expires_after_days
           data["exportControlled"] = export_controlled

           data = json.dumps(data)
           print("====================================================================================")
           print("Executing SL REST API to generate registration token in CSSM")
           print("====================================================================================")
           response = requests.request("POST", url, data=data, headers=headers)
           print(response.text)
           # using json.loads()
           # convert dictionary string to dictionary
           token = json.loads(response.text)
           idtoken = token["tokenInfo"]["token"]

        # register smart license idtoken on the node
        print("==============================================")
        print("registering smart license idtoken")
        print("===============================================")
        output = device.send_command("license smart register idtoken " + idtoken)
        print(output)

        registered = False
        # register smart license status
        print("==============================================")
        print("registering smart license status")
        print("===============================================")
        for j in range(0,5):
           time.sleep(5)
           license_status = device.send_command("show license status")
           if "Status: REGISTERED" in license_status:
              registered = True
              break
        print(license_status)

        sheet_output.write(i, 0, hostname)
        sheet_output.write(i, 1, username)

        if "successfully" in output and registered:
           sheet_output.write(i, 2, "succcess")
           print("===================================================")
           print("===================================================")
           print("SL registration completed successfully!!")
           print("====================================================")
           print("====================================================")
        else:
           sheet_output.write(i, 2, "failed")
           print("===================================================")
           print("===================================================")
           print("SL registration failed!!")
           print("====================================================")
           print("====================================================")

        if fcm == "Yes" or fcm == "yes":
           # enable license smart reservation configuration
           print("====================================================================")
           print("enabling license smart flexible-consumption on the node")
           print("====================================================================")
           config_commands = ['license smart flexible-consumption enable', 'commit', 'end']
           output = device.send_config_set(config_commands)
           print(output)
           print("===================================================")
           print("FCM is enabled successfully!!")
           print("====================================================")

        # disconnect device
        device.disconnect()
    wb_output.save('ez_register_proxy_results.xls')
