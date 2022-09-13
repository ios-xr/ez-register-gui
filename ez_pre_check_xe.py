#!/usr/bin/env python3

from netmiko import ConnectHandler
from argparse import ArgumentParser
import logging
import threading

# read input from excel sheet
import xlrd

# call sleep before retrieving smart license status
import time


def pre_check():
    try:
        timestr = time.strftime("%Y%m%d_%H%M%S")
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler("pre_checks/" + device_name + "_" + filename + "_" + timestr + ".log")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(log_Format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        # connect to the devices
        logger.info("="*60)
        logger.info("connecting to the node " + hostname)
        logger.info("="*60)
        device = ConnectHandler(device_type='cisco_ios', ip=hostname, username=username, password=password)
        device.find_prompt()

        # pre checks
        '''
        terminal length 0
        show run
        show version
        show platform
        show process memory | i call
        show processes cpu | e 0.00%  0.00%  0.00%
        show license status
        '''
        logger.info("="*60)
        logger.info("terminal length 0")
        logger.info("="*60)
        term_length = device.send_command("terminal length 0")
        #term_length += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(term_length)

        logger.info("="*60)
        logger.info("show run")
        logger.info("="*60)
        sh_run = device.send_command("show run")
        sh_run += device.send_command('\n', expect_string=r'#', delay_factor=10)
        logger.info(sh_run)

        logger.info("="*60)
        logger.info("show version")
        logger.info("="*60)
        sh_ver = device.send_command("show version")
        #sh_ver += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(sh_ver)


        logger.info("="*60)
        logger.info("show platform")
        logger.info("="*60)
        sh_ptf = device.send_command("show platform")
        #sh_ptf += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(sh_ptf)

        logger.info("="*60)
        logger.info("show process memory")
        logger.info("="*60)
        sh_prc = device.send_command("show process memory")
        sh_prc += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(sh_prc)

        logger.info("="*60)
        logger.info("show processes cpu | e 0.00%  0.00%  0.00%")
        logger.info("="*60)
        sh_cpu = device.send_command("show processes cpu | e 0.00%  0.00%  0.00%")
        sh_cpu += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(sh_cpu)

        logger.info("="*60)
        logger.info("show license status")
        logger.info("="*60)
        sh_lic = device.send_command("show license status")
        sh_lic += device.send_command('\n', expect_string=r'#', delay_factor=2)
        logger.info(sh_lic)

        print(device_name + " node" + str(i) + " : Pre Checks Completed")

        logger.info("="*80)
        logger.info("="*80)

        device.disconnect()
        logger.removeHandler(handler)

    except Exception as e:
        logger.info("="*60)
        logger.info("Exception!!")
        logger.info("="*60)
        err = str(e)
        logger.info(err)
        print("Host: " + device_name + " - pre check attempt failed" + ". Exception: " + err)
        logger.info("Host: " + device_name + " - pre check attempt failed" + ". Exception: " + err)
        logger.info("="*80)
        logger.info("="*80)


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", help="print debugging messages",
                        action="store_true")
    parser.add_argument("input_file",
                        help="input file location")
    parser.add_argument("num",
                        help="number of parallel threads")
    args = parser.parse_args()

    thread_list = []

    # Add  logs to the file
    log_Format = "%(levelname)s %(asctime)s - %(message)s"
    input_file = args.input_file
    number = int(args.num)
    filepath_list = input_file.split("/")
    filename = filepath_list[len(filepath_list)-1].split(".")[0]
    folder = "pre_checks/"
    timestr = time.strftime("%Y%m%d_%H%M%S")

    main_logger = logging.getLogger()
    main_logger.setLevel(logging.INFO)
    main_handler = logging.FileHandler(folder + filename + "_" + timestr + ".log")
    main_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(log_Format)
    main_handler.setFormatter(formatter)
    main_logger.addHandler(main_handler)

    # Read the excel sheet
    main_logger.info("="*60)
    main_logger.info("Reading the excel sheet")
    main_logger.info("="*60)
    wb = xlrd.open_workbook(input_file)
    sheet = wb.sheet_by_index(0)
    print("Beginning Pre Checks")
    main_logger.info("="*60)
    main_logger.info("Beginning Pre Checks")
    main_logger.info("="*60)
    num = 0
    for i in range(1, sheet.nrows):
        if sheet.cell_value(i, 0) == "":
            break
        else:
            main_logger.info("="*80)
            main_logger.info("Retrieving data of " + str(i) + " st/nd/th node")
            main_logger.info("="*80)
            hostname = sheet.cell_value(i, 0)
            username = sheet.cell_value(i, 1)
            password = sheet.cell_value(i, 2)
            device_name = sheet.cell_value(i, 16)
            t = threading.Thread(target=check_reachabilty, args=(hostname, username, password, device_name, i))
            thread_list.append(t)
            t.start()

            if num == number:
                time.sleep(60)
                num = 0

    for t in thread_list:
        t.join()

    main_logger.info("Pre Checks Completed")
    main_logger.removeHandler(main_handler)
