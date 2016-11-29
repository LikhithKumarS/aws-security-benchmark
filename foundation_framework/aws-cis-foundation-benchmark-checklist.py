"""Summary

Attributes:
    AWS_CIS_BENCHMARK_VERSION (str): Description
    CLOUDTRAIL_CLIENT (TYPE): Description
    CONFIG_RULE (bool): Description
    CONTROL_1_1_DAYS (int): Description
    IAM_CLIENT (TYPE): Description
    REGIONS (list): Description
    S3_WEB_REPORT (bool): Description
    S3_WEB_REPORT_BUCKET (str): Description
    S3_WEB_REPORT_EXPIRE (str): Description
    S3_WEB_REPORT_OBFUSCATE_ACCOUNT (bool): Description
    SCRIPT_OUTPUT_JSON (bool): Description
"""
### TODO:
### Paginators where needed

import json
import csv
import time
import sys
import re
import tempfile
from datetime import datetime
import boto3


# CONSTANTS used in validation

# CIS Benchmark version referenced
AWS_CIS_BENCHMARK_VERSION = "1.1"

# Control 1.1 - Days allowed since use of root account.
CONTROL_1_1_DAYS = 0

# Control 1.18 - IAM manager and master role names.
IAM_MASTER = "iam_master"
IAM_MANAGER = "iam_manager"
IAM_MASTER_POLICY = "iam_master_policy"
IAM_MANAGER_POLICY = "iam_manager_policy"


# Set to true to enable config rule reporting.
CONFIG_RULE = False

# Would you like a HTML file generated with the result?
# This file will be delivered using a signed URL.
S3_WEB_REPORT = True

# Where should the report be delivered to?
# The script will add the account number if the bucket cannot be created.
S3_WEB_REPORT_BUCKET = "cr-cis-report"

# How many hours should the report be available? Default = 168h/7days
S3_WEB_REPORT_EXPIRE = "168"

# Set to true if you wish to anonymize the account number in the report.
# This is mostly used for demo/sharing purposes.
S3_WEB_REPORT_OBFUSCATE_ACCOUNT = True

# Would you like to print the results as JSON to output?
SCRIPT_OUTPUT_JSON = True


CLOUDTRAIL_CLIENT = boto3.client('cloudtrail')
IAM_CLIENT = boto3.client('iam')
S3_CLIENT = boto3.client('s3')
EC2_CLIENT = boto3.client('ec2')


# --- 1 Identity and Access Management ---

# 1.1 Avoid the use of the "root" account (Scored)
def control_1_1_root_use(credreport):
    """Summary

    Args:
        credreport (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.1"
    description = "Avoid the use of the root account"
    scored = True
    if "Fail" in credreport: # Report failure in control
        sys.exit(credreport)
    # Check if root is used in the last 24h
    now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time()))
    frm = "%Y-%m-%dT%H:%M:%S+00:00"

    try:
        pwdDelta = (datetime.strptime(now, frm) 
                   - datetime.strptime(credreport[0]['password_last_used']
                    , frm))
        if (pwdDelta.days == CONTROL_1_1_DAYS) & (pwdDelta.seconds > 0): # Used within last 24h
            failReason = "Used within 24h"
            result = False
    except:
        if credreport[0]['password_last_used'] == "N/A":
            pass
        else:
            print "Something went wrong"

    try:
        key1Delta = (datetime.strptime(now, frm) 
                    - datetime.strptime(credreport[0]
                    ['access_key_1_last_used_date'], frm))
        if (key1Delta.days == CONTROL_1_1_DAYS) & (key1Delta.seconds > 0): # Used within last 24h
            failReason = "Used within 24h"
            result = False
    except:
        if credreport[0]['access_key_1_last_used_date'] == "N/A":
            pass
        else:
            print "Something went wrong"
    try:
        key2Delta = datetime.strptime(now, frm) - datetime.strptime(credreport[0]['access_key_2_last_used_date'], frm)
        if (key2Delta.days == CONTROL_1_1_DAYS) & (key2Delta.seconds > 0): # Used within last 24h
            failReason = "Used within 24h"
            result = False
    except:
        if credreport[0]['access_key_2_last_used_date'] == "N/A":
            pass
        else:
            print "Something went wrong"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.2 Ensure multi-factor authentication (MFA) is enabled for all IAM users that have a console password (Scored)
def control_1_2_mfa_on_password_enabled_iam(credreport):
    """Summary

    Args:
        credreport (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.2"
    description = "Ensure multi-factor authentication (MFA) is enabled for all IAM users that have a console password"
    scored = True
    for i in range(len(credreport)):
        # Verify if the user have a password configured
        if credreport[i]['password_enabled'] == "true":
            # Verify if password users have MFA assigned
            if credreport[i]['mfa_active'] == "false":
                result = False
                failReason = "No MFA on users with password. "
                offenders.append(credreport[i]['arn'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.3 Ensure credentials unused for 90 days or greater are disabled (Scored)
def control_1_3_unused_credentials(credreport):
    """Summary

    Args:
        credreport (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.3"
    description = "Ensure credentials unused for 90 days or greater are disabled"
    scored = True
    # Get current time
    now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time()))
    frm = "%Y-%m-%dT%H:%M:%S+00:00"

    # Look for unused credentails
    for i in range(len(credreport)):
        if credreport[i]['password_enabled'] == "true":
            try:
                delta = datetime.strptime(now, frm) - datetime.strptime(credreport[i]['password_last_used_date'], frm)
                # Verify password have been used in the last 90 days
                if delta.days > 90:
                    result = False
                    failReason = "Credentials unused > 90 days detected. "
                    offenders.append(credreport[i]['arn'] + ":password")
            except:
                pass # Never used
        if credreport[i]['access_key_1_active'] == "true":
            try:
                delta = datetime.strptime(now, frm) - datetime.strptime(credreport[i]['access_key_1_last_used_date'], frm)
                # Verify password have been used in the last 90 days
                if delta.days > 90:
                    result = False
                    failReason = "Credentials unused > 90 days detected. "
                    offenders.append(credreport[i]['arn'] + ":key1")
            except:
                pass
        if credreport[i]['access_key_2_active'] == "true":
            try:
                delta = datetime.strptime(now, frm) - datetime.strptime(credreport[i]['access_key_2_last_used_date'], frm)
                # Verify password have been used in the last 90 days
                if delta.days > 90:
                    result = False
                    failReason = "Credentials unused > 90 days detected. "
                    offenders.append(credreport[i]['arn'] + ":key2")
            except:
                # Never used
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.4 Ensure access keys are rotated every 90 days or less (Scored)
def control_1_4_rotated_keys(credreport):
    """Summary

    Args:
        credreport (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.4"
    description = "Ensure access keys are rotated every 90 days or less"
    scored = True
    # Get current time
    now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time()))
    frm = "%Y-%m-%dT%H:%M:%S+00:00"

    # Look for unused credentails
    for i in range(len(credreport)):
        if credreport[i]['access_key_1_active'] == "true":
            try:
                delta = datetime.strptime(now, frm) - datetime.strptime(credreport[i]['access_key_1_last_rotated'], frm)
                # Verify keys have rotated in the last 90 days
                if delta.days > 90:
                    result = False
                    failReason = "Key rotation >90 days or not used since rotation"
                    offenders.append(credreport[i]['arn'] + ":unrotated key1")
            except:
                pass
            try:
                delta = datetime.strptime(credreport[i]['access_key_1_last_used_date'], frm) - datetime.strptime(credreport[i]['access_key_1_last_rotated'], frm)
                # Verify keys have been used since rotation. Give 1 day buffer.
                if delta.days > 1:
                    result = False
                    failReason = "Key rotation >90 days or not used since rotation"
                    offenders.append(credreport[i]['arn'] + ":unused key1")
            except:
                pass
        if credreport[i]['access_key_2_active'] == "true":
            try:
                delta = datetime.strptime(now, frm) - datetime.strptime(credreport[i]['access_key_2_last_rotated'], frm)
                # Verify keys have rotated in the last 90 days
                if delta.days > 90:
                    result = False
                    failReason = "Key rotation >90 days or not used since rotation"
                    offenders.append(credreport[i]['arn'] + ":unrotated key2")
            except:
                pass
            try:
                delta = datetime.strptime(credreport[i]['access_key_2_last_used_date'], frm) - datetime.strptime(credreport[i]['access_key_2_last_rotated'], frm)
                # Verify keys have been used since rotation. Give 1 day buffer.
                if delta.days > 1:
                    result = False
                    failReason = "Key rotation >90 days or not used since rotation"
                    offenders.append(credreport[i]['arn'] + ":unused key2")
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.5 Ensure IAM password policy requires at least one uppercase letter (Scored)
def control_1_5_password_policy_uppercase(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.5"
    description = "Ensure IAM password policy requires at least one uppercase letter"
    scored = True
    if passwordpolicy['RequireUppercaseCharacters'] is False:
        result = False
        failReason = "Password policy does not require at least one uppercase letter"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.6 Ensure IAM password policy requires at least one lowercase letter (Scored)
def control_1_6_password_policy_lowercase(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.6"
    description = "Ensure IAM password policy requires at least one lowercase letter"
    scored = True
    if passwordpolicy['RequireLowercaseCharacters'] is False:
        result = False
        failReason = "Password policy does not require at least one uppercase letter"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.7 Ensure IAM password policy requires at least one symbol (Scored)
def control_1_7_password_policy_symbol(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.7"
    description = "Ensure IAM password policy requires at least one symbol"
    scored = True
    if passwordpolicy['RequireSymbols'] is False:
        result = False
        failReason = "Password policy does not require at least one symbol"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.8 Ensure IAM password policy requires at least one number (Scored)
def control_1_8_password_policy_number(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.8"
    description = "Ensure IAM password policy requires at least one number"
    scored = True
    if passwordpolicy['RequireNumbers'] is False:
        result = False
        failReason = "Password policy does not require at least one number"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.9 Ensure IAM password policy requires minimum length of 14 or greater (Scored)
def control_1_9_password_policy_length(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.9"
    description = "Ensure IAM password policy requires minimum length of 14 or greater"
    scored = True
    if passwordpolicy['MinimumPasswordLength'] < 14:
        result = False
        failReason = "Password policy does not require at least 14 characters"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.10 Ensure IAM password policy prevents password reuse (Scored)
def control_1_10_password_policy_reuse(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.10"
    description = "Ensure IAM password policy prevents password reuse"
    scored = True
    try:
        if passwordpolicy['PasswordReusePrevention'] == 24:
            pass
        else:
            result = False
            failReason = "Password policy does not prevent reusing last 24 passwords"
    except:
        result = False
        failReason = "Password policy does not prevent reusing last 24 passwords"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.11 Ensure IAM password policy expires passwords within 90 days or less (Scored)
def control_1_11_password_policy_expire(passwordpolicy):
    """Summary

    Args:
        passwordpolicy (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.11"
    description = "Ensure IAM password policy expires passwords within 90 days or less"
    scored = True
    if passwordpolicy['ExpirePasswords'] is True:
        if 0 < passwordpolicy['MaxPasswordAge'] > 90:
            result = False
            failReason = "Password policy does not expire passwords after 90 days or less"
    else:
        result = False
        failReason = "Password policy does not expire passwords after 90 days or less"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.12 Ensure no root account access key exists (Scored)
def control_1_12_root_key_exists(credreport):
    """Summary

    Args:
        credreport (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.12"
    description = "Ensure no root account access key exists"
    scored = True
    if (credreport[0]['access_key_1_active'] == "true") or (credreport[0]['access_key_2_active'] == "true"):
        result = False
        failReason = "Root have active access keys"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.13 Ensure MFA is enabled for the "root" account (Scored)
def control_1_13_root_mfa_enabled():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.13"
    description = "Ensure MFA is enabled for the root account"
    scored = True
    response = IAM_CLIENT.get_account_summary()
    if response['SummaryMap']['AccountMFAEnabled'] != 1:
        result = False
        failReason = "Root account not using MFA"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.14 Ensure hardware MFA is enabled for the "root" account (Scored)
def control_1_14_root_hardware_mfa_enabled():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.14"
    description = "Ensure hardware MFA is enabled for the root account"
    scored = True
    response = IAM_CLIENT.list_virtual_mfa_devices()
    if "mfa/root-account-mfa-device" in str(response['VirtualMFADevices']):
        failReason = "Root account not using hardware MFA"
        result = False
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.15 Ensure security questions are registered in the AWS account (Not Scored/Manual)
def control_1_15_security_questions_registered():
    """Summary

    Returns:
        TYPE: Description
    """
    result = "Manual"
    failReason = ""
    offenders = []
    control = "1.15"
    description = "Ensure security questions are registered in the AWS account, please verify manually"
    scored = False
    failReason = "Control not implemented using API, please verify manually"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.16 Ensure IAM policies are attached only to groups or roles (Scored)
def control_1_16_no_policies_on_iam_users():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.16"
    description = "Ensure IAM policies are attached only to groups or roles"
    scored = True
    response = IAM_CLIENT.list_users(
        #Marker='string',
        #MaxItems=123
    )
    for i in range(len(response['Users'])):
        policies = IAM_CLIENT.list_user_policies(
            UserName=response['Users'][i]['UserName']
            #Marker='string',
            #MaxItems=123
        )
        if policies['PolicyNames'] != []:
            result = False
            failReason = "IAM user have inline policy attached"
            offenders.append(response['Users'][i]['Arn'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.17 Enable detailed billing (Scored)
def control_1_17_detailed_billing_enabled():
    """Summary

    Returns:
        TYPE: Description
    """
    result = "Manual"
    failReason = ""
    offenders = []
    control = "1.17"
    description = "Enable detailed billing, please verify manually"
    scored = True
    failReason = "Control not implemented using API, please verify manually"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.18 Ensure IAM Master and IAM Manager roles are active (Scored)
def control_1_18_ensure_iam_master_and_manager_roles():
    """Summary

    Returns:
        TYPE: Description
    """
    result = "True"
    failReason = "No IAM Master or IAM Manager role created"
    offenders = []
    control = "1.18"
    description = "Ensure IAM Master and IAM Manager roles are active. Control under review/investigation"
    scored = True
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.19 Maintain current contact details (Scored)
def control_1_19_maintain_current_contact_details():
    """Summary

    Returns:
        TYPE: Description
    """
    result = "Manual"
    failReason = ""
    offenders = []
    control = "1.19"
    description = "Maintain current contact details, please verify manually"
    scored = True
    failReason = "Control not implemented using API, please verify manually"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.20 Ensure security contact information is registered (Scored)
def control_1_20_ensure_security_contact_details():
    """Summary

    Returns:
        TYPE: Description
    """
    result = "Manual"
    failReason = ""
    offenders = []
    control = "1.20"
    description = "Ensure security contact information is registered, please verify manually"
    scored = True
    failReason = "Control not implemented using API, please verify manually"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.21 Ensure IAM instance roles are used for AWS resource access from instances (Scored)
def control_1_21_ensure_iam_instance_roles_used():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.21"
    description = "Ensure IAM instance roles are used for AWS resource access from instances, application code is not audited"
    scored = True
    failReason = "Instance not assigned IAM role for EC2"
    response = EC2_CLIENT.describe_instances()
    offenders = []
    for n, _ in enumerate(response['Reservations']):
        try:
            if response['Reservations'][n]['Instances'][0]['IamInstanceProfile']:
                pass
        except:
                result = False
                offenders.append(response['Reservations'][n]['Instances'][0]['InstanceId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.22 Ensure a support role has been created to manage incidents with AWS Support (Scored)
def control_1_22_ensure_incident_management_roles():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.22"
    description = "Ensure a support role has been created to manage incidents with AWS Support"
    scored = True
    offenders = []
    response = IAM_CLIENT.list_entities_for_policy(
        PolicyArn='arn:aws:iam::aws:policy/AWSSupportAccess'
    )
    if (len(response['PolicyGroups']) + len(response['PolicyUsers']) + len(response['PolicyRoles'])) == 0:
        result = False
        failReason = "No user, group or role assigned AWSSupportAccess"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.23 Do not setup access keys during initial user setup for all IAM users that have a console password (Not Scored)
def control_1_23_no_active_initial_access_keys_with_iam_user(credreport):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.23"
    description = "Do not setup access keys during initial user setup for all IAM users that have a console password"
    scored = False
    offenders = []
    for n, _ in enumerate(credreport):
        if (credreport[n]['access_key_1_active'] or credreport[n]['access_key_2_active'] == 'true') and n > 0:
            response = IAM_CLIENT.list_access_keys(
                UserName=str(credreport[n]['user'])
            )
            for m in response['AccessKeyMetadata']:
                if re.sub(r"\s", "T", str(m['CreateDate'])) == credreport[n]['user_creation_time']:
                    result = False
                    failReason = "Users with keys created at user creation time found"
                    offenders.append(credreport[n]['arn']+":"+m['AccessKeyId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 1.24  Ensure IAM policies that allow full "*:*" administrative privileges are not created (Scored)
def control_1_24_no_overly_permissive_policies():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "1.24"
    description = "Ensure a support role has been created to manage incidents with AWS Support"
    scored = True
    offenders = []
    response = IAM_CLIENT.list_policies(
        Scope='Local'
        #Marker='string',
        #MaxItems=123
    )
    for m in response['Policies']:
        policy = IAM_CLIENT.get_policy_version(
            PolicyArn=m['Arn'],
            VersionId=m['DefaultVersionId']
        )
        for n in policy['PolicyVersion']['Document']['Statement']:
            if n['Action'] == "*" and n['Resource'] == "*":
                failReason = "Found *.* policy"
                offenders.append(m['Arn'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# --- 2 Logging ---

# 2.1 Ensure CloudTrail is enabled in all regions (Scored)
def control_2_1_ensure_cloud_trail_all_regions(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "2.1"
    description = "Ensure CloudTrail is enabled in all regions"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            if o['IsMultiRegionTrail']:
                client = boto3.client('cloudtrail', region_name=m)
                response = client.get_trail_status(
                    Name=o['TrailARN']
                )
                if response['IsLogging'] is True:
                    result = True
                    break
    if result is False:
        failReason = "No enabled multi region trails found"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.2 Ensure CloudTrail log file validation is enabled (Scored)
def control_2_2_ensure_cloudtrail_validation(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.2"
    description = "Ensure CloudTrail log file validation is enabled"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            if o['LogFileValidationEnabled'] is False:
                result = False
                failReason = "CloudTrails without log file validation discovered"
                offenders.append(o['TrailARN'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.3 Ensure the S3 bucket CloudTrail logs to is not publicly accessible (Scored)
def control_2_3_ensure_cloudtrail_bucket_not_public(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.3"
    description = "Ensure the S3 bucket CloudTrail logs to is not publicly accessible"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            response = S3_CLIENT.get_bucket_acl(
                Bucket=o['S3BucketName']
            )
            for p in range(len(response['Grants'])):
                try:
                    if re.search(r'(AllUsers|AuthenticatedUsers)', response['Grants'][p]['Grantee']['URI']):
                        result = False
                        failReason = "Publically accessible CloudTrail bucket discovered"
                        offenders.append(str(o['TrailARN']))
                except:
                    pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.4 Ensure CloudTrail trails are integrated with CloudWatch Logs (Scored)
def control_2_4_ensure_cloudtrail_cloudwatch_logs_integration(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.4"
    description = "Ensure CloudTrail trails are integrated with CloudWatch Logs"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if "arn:aws:logs" in o['CloudWatchLogsLogGroupArn']:
                    pass
                else:
                    result = False
                    failReason = "CloudTrails without CloudWatch Logs discovered"
                    offenders.append(o['TrailARN'])
            except:
                result = False
                failReason = "CloudTrails without CloudWatch Logs discovered"
                offenders.append(o['TrailARN'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.5 Ensure AWS Config is enabled in all regions (Scored)
def control_2_5_ensure_config_all_regions(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.5"
    description = "Ensure AWS Config is enabled in all regions"
    scored = True
    globalConfigCapture = False # Only one region needs to capture global events
    for n in regions:
        configClient = boto3.client('config', region_name=n)
        response = configClient.describe_configuration_recorder_status()
        # Get recording status
        try:
            if not response['ConfigurationRecordersStatus'][0]['recording'] is True:
                result = False
                failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
                offenders.append(n + ":NotRecording")
        except:
            result = False
            failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
            offenders.append(n + ":NotRecording")

        # Verify that each region is capturing all events
        response = configClient.describe_configuration_recorders()
        try:
            if not response['ConfigurationRecorders'][0]['recordingGroup']['allSupported'] is True:
                result = False
                failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
                offenders.append(n + ":NotAllEvents")
        except:
            pass # This indicates that Config is disabled in the region and will be captured above.

        # Check if region is capturing global events. Fail is verified later since only one region needs to capture them.
        try:
            if response['ConfigurationRecorders'][0]['recordingGroup']['includeGlobalResourceTypes'] is True:
                globalConfigCapture = True
        except:
            pass

        # Verify the delivery channels
        response = configClient.describe_delivery_channel_status()
        try:
            if response['DeliveryChannelsStatus'][0]['configHistoryDeliveryInfo']['lastStatus'] != "SUCCESS":
                result = False
                failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
                offenders.append(n + ":S3Delivery")
        except:
            pass # Will be captured by earlier rule
        try:
            if response['DeliveryChannelsStatus'][0]['configStreamDeliveryInfo']['lastStatus'] != "SUCCESS":
                result = False
                failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
                offenders.append(n + ":SNSDelivery")
        except:
            pass # Will be captured by earlier rule

    # Verify that global events is captured by any region
    if globalConfigCapture is False:
        result = False
        failReason = "Config not enabled in all regions, not capturing all/global events or delivery channel errors"
        offenders.append("Global:NotRecording")
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.6 Ensure S3 bucket access logging is enabled on the CloudTrail S3 bucket (Scored)
def control_2_6_ensure_cloudtrail_bucket_logging(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.6"
    description = "Ensure S3 bucket access logging is enabled on the CloudTrail S3 bucket"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            response = S3_CLIENT.get_bucket_logging(
                Bucket=o['S3BucketName']
            )
            try:
                if response['LoggingEnabled']:
                    pass
            except:
                result = False
                failReason = "CloudTrail S3 bucket without logging discovered"
                offenders.append(str("Trail:" + o['TrailARN'] + " - S3Bucket:" + o['S3BucketName']))
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.7 Ensure CloudTrail logs are encrypted at rest using KMS CMKs (Scored)
def control_2_7_ensure_cloudtrail_encryption_kms(cloudtrails):
    """Summary

    Args:
        cloudtrails (TYPE): Description

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.6"
    description = "Ensure CloudTrail logs are encrypted at rest using KMS CMKs"
    scored = True
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['KmsKeyId']:
                    pass
            except:
                result = False
                failReason = "CloudTrail not using KMS CMK for encryption discovered"
                offenders.append(str("Trail:" + o['TrailARN']))
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 2.8 Ensure rotation for customer created CMKs is enabled (Scored)
def control_2_8_ensure_kms_cmk_rotation(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "2.8"
    description = "Ensure rotation for customer created CMKs is enabled"
    scored = True
    for n in regions:
        kms_client = boto3.client('kms', region_name=n)
        keys = kms_client.list_keys()
        for i in range(len(keys['Keys'])):
            try:
                rotationStatus = kms_client.get_key_rotation_status(
                    KeyId=keys['Keys'][i]['KeyId'])
                if rotationStatus['KeyRotationEnabled'] is False:
                    keyDescription = kms_client.describe_key(KeyId=keys['Keys'][i]['KeyId'])
                    if not "Default master key that protects my" in keyDescription['KeyMetadata']['Description']: # Ignore service keys
                        result = False
                        failReason = "CloudTrail not using KMS CMK for encryption discovered"
                        offenders.append(str("Key:" + keyDescription['KeyMetadata']['Arn']))
            except:
                pass # Ignore keys without permission, for example ACM key
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# --- Monitoring ---

# 3.1 Ensure a log metric filter and alarm exist for unauthorized API calls (Scored)
def control_3_1_ensure_log_metric_filter_unauthorized_api_calls(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.1"
    description = "Ensure log metric filter unauthorized api calls"
    scored = True
    failReason = "Incorrect log metric alerts for unauthorized_api_calls"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.errorCode = \"*UnauthorizedOperation\") || ($.errorCode = \"AccessDenied*\") }" in str(p['filterPattern']):
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.2 Ensure a log metric filter and alarm exist for Management Console sign-in without MFA (Scored)
def control_3_2_ensure_log_metric_filter_console_signin_no_mfa(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.2"
    description = "Ensure a log metric filter and alarm exist for Management Console sign-in without MFA"
    scored = True
    failReason = "Incorrect log metric alerts for management console signin without MFA"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = \"ConsoleLogin\") && ($.additionalEventData.MFAUsed != \"Yes\") }" in str(p['filterPattern']):
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.3 Ensure a log metric filter and alarm exist for usage of "root" account (Scored)
def control_3_3_ensure_log_metric_filter_root_usage(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.3"
    description = "Ensure a log metric filter and alarm exist for root usage"
    scored = True
    failReason = "Incorrect log metric alerts for root usage"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ $.userIdentity.type = \\\"Root\\\" && $.userIdentity.invokedBy NOT EXISTS && $.eventType != \\\"AwsServiceEvent\\\" }\" in str(p['filterPattern'])":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.4 Ensure a log metric filter and alarm exist for IAM policy changes  (Scored)
def control_3_4_ensure_log_metric_iam_policy_change(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.4"
    description = "Ensure a log metric filter and alarm exist for IAM changes"
    scored = True
    failReason = "Incorrect log metric alerts for IAM policy changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{($.eventName=DeleteGroupPolicy)||($.eventName=DeleteRolePolicy)||($.eventName=DeleteUserPolicy)||($.eventName=PutGroupPolicy)||($.eventName=PutRolePolicy)||($.eventName=PutUserPolicy)||($.eventName=CreatePolicy)||($.eventName=DeletePolicy)||($.eventName=CreatePolicyVersion)||($.eventName=DeletePolicyVersion)||($.eventName=AttachRolePolicy)||($.eventName=DetachRolePolicy)||($.eventName=AttachUserPolicy)||($.eventName=DetachUserPolicy)||($.eventName=AttachGroupPolicy)||($.eventName=DetachGroupPolicy)}":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.5 Ensure a log metric filter and alarm exist for CloudTrail configuration changes (Scored)
def control_3_5_ensure_log_metric_cloudtrail_configuration_changes(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.5"
    description = "Ensure a log metric filter and alarm exist for IAM policy changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for IAM policy changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = CreateTrail) || ($.eventName = UpdateTrail) || ($.eventName = DeleteTrail) || ($.eventName = StartLogging) || ($.eventName = StopLogging) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.6 Ensure a log metric filter and alarm exist for AWS Management Console authentication failures (Scored)
def control_3_6_ensure_log_metric_console_auth_failures(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.6"
    description = "Ensure a log metric filter and alarm exist for console auth failures"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for console auth failures"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = ConsoleLogin) && ($.errorMessage = \\\"Failed authentication\\\") }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.7 Ensure a log metric filter and alarm exist for disabling or scheduled deletion of customer created CMKs (Scored)
def control_3_7_ensure_log_metric_disabling_scheduled_delete_of_kms_cmk(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.7"
    description = "Ensure a log metric filter and alarm exist for disabling or scheduling deletion of KMS CMK"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for disabling or scheduling deletion of KMS CMK"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{($.eventSource = kms.amazonaws.com) && (($.eventName=DisableKey)||($.eventName=ScheduleKeyDeletion))} }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.8 Ensure a log metric filter and alarm exist for S3 bucket policy changes (Scored)
def control_3_8_ensure_log_metric_s3_bucket_policy_changes(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.8"
    description = "Ensure a log metric filter and alarm exist for S3 bucket policy changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for S3 bucket policy changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventSource = s3.amazonaws.com) && (($.eventName = PutBucketAcl) || ($.eventName = PutBucketPolicy) || ($.eventName = PutBucketCors) || ($.eventName = PutBucketLifecycle) || ($.eventName = PutBucketReplication) || ($.eventName = DeleteBucketPolicy) || ($.eventName = DeleteBucketCors) || ($.eventName = DeleteBucketLifecycle) || ($.eventName = DeleteBucketReplication)) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.9 Ensure a log metric filter and alarm exist for AWS Config configuration changes (Scored)
def control_3_9_ensure_log_metric_config_configuration_changes(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.9"
    description = "Ensure a log metric filter and alarm exist for for AWS Config configuration changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for for AWS Config configuration changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{($.eventSource = config.amazonaws.com) && (($.eventName=StopConfigurationRecorder)||($.eventName=DeleteDeliveryChannel)||($.even tName=PutDeliveryChannel)||($.eventName=PutConfigurationRecorder))}":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.10 Ensure a log metric filter and alarm exist for security group changes (Scored)
def control_3_10_ensure_log_metric_security_group_changes(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.10"
    description = "Ensure a log metric filter and alarm exist for security group changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for security group changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = AuthorizeSecurityGroupIngress) || ($.eventName = AuthorizeSecurityGroupEgress) || ($.eventName = RevokeSecurityGroupIngress) || ($.eventName = RevokeSecurityGroupEgress) || ($.eventName = CreateSecurityGroup) || ($.eventName = DeleteSecurityGroup)}":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.11 Ensure a log metric filter and alarm exist for changes to Network Access Control Lists (NACL) (Scored)
def control_3_11_ensure_log_metric_nacl(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.11"
    description = "Ensure a log metric filter and alarm exist for changes to Network Access Control Lists (NACL)"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for changes to Network Access Control Lists (NACL)"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = CreateNetworkAcl) || ($.eventName = CreateNetworkAclEntry) || ($.eventName = DeleteNetworkAcl) || ($.eventName = DeleteNetworkAclEntry) || ($.eventName = ReplaceNetworkAclEntry) || ($.eventName = ReplaceNetworkAclAssociation) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.12 Ensure a log metric filter and alarm exist for changes to network gateways (Scored)
def control_3_12_ensure_log_metric_changes_to_network_gateways(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.12"
    description = "Ensure a log metric filter and alarm exist for changes to network gateways"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for changes to network gateways"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = CreateCustomerGateway) || ($.eventName = DeleteCustomerGateway) || ($.eventName = AttachInternetGateway) || ($.eventName = CreateInternetGateway) || ($.eventName = DeleteInternetGateway) || ($.eventName = DetachInternetGateway) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.13 Ensure a log metric filter and alarm exist for route table changes (Scored)
def control_3_13_ensure_log_metric_changes_to_route_tables(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.13"
    description = "Ensure a log metric filter and alarm exist for route table changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for route table changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = CreateRoute) || ($.eventName = CreateRouteTable) || ($.eventName = ReplaceRoute) || ($.eventName = ReplaceRouteTableAssociation) || ($.eventName = DeleteRouteTable) || ($.eventName = DeleteRoute) || ($.eventName = DisassociateRouteTable) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.14 Ensure a log metric filter and alarm exist for VPC changes (Scored)
def control_3_14_ensure_log_metric_changes_to_vpc(cloudtrails):
    """Summary

    Returns:
        TYPE: Description
    """
    result = False
    failReason = ""
    offenders = []
    control = "3.14"
    description = "Ensure a log metric filter and alarm exist for VPC changes"
    scored = True
    failReason = "Ensure a log metric filter and alarm exist for VPC changes"
    for m, n in cloudtrails.iteritems():
        for o in n:
            try:
                if o['CloudWatchLogsLogGroupArn']:
                    group = re.search('log-group:(.+?):', o['CloudWatchLogsLogGroupArn']).group(1)
                    client = boto3.client('logs', region_name=m)
                    filters = client.describe_metric_filters(
                        logGroupName=group
                    )
                    for p in filters['metricFilters']:
                        if "{ ($.eventName = CreateVpc) || ($.eventName = DeleteVpc) || ($.eventName = ModifyVpcAttribute) || ($.eventName = AcceptVpcPeeringConnection) || ($.eventName = CreateVpcPeeringConnection) || ($.eventName = DeleteVpcPeeringConnection) || ($.eventName = RejectVpcPeeringConnection) || ($.eventName = AttachClassicLinkVpc) || ($.eventName = DetachClassicLinkVpc) || ($.eventName = DisableVpcClassicLink) || ($.eventName = EnableVpcClassicLink) }":
                            cwclient = boto3.client('cloudwatch', region_name=m)
                            response = cwclient.describe_alarms_for_metric(
                                MetricName=p['metricTransformations'][0]['metricName'],
                                Namespace="CloudTrailMetrics"
                            )
                            snsClient = boto3.client('sns', region_name=m)
                            subscribers = snsClient.list_subscriptions_by_topic(
                                TopicArn=response['MetricAlarms'][0]['AlarmActions'][0]
                                #NextToken='string'
                            )
                            if not len(subscribers['Subscriptions']) == 0:
                                result = True
            except:
                pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 3.15 Ensure appropriate subscribers to each SNS topic (Not Scored)
def control_3_15_verify_sns_subscribers():
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "3.15"
    description = "Ensure appropriate subscribers to each SNS topic, please verify manually"
    scored = False
    failReason = "Control not implemented using API, please verify manually"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# --- Networking ---

# 4.1 Ensure no security groups allow ingress from 0.0.0.0/0 to port 22 (Scored)
def control_4_1_ensure_ssh_not_open_to_world(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.1"
    description = "Ensure no security groups allow ingress from 0.0.0.0/0 to port 22"
    scored = True
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        response = client.describe_security_groups()
        for m in response['SecurityGroups']:
            if "0.0.0.0/0" in str(m['IpPermissions']):
                for o in m['IpPermissions']:
                    try:
                        if int(o['FromPort']) <= 22 <= int(o['ToPort']):
                            result = False
                            failReason = "Found Security Group with port 22 open to the world (0.0.0.0/0)"
                            offenders.append(m['GroupId'])
                    except:
                        if str(o['IpProtocol']) == "-1":
                            result = False
                            failReason = "Found Security Group with port 22 open to the world (0.0.0.0/0)"
                            offenders.append(n+" : "+m['GroupId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 4.2 Ensure no security groups allow ingress from 0.0.0.0/0 to port 3389 (Scored)
def control_4_2_ensure_rdp_not_open_to_world(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.2"
    description = "Ensure no security groups allow ingress from 0.0.0.0/0 to port 3389"
    scored = True
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        response = client.describe_security_groups()
        for m in response['SecurityGroups']:
            if "0.0.0.0/0" in str(m['IpPermissions']):
                for o in m['IpPermissions']:
                    try:
                        if int(o['FromPort']) <= 3389 <= int(o['ToPort']):
                            result = False
                            failReason = "Found Security Group with port 3389 open to the world (0.0.0.0/0)"
                            offenders.append(m['GroupId'])
                    except:
                        if str(o['IpProtocol']) == "-1":
                            result = False
                            failReason = "Found Security Group with port 3389 open to the world (0.0.0.0/0)"
                            offenders.append(n+" : "+m['GroupId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 4.3 Ensure VPC flow logging is enabled in all VPCs (Scored)
def control_4_3_ensure_flow_logs_enabled_on_all_vpc(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.3"
    description = "Ensure VPC flow logging is enabled in all VPCs"
    scored = True
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        flowlogs = client.describe_flow_logs(
            #NextToken='string',
            #MaxResults=123
        )
        activeLogs = []
        for m in flowlogs['FlowLogs']:
            if "vpc-" in str(m['ResourceId']):
                activeLogs.append(m['ResourceId'])
        vpcs = client.describe_vpcs(
            Filters=[
                {
                    'Name': 'state',
                    'Values': [
                        'available',
                    ]
                },
            ]
        )
        for m in vpcs['Vpcs']:
            if not str(m['VpcId']) in str(activeLogs):
                result = False
                failReason = "VPC without active VPC Flow Logs found"
                offenders.append(n+" : "+m['VpcId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 4.4 Ensure the default security group of every VPC restricts all traffic (Scored)
def control_4_4_ensure_default_security_groups_restricts_traffic(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.4"
    description = "Ensure the default security group of every VPC restricts all traffic"
    scored = True
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        response = client.describe_security_groups(
            Filters=[
                {
                    'Name': 'group-name',
                    'Values': [
                        'default',
                    ]
                },
            ]
        )
        for m in response['SecurityGroups']:
            if not (len(m['IpPermissions']) + len(m['IpPermissionsEgress'])) == 0:
                result = False
                failReason = "Default security groups with ingress or egress rules discovered"
                offenders.append(n+" : "+m['GroupId'])
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# 4.5 Ensure routing tables for VPC peering are "least access" (Not Scored)
def control_4_5_ensure_route_tables_are_least_access(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.5"
    description = "Ensure routing tables for VPC peering are least access"
    scored = False
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        response = client.describe_route_tables()
        for m in response['RouteTables']:
            for o in m['Routes']:
                try:
                    if o['VpcPeeringConnectionId']:
                        if int(str(o['DestinationCidrBlock']).split("/",1)[1]) < 24:
                            result = False
                            failReason = "Large CIDR block routed to peer discovered, please investigate"
                            offenders.append(n+" : "+m['RouteTableId'])
                except:
                    pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}



# 4.5 Ensure routing tables for VPC peering are "least access" (Not Scored)
def control_4_5_ensure_route_tables_are_least_access(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    result = True
    failReason = ""
    offenders = []
    control = "4.5"
    description = "Ensure routing tables for VPC peering are least access"
    scored = False
    for n in regions:
        client = boto3.client('ec2', region_name=n)
        response = client.describe_route_tables()
        for m in response['RouteTables']:
            for o in m['Routes']:
                try:
                    if o['VpcPeeringConnectionId']:
                        if int(str(o['DestinationCidrBlock']).split("/",1)[1]) < 24:
                            result = False
                            failReason = "Large CIDR block routed to peer discovered, please investigate"
                            offenders.append(n+" : "+m['RouteTableId'])
                except:
                    pass
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}


# --- Central functions ---

def get_cred_report():
    """Summary

    Returns:
        TYPE: Description
    """
    x = 0
    status = ""
    while IAM_CLIENT.generate_credential_report()['State'] != "COMPLETE":
        time.sleep(2)
        x += 1
        # If no credentail report is delivered within this time fail the check.
        if x > 10:
            status = "Fail: rootUse - no CredentialReport available."
            break
    if "Fail" in status:
        return status
    response = IAM_CLIENT.get_credential_report()
    report = []
    reader = csv.DictReader(response['Content'].splitlines(), delimiter=',')
    for row in reader:
        report.append(row)
    return report


def get_account_password_policy():
    """Summary

    Returns:
        TYPE: Description
    """
    response = IAM_CLIENT.get_account_password_policy()
    return response['PasswordPolicy']


def get_regions():
    region_response = EC2_CLIENT.describe_regions()
    regions = [region['RegionName'] for region in region_response['Regions']]
    return regions


def get_cloudtrails(regions):
    """Summary

    Returns:
        TYPE: Description
    """
    trails = dict()
    for n in regions:
        client = boto3.client('cloudtrail', region_name=n)
        response = client.describe_trails()
        trails[n] = response['trailList']
    return trails


def set_evaluation(event, annotation):
    """Summary

    Args:
        event (TYPE): Description
        annotation (TYPE): Description

    Returns:
        TYPE: Description
    """
    configClient = boto3.client('config')
    if len(annotation) > 0:
        configClient.put_evaluations(
            Evaluations=[
                {
                    'ComplianceResourceType': 'AWS::::Account',
                    'ComplianceResourceId': event['accountId'],
                    'ComplianceType': 'NON_COMPLIANT',
                    'Annotation': 'Failed controls: ' + str(annotation),
                    'OrderingTimestamp': event['notificationCreationTime']
                },
            ],
            ResultToken=event['resultToken']
            )
    else:
        configClient.put_evaluations(
            Evaluations=[
                {
                    'ComplianceResourceType': 'AWS::::Account',
                    'ComplianceResourceId': event['accountId'],
                    'ComplianceType': 'COMPLIANT',
                    'OrderingTimestamp': event['notificationCreationTime']
                },
            ],
            ResultToken=event['resultToken']
            )


def json2html(controlResult):
    """Summary

    Args:
        controlResult (TYPE): Description

    Returns:
        TYPE: Description
    """
    table = []
    shortReport = shortAnnotation(controlResult)
    table.append("<html>\n<head>\n<style>\n\n.table-outer {\n    background-color: #eaeaea;\n    border: 3px solid darkgrey;\n}\n\n.table-inner {\n    background-color: white;\n    border: 3px solid darkgrey;\n}\n\n.table-hover tr{\nbackground: transparent;\n}\n\n.table-hover tr:hover {\nbackground-color: lightgrey;\n}\n\ntable, tr, td, th{\n    line-height: 1.42857143;\n    vertical-align: top;\n    border: 1px solid darkgrey;\n    border-spacing: 0;\n    border-collapse: collapse;\n    width: auto;\n    max-width: auto;\n    background-color: transparent;\n    padding: 5px;\n}\n\ntable th {\n    padding-right: 20px;\n    text-align: left;\n}\n\ntd {\n    width:100%;\n}\n\ndiv.centered\n{\n  position: absolute;\n  width: auto;\n  height: auto;\n  z-index: 15;\n  top: 10%;\n  left: 20%;\n  right: 20%;\n  background: white;\n}\n\ndiv.centered table\n{\n    margin: auto;\n    text-align: left;\n}\n</style>\n</head>\n<body>\n<h1 style=\"text-align: center;\">AWS CIS Foundation Framework</h1>\n<div class=\"centered\">")
    table.append("<table class=\"table table-inner\">")
    table.append("<tr><td>Report date: "+time.strftime("%c")+"</td></tr>")
    table.append("<tr><td>Benchmark version: "+AWS_CIS_BENCHMARK_VERSION+"</td></tr>")
    table.append("<tr><td>Whitepaper location: <a href=\"https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf\" target=\"_blank\">https://d0.awsstatic.com/whitepapers/compliance/AWS_CIS_Foundations_Benchmark.pdf</a></td></tr>")
    table.append("<tr><td>"+shortReport+"</td></tr></table><br><br>")
    tableHeadOuter = "<table class=\"table table-outer\">"
    tableHeadInner = "<table class=\"table table-inner\">"
    tableHeadHover = "<table class=\"table table-hover\">"
    table.append(tableHeadOuter) #Outer table
    for n, _ in enumerate(controlResult):
        table.append("<tr><th>"+str(n+1)+"</th><td>"+tableHeadInner)
        for x, _ in enumerate(controlResult[n+1]):
            if str(controlResult[n+1][x+1]['Result']) == "False":
                resultStyle = " style=\"background-color:#ef3d47;\""
            elif str(controlResult[n+1][x+1]['Result']) == "Manual":
                resultStyle = " style=\"background-color:#ffff99;\""
            else:
                resultStyle = " style=\"background-color:lightgreen;\""
            table.append("<tr><th"+resultStyle+">"+str(x+1)+"</th><td>"+tableHeadHover)
            table.append("<tr><th>ControlId</th><td>"+controlResult[n+1][x+1]['ControlId']+"</td></tr>")
            table.append("<tr><th>Description</th><td>"+controlResult[n+1][x+1]['Description']+"</td></tr>")
            table.append("<tr><th>failReason</th><td>"+controlResult[n+1][x+1]['failReason']+"</td></tr>")
            table.append("<tr><th>Offenders</th><td><ul>"+str(controlResult[n+1][x+1]['Offenders']).replace("', ", "',<br>")+"</ul></td></tr>")
            table.append("<tr><th>Result</th><td>"+str(controlResult[n+1][x+1]['Result'])+"</td></tr>")
            table.append("<tr><th>ScoredControl</th><td>"+str(controlResult[n+1][x+1]['ScoredControl'])+"</td></tr>")
            table.append("</table></td></tr>")
        table.append("</table></td></tr>")
    table.append("</table>")
    table.append("</div>\n</body>\n</html>")
    return table


def shortAnnotation(controlResult):
    """Summary

    Args:
        controlResult (TYPE): Description

    Returns:
        TYPE: Description
    """
    annotation = []
    for n in range(len(controlResult)):
        for x in range(len(controlResult[n+1])):
            if controlResult[n+1][x+1]['Result'] is False:
                annotation.append(controlResult[n+1][x+1]['ControlId'])
    # Return JSON
    return "{\"FailedControls\":"+json.dumps(annotation)+"}"


def s3report(htmlReport):
    """Summary

    Args:
        htmlReport (TYPE): Description

    Returns:
        TYPE: Description
    """
    with tempfile.NamedTemporaryFile() as f:
        for item in htmlReport:
            f.write(item)
            f.flush()
        S3_CLIENT.upload_file(f.name, S3_WEB_REPORT_BUCKET, 'report.html')
    ttl = int(S3_WEB_REPORT_EXPIRE) * 60
    signedURL = S3_CLIENT.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': S3_WEB_REPORT_BUCKET,
            'Key': 'report.html'
        },
        ExpiresIn=ttl)
    return signedURL


def lambda_handler(event, context):
    """Summary

    Args:
        event (TYPE): Description
        context (TYPE): Description

    Returns:
        TYPE: Description
    """
    # Run all control validations.
    # The control object is a dictionary with the value
    # result : Boolean - True/False
    # failReason : String - Failure description
    # scored : Boolean - True/False

    if CONFIG_RULE:
        # Verify correct format of event
        try:
            invokingEvent = json.loads(event['invokingEvent'])
        except:
            print str(sys.exc_info()[0])
            invokingEvent = event['invokingEvent']

    # Globally used resources
    region_list = get_regions()
    cred_report = get_cred_report()
    password_policy = get_account_password_policy()
    cloud_trails = get_cloudtrails(region_list)
    
    control1 = dict()
    control1[1] = control_1_1_root_use(cred_report)
    control1[2] = control_1_2_mfa_on_password_enabled_iam(cred_report)
    control1[3] = control_1_3_unused_credentials(cred_report)
    control1[4] = control_1_4_rotated_keys(cred_report)
    control1[5] = control_1_5_password_policy_uppercase(password_policy)
    control1[6] = control_1_6_password_policy_lowercase(password_policy)
    control1[7] = control_1_7_password_policy_symbol(password_policy)
    control1[8] = control_1_8_password_policy_number(password_policy)
    control1[9] = control_1_9_password_policy_length(password_policy)
    control1[10] = control_1_10_password_policy_reuse(password_policy)
    control1[11] = control_1_11_password_policy_expire(password_policy)
    control1[12] = control_1_12_root_key_exists(cred_report)
    control1[13] = control_1_13_root_mfa_enabled()
    control1[14] = control_1_14_root_hardware_mfa_enabled()
    control1[15] = control_1_15_security_questions_registered()
    control1[16] = control_1_16_no_policies_on_iam_users()
    control1[17] = control_1_17_detailed_billing_enabled()
    control1[18] = control_1_18_ensure_iam_master_and_manager_roles()
    control1[19] = control_1_19_maintain_current_contact_details()
    control1[20] = control_1_20_ensure_security_contact_details()
    control1[21] = control_1_21_ensure_iam_instance_roles_used()
    control1[22] = control_1_22_ensure_incident_management_roles()
    control1[23] = control_1_23_no_active_initial_access_keys_with_iam_user(cred_report)
    control1[24] = control_1_24_no_overly_permissive_policies()

    control2 = dict()
    control2[1] = control_2_1_ensure_cloud_trail_all_regions(cloud_trails)
    control2[2] = control_2_2_ensure_cloudtrail_validation(cloud_trails)
    control2[3] = control_2_3_ensure_cloudtrail_bucket_not_public(cloud_trails)
    control2[4] = control_2_4_ensure_cloudtrail_cloudwatch_logs_integration(cloud_trails)
    control2[5] = control_2_5_ensure_config_all_regions(region_list)
    control2[6] = control_2_6_ensure_cloudtrail_bucket_logging(cloud_trails)
    control2[7] = control_2_7_ensure_cloudtrail_encryption_kms(cloud_trails)
    control2[8] = control_2_8_ensure_kms_cmk_rotation(region_list)

    control3 = dict()
    control3[1] = control_3_1_ensure_log_metric_filter_unauthorized_api_calls(cloud_trails)
    control3[1] = control_3_2_ensure_log_metric_filter_console_signin_no_mfa(cloud_trails)
    control3[1] = control_3_3_ensure_log_metric_filter_root_usage(cloud_trails)
    control3[1] = control_3_4_ensure_log_metric_iam_policy_change(cloud_trails)
    control3[1] = control_3_5_ensure_log_metric_cloudtrail_configuration_changes(cloud_trails)
    control3[1] = control_3_6_ensure_log_metric_console_auth_failures(cloud_trails)
    control3[1] = control_3_7_ensure_log_metric_disabling_scheduled_delete_of_kms_cmk(cloud_trails)
    control3[1] = control_3_8_ensure_log_metric_s3_bucket_policy_changes(cloud_trails)
    control3[1] = control_3_9_ensure_log_metric_config_configuration_changes(cloud_trails)
    control3[1] = control_3_10_ensure_log_metric_security_group_changes(cloud_trails)
    control3[1] = control_3_11_ensure_log_metric_nacl(cloud_trails)
    control3[1] = control_3_12_ensure_log_metric_changes_to_network_gateways(cloud_trails)
    control3[1] = control_3_13_ensure_log_metric_changes_to_route_tables(cloud_trails)
    control3[1] = control_3_14_ensure_log_metric_changes_to_vpc(cloud_trails)
    control3[1] = control_3_15_verify_sns_subscribers()

    control4 = dict()
    control4[1] = control_4_1_ensure_ssh_not_open_to_world(region_list)
    control4[2] = control_4_2_ensure_rdp_not_open_to_world(region_list)
    control4[3] = control_4_3_ensure_flow_logs_enabled_on_all_vpc(region_list)
    control4[4] = control_4_4_ensure_default_security_groups_restricts_traffic(region_list)
    control4[5] = control_4_5_ensure_route_tables_are_least_access(region_list)


    # Build JSON reporting structure
    controls = dict()
    controls[1] = control1
    controls[2] = control2
    controls[3] = control3
    controls[4] = control4


    if SCRIPT_OUTPUT_JSON:
        print json.dumps(controls, sort_keys=True, indent=4, separators=(',', ': '))


    if S3_WEB_REPORT:
        htmlReport = json2html(controls)
        if S3_WEB_REPORT_OBFUSCATE_ACCOUNT:
            #for n in range(len(htmlReport)):
            for n, _ in enumerate(htmlReport):
                htmlReport[n] = re.sub(r"\d{12}", "111111111111", htmlReport[n])
        signedURL = s3report(htmlReport)
        print signedURL


    if CONFIG_RULE:
        evalAnnotation = shortAnnotation(controls)
        set_evaluation(invokingEvent, evalAnnotation)

if __name__ == '__main__':
    lambda_handler("test", "test")