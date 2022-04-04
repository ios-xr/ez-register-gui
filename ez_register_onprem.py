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

    # Add  logs to the file
    log_Format = "%(levelname)s %(asctime)s - %(message)s"
    input_file = args.input_file
    filepath_list = input_file.split("/")
    filename = filepath_list[len(filepath_list)-1].split(".")[0]
    timestr = time.strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(filename=filename + "_" + timestr + ".log",
                        filemode="w",
                        format=log_Format,
                        level=logging.INFO)
    logger = logging.getLogger()

    # Initialize output file
    wb_output = xlwt.Workbook()
    sheet_output = wb_output.add_sheet('output')
    sheet_output.write(0, 0, "Hostname")
    sheet_output.write(0, 1, "Username")
    sheet_output.write(0, 2, "SL Registration Status")
    sheet_output.write(0, 3, "License Authorization Status")

    # initialize tokens dictionary
    sa_va_tokens = {}

    # dictionary to store error status of a node
    registration_status = {}

    # compliance status
    compliance_status = {}

    # Read the excel sheet
    logger.info("================================")
    logger.info("Reading the excel sheet")
    logger.info("================================")
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    print("Beginning Registration Attempts")
    for i in range(1, sheet.nrows):
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
           reregister = sheet.cell_value(i, 13)
           install_cert = sheet.cell_value(i, 14)

        try:
            # connect to the devices
            logger.info("================================")
            logger.info("connecting to the node")
            logger.info("================================")
            device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
            device.find_prompt()

            # check initial registration status
            initial_license_status = device.send_command("show license status")
            if "Status: REGISTERED" in initial_license_status and not (reregister.upper() == "YES" or reregister.upper() == "Y"):
               actual_smart_account = device.send_command("show license status | include Smart Account:").split("Smart Account: ")[1]
               actual_virtual_account = device.send_command("show license status | include Virtual Account:").split("Virtual Account: ")[1]
               reg_status = " Already registered with the Smart Account: " + actual_smart_account + " and the Virtual Account: " + actual_virtual_account
               print("Host: " + hostname + " - " + reg_status)
               registration_status[hostname] = reg_status
               lic_auth = device.send_command("show license status | begin License Authorization")
               comp_stat = lic_auth.split('\n')[3].split("Status: ")[1]
               compliance_status[hostname] = comp_stat
               continue
            elif "Status: REGISTERED" in initial_license_status:
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
                'destination address http https://' + onprem_ip + '/Transportgateway/services/DeviceRequestHandler',
                'commit', 'end']
                output = device.send_config_set(config_commands)
            else:
                config_commands = ['call-home', 'profile CiscoTAC-1',
                'no destination address http https://tools.cisco.com/its/service/oddce/services/DDCEService',
                'destination address http https://' + onprem_ip + '/Transportgateway/services/DeviceRequestHandler',
                'commit', 'end']
                output = device.send_config_set(config_commands)
            logger.info(output)

            # configure trustpoint
            ws_reachable_via_vrf = sheet.cell_value(i, 16)
            trustpoint = sheet.cell_value(i, 17)
            logger.info("====================================================================")
            logger.info("Trustpoint configuration on the node")
            logger.info("====================================================================")
            if ws_reachable_via_vrf.upper() == "YES" or ws_reachable_via_vrf.upper() == "Y":
                config_commands1 = ['crypto ca trustpoint Trustpool', 'crl optional', 'vrf ' + vrf, 'commit', 'end']
                if trustpoint:
                    config_commands2 = ['crypto ca trustpoint ' + trustpoint, 'crl optional', 'vrf ' + vrf, 'enrollment url terminal', 'commit', 'end']
            else:
                config_commands1 = ['crypto ca trustpoint Trustpool', 'crl optional', 'commit', 'end']
                if trustpoint:
                    config_commands2 = ['crypto ca trustpoint ' + trustpoint, 'crl optional', 'enrollment url terminal', 'commit', 'end']

            output1 = device.send_config_set(config_commands1)
            logger.info(output1)
            if trustpoint:
                output2 = device.send_config_set(config_commands2)
                logger.info(output2)

            # install certificate
            if install_cert.upper() == "YES" or install_cert.upper() == "Y":
                web_server_ip = sheet.cell_value(i, 15)
                cert_output = device.send_command("crypto ca trustpool import url http://" + web_server_ip + "/ios_core.p7b")
                logger.info(cert_output)

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
            reg_output = device.send_command("license smart register idtoken " + idtoken)
            logger.info(reg_output)

            if fcm.upper() == "YES" or fcm.upper() == "Y":
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

            print("Host: " + hostname + " - Registration attempt completed")
        except Exception as e:
            err = str(e)
            print("Host: " + hostname + " - Registration attempt failed" + ". Exception: " + err)
            registration_status[hostname] = err

    print("\nBeginning Verification")
    count = 0
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
           break
        else:
           logger.info("Retrieving data of " + str(i) + " st/nd/th node" )
           hostname = sheet.cell_value(i, 0)
           username = sheet.cell_value(i, 1)
           password = sheet.cell_value(i, 2)

        sheet_output.write(i, 0, hostname)
        sheet_output.write(i, 1, username)
        if hostname in registration_status:
           count += 1
           sheet_output.write(i, 2, str(registration_status[hostname]))
           if hostname in compliance_status:
              sheet_output.write(i, 3, str(compliance_status[hostname]))
           print("Host: "+ hostname + " - " + str(registration_status[hostname]))
           continue

        # connect to the devices
        logger.info("================================")
        logger.info("connecting to the node")
        logger.info("================================")
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        registered = False
        lic_auth = device.send_command("show license status | begin License Authorization")
        comp_stat = lic_auth.split('\n')[3].split("Status: ")[1]
        sheet_output.write(i, 3, comp_stat)

        # register smart license status
        logger.info("==============================================")
        logger.info("verifying smart license status")
        logger.info("===============================================")
        license_status = device.send_command("show license status")
        if "Status: REGISTERED" in license_status:
           registered = True
        logger.info(license_status)

        if registered:
           count += 1
           sheet_output.write(i, 2, "succcess")
           print("Host: " + hostname + " - Registration Successful")
           logger.info("===================================================")
           logger.info("===================================================")
           logger.info("SL registration completed successfully!!")
           logger.info("====================================================")
           logger.info("====================================================")
        else:
           sheet_output.write(i, 2, "failed")
           print("Host: " + hostname + " - Registration Failed")
           logger.info("===================================================")
           logger.info("===================================================")
           logger.info("SL registration failed!!")
           logger.info("====================================================")
           logger.info("====================================================")

        # disconnect device
        device.disconnect()
    print("\nOut of " + str(sheet.nrows-1) + " node(s), " + str(count) + " node(s) is/are successfully registered")
    wb_output.save(filename + "_output_" + timestr + ".xls")
