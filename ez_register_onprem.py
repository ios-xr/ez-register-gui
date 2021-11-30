#!/usr/bin/env python3

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

    # Add  logs to the file
    log_Format = "%(levelname)s %(asctime)s - %(message)s"
    logging.basicConfig(filename = "onprem.log",
                        filemode = "w",
                        format = log_Format,
                        level = logging.INFO)
    logger = logging.getLogger()

    # Initialize output file
    wb_output = xlwt.Workbook()
    sheet_output = wb_output.add_sheet('output')
    sheet_output.write(0, 0, "Hostname")
    sheet_output.write(0, 1, "Username")
    sheet_output.write(0, 2, "SL Registration Status")

    # initialize tokens dictionary
    sa_va_tokens = {}

    # Read the excel sheet
    logger.info("================================")
    logger.info("Reading the excel sheet")
    logger.info("================================")
    input_file = args.input_file
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    hostname = ""
    logger.info("Beginning Registration Attempts")
    for i in range(1, sheet.nrows):
        licenses = {}
        if sheet.cell_value(i, 0) == "":
           break
        else:
           logger.info("Retrieving data of " + str(i) + " st/nd/th node" )
       	   hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)
           smart_account = sheet.cell_value(i, 3)
           virtual_account = sheet.cell_value(i, 4)
           fcm = sheet.cell_value(i, 5)
           description = sheet.cell_value(i, 6)
           expires_after_days = sheet.cell_value(i, 7)
           export_controlled = sheet.cell_value(i, 8)
           onprem_ip = sheet.cell_value(i, 9)
           onprem_clientid = sheet.cell_value(i, 10)
           onprem_clientsecret = sheet.cell_value(i, 11)
           vrf = sheet.cell_value(i, 12)

        print("Beginning Registration Attempts")

        # connect to the devices
        logger.info("================================")
        logger.info("connecting to the node")
        logger.info("================================")
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        # check initial registration status
        initial_license_status = device.send_command("show license status")
        if "Status: REGISTERED" in initial_license_status:
            if "Smart Account: " + smart_account in initial_license_status and "Virtual Account: " + virtual_account in initial_license_status:
                continue
            else:
                deregister = device.send_command("license smart deregister ")
                logger.info(deregister)

        # configure call-home
        logger.info("====================================================================")
        logger.info("Configuring Call Home")
        logger.info("====================================================================")
        if vrf:
            config_commands = ['call-home',
            'vrf ' + vrf, 'profile CiscoTAC-1',
            'no destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
            'destination address http http://' + onprem_ip + '/Transportgateway/services/DeviceRequestHandler',
            'commit', 'end']
            output = device.send_config_set(config_commands)
            logger.info(output)
        else:
            config_commands = ['call-home', 'profile CiscoTAC-1',
            'no destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
            'destination address http http://' + onprem_ip + '/Transportgateway/services/DeviceRequestHandler',
            'commit', 'end']
            output = device.send_config_set(config_commands)
            logger.info(output)

        # configure trustpoint
        logger.info("====================================================================")
        logger.info("Trustpoint configuration on the node")
        logger.info("====================================================================")
        config_commands = ['crypto ca trustpoint Trustpool crl optional', 'commit', 'end']
        output = device.send_config_set(config_commands)
        logger.info(output)

        if (smart_account, virtual_account) in sa_va_tokens:
            id_token = sa_va_tokens[(smart_account, virtual_account)]
        else:
            logger.info("=================================================")
            logger.info("Creating access token to securely connect CSSM On-Prem")
            logger.info("=================================================")
            url = "https://" + onprem_ip + ":8443/oauth/token"
            params = {
                'grant_type': "client_credentials",
                'client_id': onprem_clientid,
                'client_secret': onprem_clientsecret
            }
            response = requests.request("POST", url,  params=params)
            logger.info(response.text)
            # using json.loads()
            # convert dictionary string to dictionary
            bearer = json.loads(response.text)
            access_token = bearer["access_token"]

             # Constructing Retrieve Existing Tokens Rest API
            logger.info("=============================================")
            logger.info("Constructing Retrieve Existing Tokens Rest API")
            logger.info("=============================================")
            tokens_url = "https://" + onprem_ip + ":8443/api/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
            headers = {
                 'Authorization': ' '.join(('Bearer',access_token)),
                 'Content-Type':'application/json',
                 #'Content-Type':'application/x-www-form-urlencoded',
                 'Accept':'application/json'
            }

            logger.info("====================================================================================")
            logger.info("Executing SL REST API to Retrieve Existing Tokens in CSSM On-Prem")
            logger.info("====================================================================================")
            existing_tokens = requests.request("GET", tokens_url, headers=headers)
            logger.info(response.text)
            # using json.loads()
            # convert dictionary string to dictionary
            tokens = json.loads(existing_tokens.text)
            if len(tokens['tokens']) != 0:
               idtoken = tokens['tokens'][0]['token']
            else:
               # SL on CSSM On-Prem
               logger.info("=============================================")
               logger.info("Constructing SL token REST API")
               logger.info("=============================================")
               url = "https://" + onprem_ip + ":8443/api/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
               headers = {
    	        'Authorization': ' '.join(('Bearer',access_token)),
                    'Content-Type':'application/json'
                    #'Content-Type':'application/x-www-form-urlencoded',
                    #'Accept':'application/json'
        	   }

               data = {}
               data["description"] = description
               data["expiresAfterDays"] = expires_after_days
               data["exportControlled"] = export_controlled

               data = json.dumps(data)
               logger.info("====================================================================================")
               logger.info("Executing SL REST API to generate registration token in CSSM On-Prem")
               logger.info("====================================================================================")
               response = requests.request("POST", url, data=data, headers=headers)
               logger.info(response.text)
               # using json.loads()
               # convert dictionary string to dictionary
               token = json.loads(response.text)
               logger.info(token)
               idtoken = token["tokenInfo"]["token"]
           sa_va_tokens[(smart_account, virtual_account)] = idtoken

        # register smart license idtoken on the node
        logger.info("==============================================")
        logger.info("registering smart license idtoken")
        logger.info("===============================================")
        output = device.send_command("license smart register idtoken " + idtoken)
        logger.info(output)

        if fcm == "Yes" or fcm == "yes":
           # enable license smart reservation configuration
           logger.info("====================================================================")
           logger.info("enabling license smart flexible-consumption on the node")
           logger.info("====================================================================")
           config_commands = ['license smart flexible-consumption enable', 'commit', 'end']
           output = device.send_config_set(config_commands)
           logger.info(output)
           logger.info("===================================================")
           logger.info("FCM is enabled successfully!!")
           logger.info("====================================================")

        print("Registration Attempt completed on host: " + hostname)

    logger.info("Beginning Verification")
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
           break
        else:
           logger.info("Retrieving data of " + str(i) + " st/nd/th node" )
           hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)

        print ("Beginning Verification")

        # connect to the devices
        logger.info("================================")
        logger.info("connecting to the node")
        logger.info("================================")
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        registered = False
        # register smart license status
        logger.info("==============================================")
        logger.info("registering smart license status")
        logger.info("===============================================")
        for j in range(0,5):
           license_status = device.send_command("show license status")
           if "Status: REGISTERED" in license_status:
              registered = True
              break
           time.sleep(1)
        logger.info(license_status)

        sheet_output.write(i, 0, hostname)
        sheet_output.write(i, 1, username)

        if "successfully" in output and registered:
           sheet_output.write(i, 2, "succcess")
           print(hostname + " - Registration Successful")
           logger.info("===================================================")
           logger.info("===================================================")
           logger.info("SL registration completed successfully!!")
           logger.info("====================================================")
           logger.info("====================================================")
        else:
           sheet_output.write(i, 2, "failed")
           print(hostname + " - Registration Failed")
           logger.info("===================================================")
           logger.info("===================================================")
           logger.info("SL registration failed!!")
           logger.info("====================================================")
           logger.info("====================================================")

        # disconnect device
        device.disconnect()
    wb_output.save('ez_register_onprem_results.xls')
