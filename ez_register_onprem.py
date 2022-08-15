#!/usr/bin/env python3

from netmiko import ConnectHandler
import requests
from argparse import ArgumentParser
import logging
import warnings
import threading

# convert dictionary string to dictionary
# using json.loads()
import json

# read input from excel sheet
import xlrd

# write output to the excel sheet
import xlwt

# call sleep before retrieving smart license status
import time

# dictionary to store registration status of a node
registration_status = {}

# initialize tokens dictionary
sa_va_tokens = {}

# Initialize output file
wb_output = xlwt.Workbook()
sheet_output = wb_output.add_sheet('output')
sheet_output.write(0, 0, "Hostname")
sheet_output.write(0, 1, "Username")
sheet_output.write(0, 2, "SL Registration Status")
sheet_output.write(0, 3, "License Authorization Status")
sheet_output.write(0, 4, "Device Name")


def register(hostname, username, password, smart_account,
             virtual_account, fcm, description, expires_after_days,
             export_controlled, onprem_ip, onprem_clientid, onprem_clientsecret,
             vrf, reregister, install_cert, device_name, ws_reachable_via_vrf,
             trustpoint, src_int, web_server_ip, i):

    try:
        # connect to the devices
        logger.info("="*60)
        logger.info("connecting to the node")
        logger.info("="*60)
        device = ConnectHandler(device_type='cisco_xr', ip=hostname, username=username, password=password)
        device.find_prompt()

        # check initial registration status
        logger.info("="*60)
        logger.info("checking initial registration status")
        logger.info("="*60)
        initial_license_status = device.send_command("show license status")
        logger.info(initial_license_status)
        if ("Status: REGISTERED" in initial_license_status) and not (reregister.upper() == "YES" or reregister.upper() == "Y"):
            actual_smart_account = device.send_command("show license status | include Smart Account:").split("Smart Account: ")[1]
            actual_virtual_account = device.send_command("show license status | include Virtual Account:").split("Virtual Account: ")[1]
            reg_status = " Already registered with the Smart Account: " + actual_smart_account + " and the Virtual Account: " + actual_virtual_account
            print("Host: " + hostname + " - " + reg_status)
            logger.info("Host: " + hostname + " - " + reg_status)
            sheet_output.write(i, 2, reg_status)
            registration_status[hostname] = True
            lic_auth = device.send_command("show license status | begin License Authorization")
            # TODO: split number varies between 2 or 3 based on the env
            logger.info(lic_auth.split('\n'))
            auth = lic_auth.split('\n')
            comp_stat = ""
            if 'Status' in auth[3]:
                comp_stat = auth[3].split("Status: ")[1]
            elif 'Status' in auth[2]:
                comp_stat = auth[2].split("Status: ")[1]
            sheet_output.write(i, 3, comp_stat)
        elif "Status: REGISTERED" in initial_license_status and (reregister.upper() == "YES" or reregister.upper() == "Y"):
            deregister = device.send_command("license smart deregister ")
            logger.info(deregister)
        license_status = device.send_command("show license status")
        if "Status: REGISTERED" not in initial_license_status:
            # configure call-home
            logger.info("="*60)
            logger.info("Configuring Call Home")
            logger.info("="*60)
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
            logger.info("="*60)
            logger.info("Configuring trustpoint on the node")
            logger.info("="*60)

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

            # configure ipv6 source interface
            logger.info("="*60)
            logger.info("Configuring ipv6 source interface")
            logger.info("="*60)
            if onprem_ip.startswith('['):
                if vrf:
                    http_client_cfg = ['http client vrf ' + vrf, 'commit', 'end']
                    http_client_output = device.send_config_set(http_client_cfg)
                    logger.info(http_client_output)
                ipv6_cfg = ['http client source-interface ipv6 ' + src_int, 'commit', 'end']
                ipv6_cfg_output = device.send_config_set(ipv6_cfg)
                logger.info(ipv6_cfg_output)

            # install certificate
            logger.info("="*60)
            logger.info("copy certificate")
            logger.info("="*60)
            if install_cert.upper() == "YES" or install_cert.upper() == "Y":

                #if ws_reachable_via_vrf.upper() == "YES" or ws_reachable_via_vrf.upper() == "Y":
                    #cpy_cert = device.send_command("copy http://" + web_server_ip + "/ios_core.p7b harddisk:" + " vrf " + vrf, expect_string=r'Destination filename')
                #else:
                    #cpy_cert = device.send_command("copy http://" + web_server_ip + "/ios_core.p7b harddisk:", expect_string=r'Destination filename')
                #cpy_cert += device.send_command('\n', expect_string=r'#', delay_factor=2)
                #logger.info(cpy_cert)
                #logger.info("="*60)
                logger.info("import CA")
                logger.info("="*60)
                cert_output = device.send_command("crypto ca trustpool import url http://" + web_server_ip + "/ios_core.p7b")
                cert_output += device.send_command('\n', expect_string=r'#', delay_factor=2)
                logger.info(cert_output)

            # disable http client secure-verify-peer
            logger.info("="*60)
            logger.info("disable http client secure-verify-peer")
            logger.info("="*60)
            if vrf:
                http_client_cfg = ['http client vrf ' + vrf, 'commit', 'end']
                http_client_output = device.send_config_set(http_client_cfg)
                logger.info(http_client_output)
            vrfy_peer = ['http client secure-verify-peer disable', 'commit', 'end']
            vrfy_peer_output = device.send_config_set(vrfy_peer)
            logger.info(vrfy_peer_output)

            # ignore warnings
            warnings.simplefilter("ignore")

            # check if SA/VA token is available in the cache
            if (smart_account, virtual_account) in sa_va_tokens:
                idtoken = sa_va_tokens[(smart_account, virtual_account)]
            else:
                logger.info("="*60)
                logger.info("Creating access token to securely connect CSSM On-Prem")
                logger.info("="*60)
                url = "https://" + onprem_ip + ":8443/oauth/token"
                params = {
                    'grant_type': "client_credentials",
                    'client_id': onprem_clientid,
                    'client_secret': onprem_clientsecret
                }
                response = requests.request("POST", url,  params=params, verify=False)
                logger.info(response.text)
                # using json.loads()
                # convert dictionary string to dictionary
                bearer = json.loads(response.text)
                access_token = bearer["access_token"]

                # Constructing Retrieve Existing Tokens Rest API
                logger.info("="*60)
                logger.info("Constructing Retrieve Existing Tokens Rest API")
                logger.info("="*60)
                tokens_url = "https://" + onprem_ip + ":8443/api/v1/accounts/" + smart_account + "/virtual-accounts/" + virtual_account + "/tokens"
                headers = {
                     'Authorization': ' '.join(('Bearer', access_token)),
                     'Content-Type': 'application/json',
                     # 'Content-Type':'application/x-www-form-urlencoded',
                     'Accept': 'application/json'
                }

                logger.info("="*80)
                logger.info("Executing SL REST API to Retrieve Existing Tokens in CSSM On-Prem")
                logger.info("="*80)
                existing_tokens = requests.request("GET", tokens_url, headers=headers, verify=False)
                logger.info(existing_tokens)
                # using json.loads()
                # convert dictionary string to dictionary
                tokens = json.loads(existing_tokens.text)
                logger.info(tokens)
                if tokens and len(tokens['tokens']) != 0:
                    idtoken = tokens['tokens'][0]['token']
                else:
                   # SL on CSSM On-Prem
                   logger.info("="*60)
                   logger.info("Constructing SL token REST API")
                   logger.info("="*60)
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
                   logger.info("="*80)
                   logger.info("Executing SL REST API to generate registration token in CSSM On-Prem")
                   logger.info("="*80)
                   response = requests.request("POST", url, data=data, headers=headers, verify=False)
                   logger.info(response.text)
                   # using json.loads()
                   # convert dictionary string to dictionary
                   token = json.loads(response.text)
                   logger.info(token)
                   idtoken = token["tokenInfo"]["token"]
                sa_va_tokens[(smart_account, virtual_account)] = idtoken

            # register smart license idtoken on the node
            logger.info("="*60)
            logger.info("registering smart license idtoken")
            logger.info("="*60)
            reg_output = device.send_command("license smart register idtoken " + idtoken)
            logger.info(reg_output)

            if fcm.upper() == "YES" or fcm.upper() == "Y":
               # enable license smart reservation configuration
               logger.info("="*80)
               logger.info("enabling license smart flexible-consumption on the node")
               logger.info("="*80)
               config_commands = ['license smart flexible-consumption enable', 'commit', 'end']
               output = device.send_config_set(config_commands)
               logger.info(output)
               logger.info("="*60)
               logger.info("FCM is enabled successfully!!")
               logger.info("="*60)

            print("Host: " + device_name + " - Registration attempt completed")

            print("\nBeginning Verification")
            logger.info("="*60)
            logger.info("Beginning Verification")
            logger.info("="*60)

            logger.info("="*60)
            logger.info("license smart renew auth")
            logger.info("="*60)
            renew_auth = device.send_command("license smart renew auth")
            logger.info(renew_auth)

            time.sleep(10)

            registered = False
            lic_auth = device.send_command("show license status | begin License Authorization")
            logger.info(lic_auth)
            logger.info("lic_auth.split('\n')[2].split('Status: ')[1]")
            logger.info(lic_auth.split('\n'))
            # split 2 or 3 varies based on the system - TODO
            auth = lic_auth.split('\n')
            comp_stat = ""
            if 'Status' in auth[3]:
                comp_stat = auth[3].split("Status: ")[1]
            elif 'Status' in auth[2]:
                comp_stat = auth[2].split("Status: ")[1]
            sheet_output.write(i, 3, comp_stat)

            # register smart license status
            logger.info("="*60)
            logger.info("verifying smart license status")
            logger.info("="*60)
            license_status = device.send_command("show license status")
            if ("Status: REGISTERED" in license_status) or ("Registration: Succeeded" in license_status) or ("Registration: SUCCEEDED" in license_status):
                registered = True
            logger.info(license_status)

            if registered:
                sheet_output.write(i, 2, "succcess")
                registration_status[hostname] = True
                print("Host: " + device_name + " - Registration Successful")
                logger.info("===================================================")
                logger.info("===================================================")
                logger.info("SL registration completed successfully!!")
                logger.info("====================================================")
                logger.info("====================================================")
            else:
                sheet_output.write(i, 2, "failed")
                registration_status[hostname] = False
                print("Host: " + device_name + " - Registration Failed")
                logger.info("===================================================")
                logger.info("===================================================")
                logger.info("SL registration failed!!")
                logger.info("====================================================")
                logger.info("====================================================")

            # disconnect device
            device.disconnect()

    except Exception as e:
        logger.info("="*60)
        logger.info("Exception!!")
        logger.info("="*60)
        err = str(e)
        logger.info(err)
        print("Host: " + device_name + " - Registration attempt failed" + ". Exception: " + err)



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
    folder = "logs/"
    timestr = time.strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(filename=folder + filename + "_" + timestr + ".log",
                        filemode="w",
                        format=log_Format,
                        level=logging.INFO)
    logger = logging.getLogger()

    thread_list = []

    # Read the excel sheet
    logger.info("="*60)
    logger.info("Reading the excel sheet")
    logger.info("="*60)
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    print("Beginning Registration Attempts")
    logger.info("="*60)
    logger.info("Beginning Registration Attempts")
    logger.info("="*60)

    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
            break
        else:
            logger.info("="*80)
            logger.info("Retrieving data of " + str(i) + " st/nd/th node" )
            logger.info("="*80)
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
            device_name = sheet.cell_value(i,19)
            ws_reachable_via_vrf = sheet.cell_value(i, 16)
            trustpoint = sheet.cell_value(i, 17)
            src_int = sheet.cell_value(i, 18)
            web_server_ip = sheet.cell_value(i, 15)

            t = threading.Thread(target=register, args=(hostname, username, password, smart_account,
                                 virtual_account, fcm, description, expires_after_days,
                                 export_controlled, onprem_ip, onprem_clientid, onprem_clientsecret,
                                 vrf, reregister, install_cert, device_name, ws_reachable_via_vrf,
                                 trustpoint, src_int, web_server_ip, i))
            thread_list.append(t)
            t.start()

    for t in thread_list:
        t.join()

    count = 0
    for key in registration_status:
        if registration_status[key]:
            count += 1
    print("Out of " + str(sheet.nrows-1) + " nodes " + str(count) + " nodes are registered successfully")
    folder = "output_files/"
    wb_output.save(folder + filename + "_output_" + timestr + ".xls")
