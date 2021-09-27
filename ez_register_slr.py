#!/usr/bin/env python

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging

# convert dictionary string to dictionary
# using json.loads()
import json

# copy auth_code file to the router
from paramiko import SSHClient
from scp import SCPClient
import os

# read input from excel sheet
import xlrd

# write output to the excel sheet
import xlwt

# call sleep before retrieving smart license status
import time

# slr SLR_PIDS
import ez_slr_pids as PD

if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    args = parser.parse_args()

    entitlement_Tags = {}
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

    # Initializing license reservation payload
    print("=====================================================")
    print("Initializing license reservation payload")
    print("=====================================================")
    payload = {
         "reservationRequests":[
 			  {
                              "licenses":[]
                          }
                     ]
           }

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
        if sheet.cell_value(i, 0) == "" and sheet.cell_value(i, 5) == "":
           break
        elif sheet.cell_value(i, 0) != "":
           print("Retrieving data of " + sheet.cell_value(i, 0))
           payload["reservationRequests"][0]["licenses"] = []
       	   hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)
           smart_account = sheet.cell_value(i, 3)
           virtual_account = sheet.cell_value(i, 4)
           client_id = sheet.cell_value(i, 7)
           client_secret = sheet.cell_value(i, 8)
           entitlement_tags = PD.SLR_PIDS[sheet.cell_value(i, 5)]
           for tag in entitlement_tags:
               licenses = {}
               licenses["entitlementTag"] = tag
               licenses["quantity"] = str(int(sheet.cell_value(i, 6)))
               payload["reservationRequests"][0]["licenses"].append(licenses)
        else:
           entitlement_tags = PD.SLR_PIDS[sheet.cell_value(i, 5)]
           for tag in entitlement_tags:
               licenses = {}
               licenses["entitlementTag"] = tag
               licenses["quantity"] = str(int(sheet.cell_value(i, 6)))
               payload["reservationRequests"][0]["licenses"].append(licenses)

        if (i == sheet.nrows-1) or (i+1 < sheet.nrows and sheet.cell_value(i+1, 0) != ""):
           licenses["precedence"] = "LONGEST_TERM_FIRST"
           #payload["reservationRequests"][0]["licenses"].append(licenses)
           print(payload)

           # connect to the devices
           print("================================")
           print("connecting to the node")
           print("================================")
           device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
           device.find_prompt()

           # check initial registration status
           initial_license_status = device.send_command("show license status")
           if "Status: REGISTERED" in initial_license_status:
              continue

           # enable license smart reservation configuration
           print("====================================================================")
           print("enabling license smart reservation configuration on the node")
           print("====================================================================")
           config_commands = ['license smart reservation', 'commit', 'end']
           output = device.send_config_set(config_commands)
           print(output)

           # create reservation request code
           print("============================================================")
           print("Retrieveing reservation request code from the node")
           print("============================================================")
           output = device.send_command("license smart reservation request local ")
           request_code = output.split("portal:")[1].replace("\n", "")

           # create bearer access token
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

           # SLR on CSSM
           print("=============================================")
           print("Constructing SLR reserve licenses REST API")
           print("=============================================")
           url = "https://swapi.cisco.com/services/api/smart-accounts-and-licensing/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/reserve-licenses"

           headers = {
	        'Authorization': ' '.join(('Bearer',access_token)),
                'Content-Type':'application/json',
                #'Content-Type':'application/x-www-form-urlencoded',
                'Accept':'application/json'
	   }

           payload["reservationRequests"][0]["reservationCode"] = request_code
           payload["reservationRequests"][0]["reservationType"] = "SPECIFIC"
           data = json.dumps(payload)

           print("====================================================================================")
           print("Executing SLR REST API to reserve licenses on CSSM and generate authorization code")
           print("====================================================================================")
           response = requests.request("POST", url,  data=data, headers=headers)
           print(response.text)

           # using json.loads()
           # convert dictionary string to dictionary
           authorization_codes = json.loads(response.text)
           auth_code = authorization_codes["authorizationCodes"][0]["authorizationCode"]
           print(auth_code)

           # create auth_code file and write the CSSM generated auth_code to the file
           print("==============================================================================")
           print("creating auth_code file and copying the CSSM generated auth code to the file")
           print("==============================================================================")
           auth_code_file = open("auth_code.txt","w+")
           auth_code_file.write(auth_code)
           auth_code_file.close()

           # copy auth_code file to the router
           print("==========================================================")
           print("copying the auth_code file to the node via SSHClient ")
           print("==========================================================")
           ssh = SSHClient()
           ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
           ssh.connect(hostname=hostname, username=username, password=password, allow_agent=False, look_for_keys=False)
           with SCPClient(ssh.get_transport()) as scp:
                   scp.put('auth_code.txt', '/disk0:')


           # install Authorization code on the device
           print("==============================================")
           print("Installing Authorization code on the node")
           print("===============================================")
           output = device.send_command("license smart reservation install file auth_code.txt")
           print (output)

           sheet_output.write(i, 0, hostname)
           sheet_output.write(i, 1, username)

           registered = False
           # verify smart license status
           print("==============================================")
           print("verify smart license status")
           print("===============================================")
           for j in range(0,5):
              time.sleep(5)
              license_status = device.send_command("show license status")
              if "Status: REGISTERED - SPECIFIC LICENSE RESERVATION" in license_status:
                 registered = True
                 break
           print(license_status)

           if registered:
              sheet_output.write(i, 2, "succcess")
              print("===================================================")
              print("===================================================")
              print("SLR reservation completed!!")
              print("====================================================")
              print("====================================================")
           else:
              sheet_output.write(i, 2, "failed")
              print("===================================================")
              print("===================================================")
              print("SLR reservation failed!!")
              print("====================================================")
              print("====================================================")

           # disconnect device
           device.disconnect()
    wb_output.save('ez_register_slr_results.xls')
