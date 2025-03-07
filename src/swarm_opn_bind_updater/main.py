import os
import sys
import threading
import time
import argparse
import logging

import dotenv

import re
import json
import requests
import docker

LOGGER = logging.getLogger(__name__)

CONFIG_API_GW_URL = "GW_API_URL"

CONFIG_API_KEY = "GW_API_KEY"
CONFIG_API_SECRET = "GW_API_SECRET"

def reconfigure_bind_controller(api_key, api_secret, api_gw_url):
    headers = {
        "Content-Type" : "application/json"
    }
    payload = { }
    url = "".join([api_gw_url, "/api/bind/service/reconfigure"])
    response = requests.post(url=url, auth=(api_key, api_secret), headers=headers, json=payload)

    if response.status_code != 200:
        _handle_response(response, "Failed to reconfigure bind service")
    
    result = response.json()
    if result["status"] != "ok":
        raise Exception("Bind service responded with unexpected result : {}".format(result))
    
    return result

def search_domain(api_key, api_secret, api_gw_url, domain_name):
    """
    Searches the bind api for a domain by its name

    Parameters
    -----------
    api_key : str
        The API key used for authentication
    api_secret : str
        The API secred used for authentication
    base_url : str
        The base URL for accessing the OPNSense API. This is an URL without path
        Example: "https://fw.example.org"
    domain_name : str
        The name of the domain to search for.
        Example: "example.org"

    Returns
    -------
    str
        The record id or None, if the record could not be found
    """

    url = "".join([api_gw_url, "/api/bind/domain/get"])
    response = requests.get(url, auth=(api_key, api_secret))

    if response.status_code != 200:
        _handle_response(response,"Failed to read domains")
    
    payload = response.json()
    domains = payload["domain"]["domains"]["domain"]

    for domain_id, domain in domains.items():
        if domain["domainname"] != domain_name:
            continue

        if domain["enabled"] != "1":
            LOGGER.warning("Domain %s is not enabled", domain["domainname"])
            continue

        return domain_id

    return None        

def search_record(api_key, api_secret, api_gw_url, domain_name, record_type, record_name):
    """
    Searches the bind API for a record matching domain name, record type and record name

    Parameters
    ----------
    api_key : str
        The API key used for authentication
    api_secret : str
        The API secred used for authentication
    base_url : str
        The base URL for accessing the OPNSense API. This is an URL without path
        Example: "https://fw.example.org"
    domain_name : str
        The domain to search for
    record_type : str
        The record type to search for.
        Example: "A", "PTR, "CNAME", etc.
    record_name : str
        The name to search for

    Returns
    -------
    str
        The record id or None, if the record could not be found

    """
    headers = {
        "Content-Type" : "application/json"
    }
    request_payload = {
        "current" : 1,
        "rowCount" : 50,
        "sort" : {
            "type" : "asc"
        },
        "searchPhrase" : record_name,
        "domain" : search_domain(api_key, api_secret, api_gw_url, domain_name)
    }
    url = "".join([api_gw_url, "/api/bind/record/searchRecord"])

    response = requests.post(url=url, auth=(api_key, api_secret), headers=headers, json=request_payload)

    if response.status_code != 200:
        _handle_response(response, "Failed to search record {} with type {} in domain {}".format(record_name, record_type, domain_name))
    
    response_payload = response.json()
    for item in response_payload["rows"]:
        name = item["name"]
        type = item["type"]
        uuid = item["uuid"]

        if name != record_name:
            continue

        if type != record_type:
            LOGGER.warning("Record %s is already mapped to record type %s", record_name, record_type)
            
        LOGGER.info("Record %s has uuid %s", record_name, uuid)
        return uuid
    
    return None

def add_record(api_key, api_secret, api_gw_url, domain_id, name, record_type, value):
    """
    Add a new record to the bind dns database via bind API

    The record will be added with type CNAME to the given domain

    Parameters
    ----------
    api_key : str
        The API key used for authentication
    api_secret : str
        The API secred used for authentication
    base_url : str
        The base URL for accessing the OPNSense API. This is an URL without path
        Example: "https://fw.example.org"
    domain_id : str
        The id of the domain this record should be added to
    name
        The name of the newly created record
    record_type
        The type of the newly created record
    value
        The value of the newly created record

    Raises
    ------
    Exception
        If an error occoured accessing the bind API
    """
    headers = {
        "Content-Type" : "application/json"
    }
    payload = _create_record_payload(domain_id, name, record_type, value)
    url = "".join([api_gw_url, "/api/bind/record/addRecord"])

    response = requests.post(url=url, auth=(api_key, api_secret), headers=headers, json=payload)

    if response.status_code != 200:
        _handle_response(response, "Failed to add host")

    result = response.json()
    if result["result"] != "saved":
        raise Exception("Failed to add host \"{}\" to domain id \"{}\" : {}".format(name, domain_id, result))
    
    return result

def remove_record(api_key, api_secret, api_gw_url, record_id):
    """
    Remove a record from the bind dns database via bind API

    Parameters
    ----------
    api_key : str
        The API key used for authentication
    api_secret : str
        The API secred used for authentication
    base_url : str
        The base URL for accessing the OPNSense API. This is an URL without path
        Example: "https://fw.example.org"
    record_id : str
        The id of the record to be deleted

    Raises
    ------
    Exception
        If an error occoured accessing the bind API
    """

    url = "".join([api_gw_url, "/api/bind/record/delRecord/", record_id])

    response = requests.post(url=url, auth=(api_key, api_secret), json={})

    if response.status_code != 200:
        _handle_response(response, "Failed to remove host")
    
    result = response.json()
    if result["result"] != "deleted":
        raise Exception("Failed to remove host: {}".format(result))
    
    return result
    
def remove_host_by_domain_and_name(api_key, api_secret, api_gw_url, domain_name, record_name, record_type):
    """
    Remove a record from the bind dns database via bind API

    The record will be identified by its domain name and its record name.
    The record type will be implicitly assumed to be "CNAME"

    Parameters
    ----------
    api_key : str
        The API key used for authentication
    api_secret : str
        The API secred used for authentication
    base_url : str
        The base URL for accessing the OPNSense API. This is an URL without path
        Example: "https://fw.example.org"
    domain_name : str
        The domain name the record is assigned to
    record_name : str
        The name of the record to be deleted

    Raises
    ------
    Exception
        If an error occoured accessing the bind API
    """

    domain_id = search_domain(api_key, api_secret, api_gw_url, domain_name)
    if domain_id == None:
        raise Exception("Domain \"{}\" unknown or not enabled".format(domain_name))
    
    record_id = search_record(api_key, api_secret, api_gw_url, domain_name, record_type, record_name)
    if record_id == None:
        raise Exception("Record \"{}\" with type \"{}\" not found under domain \"{}\"".format(record_name, record_type, domain_name))

    return remove_record(api_key, api_secret, api_gw_url, record_id)

# Define pattern for our labels
LABEL_PATTERN = re.compile(r"(com\.aixo\.cloud\.ingress\.mappings)\.(\w+)\.(domain|host|type|value)")

# Repository for active services
ACTIVE_SERVICES = { }

def handle_service_created_event(api_key, api_secret, api_gw_url, api_client : docker.APIClient, service_id):
    # Get service
    service_payload = api_client.inspect_service(service_id)

    # Get spec from service
    service_spec_payload = service_payload["Spec"]

    # Read lables from service spec
    labels_paylod = service_spec_payload["Labels"]

    # Preset host records to add
    host_records = { }

    # Collect host records
    for label_payload, value in labels_paylod.items():
        # Match label to our label pattern
        result = LABEL_PATTERN.match(label_payload)

        # Check if one of our label was found
        if not result:
            LOGGER.debug("Ignoring label %s", label_payload)
            continue

        # Check if a value was given
        if not value:
            LOGGER.error("Label %s does not have a value", label_payload)

        # Extract label parts
        selector = result.group(2)
        key = result.group(3)

        # Get host record by selector or create a new one
        host_record = host_records.get(selector, { })

        # Add host attribute
        host_record[key] = value

        # Store back host record
        host_records[selector] = host_record

    # Process host records
    for selector, host_record in host_records.items():
        if not host_record.get("domain"):
            LOGGER.error("Failed to read domain name label on service %s", service_id)
            continue

        if not host_record.get("host"):
            LOGGER.error("Failed to read host label on service %s", service_id)
            continue

        if not host_record.get("type"):
            LOGGER.error("Failed to read type label on service %s", service_id)
            continue

        if not host_record.get("value"):
            LOGGER.error("Failed to read value label on service %s", service_id)
            continue

        host_record["domain_id"] = search_domain(api_key, api_secret, api_gw_url, host_record.get("domain"))

        if not host_record.get("domain_id"):
            LOGGER.warning("Could not find domain id for domain %s on service %s", host_record.get("domain"), service_id)

        # Only add a new record to the OPNSense if it does not already exist
        host_record["id"] = search_record(api_key, api_secret, api_gw_url, host_record.get("domain"), host_record.get("type"), host_record.get("host"))
        if not host_record.get("id"):
            result = add_record(api_key, api_secret, api_gw_url, host_record.get("domain_id"), host_record.get("host"), host_record.get("type"), host_record.get("value"))
            host_record["id"] = result.get("uuid")
            LOGGER.info("Added bind record %s", host_record)
        else:
            LOGGER.warning("For service %s, host record %s already exists on domain %s", service_id, host_record, host_record.get("domain"))

        service = {
            "id" : service_id,
            "record" : host_record
        }
        
        ACTIVE_SERVICES[service_id] = service
        LOGGER.info("Added service %s", service)

def service_removed(api_key, api_secret, api_gw_url, service_id):
    service = ACTIVE_SERVICES.get(service_id)
    if not service:
        LOGGER.error("No active service found for service id %s", service_id)
        return
    
    record_id = service["record"]["id"]
    
    try:
        remove_record(api_key, api_secret, api_gw_url, record_id)
        LOGGER.info("Removed bind record %s", service.get("record"))
    except Exception as ex:
        LOGGER.warning(str(ex))
                  
    ACTIVE_SERVICES.pop(service_id, None)
    LOGGER.info("Removed service %s", service)

def process_docker_events(api_key, api_secret, api_gw_url, docker_url):
    docker_client = docker.DockerClient(base_url=docker_url)
    api_client = docker_client.api

    LOGGER.info("Created docker client")

    docker_events = docker_client.events(
        filters={
            "type" : "service"
        }
    )
    LOGGER.info("Created event stream")
  
    try:
        LOGGER.info("Listening for events...")

        for raw_event in docker_events:
            event = json.loads(raw_event)
            
            action = event["Action"]
            service_id = event["Actor"]["ID"]

            match action:
                case "create":
                    handle_service_created_event(api_key, api_secret, api_gw_url, api_client, service_id)
                    reconfigure_bind_controller(api_key, api_secret, api_gw_url)


                case "remove":
                    service_removed(api_key, api_secret, api_gw_url, service_id)
                    reconfigure_bind_controller(api_key, api_secret, api_gw_url)
    
    except KeyboardInterrupt:
        print("")
        LOGGER.warning("Received SIGINT")

    docker_events.close()
    LOGGER.info("Closed event stream")

    docker_client.close()
    LOGGER.info("Closed docker client")

def _create_record_payload(domain_id, name, type, value):
    return {
        "record" : {
            "enabled" : "1",
            "domain"  : domain_id,
            "name"    : name,
            "type"    : type,
            "value"   : value
        }
    }

def _handle_response(response : requests.Response, message):
    if not 'application/json' in response.headers.get('Content-Type', ''):
        if response.text != None and response.text != "":
            raise Exception("{} - {}: {}".format(response.status_code, message, response.text))
        else:
            raise Exception("{} - {}".format(response.status_code, message))
            
    raise Exception("{} - {}: {}".format(response.status_code, message, response.json()))

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        prog='opnsense_bind',
        description='Manages opnsense bind service DNS records',
        add_help=True
    )
    parser.add_argument("-u", "--url", help="The base URL to the opnsense router")

    command_parser = parser.add_subparsers(
        title="commands",
        help="record commands",
        dest="command",
        required=True
    )

    add_parser = command_parser.add_parser(
        "add",
        help="Add a record"
    )
    add_parser.add_argument("-d", "--domain", help="the domain of the record", required=True)
    add_parser.add_argument("-n", "--name", help="the name of the record", required=True)
    add_parser.add_argument("-t", "--type", help="the type of the record, e.g. A or CNAME", required=True)
    add_parser.add_argument("-v", "--value", help="the value of the record, e.g. 192.168.1.1", required=True)

    remove_parser = command_parser.add_parser(
        "remove",
        help="Remove a record"
    )
    remove_parser.add_argument("-d", "--domain", help="the domain of the record", required=True)
    remove_parser.add_argument("-n", "--name", help="the name of the record", required=True)
    remove_parser.add_argument("-t", "--type", help="the type of the record, e.g. A or CNAME", required=True)

    reconfigure_parser = command_parser.add_parser(
        "reconfigure",
        help="Reconfigure the bind service"
    )

    docker_parser = command_parser.add_parser(
        "events",
        help="Listen and process docker events"
    )

    args = parser.parse_args()

    dotenv.load_dotenv()
    LOGGER.info("Loaded environment")

    try:
        match args.command:
            case "add":
                name = args.name
                domain = args.domain
                record_type = args.type
                value = args.value

                domain_id = search_domain(os.environ[CONFIG_API_KEY], os.environ[CONFIG_API_SECRET], os.environ[CONFIG_API_GW_URL], domain)
                result = add_record(os.environ[CONFIG_API_KEY], os.environ[CONFIG_API_SECRET], os.environ[CONFIG_API_GW_URL], domain_id, name, record_type, value)
                print(result)

            case "remove":
                domain = args.domain
                name = args.name
                record_type = args.type

                result = remove_host_by_domain_and_name(os.environ[CONFIG_API_KEY], os.environ[CONFIG_API_SECRET], os.environ[CONFIG_API_GW_URL], domain, name, record_type)
                print(result)

            case "reconfigure":
                result = reconfigure_bind_controller(os.environ[CONFIG_API_KEY], os.environ[CONFIG_API_SECRET], os.environ[CONFIG_API_GW_URL])
                print(result)
    
            case "events":
                process_docker_events(os.environ[CONFIG_API_KEY], os.environ[CONFIG_API_SECRET], os.environ[CONFIG_API_GW_URL], os.environ["DOCKER_HOST"])

    except Exception as ex:
        parser.exit(1, str(ex) + "\n")

if __name__ == "__main__":
    main()
