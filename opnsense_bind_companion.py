import logging
import dotenv
import requests

LOGGER = logging.getLogger(__name__)

def load_configuration():
    return dotenv.dotenv_values(".env")

CONFIG = load_configuration()

GW_BASE_URL = CONFIG["GW_BASE_URL"]

GW_API_KEY = CONFIG["GW_API_KEY"]
GW_API_SECRET = CONFIG["GW_API_SECRET"]

DNS_NAME_INGRESS = "camina"
DNS_TYPE = "CNAME"

def find_domain(api_key, api_secret, base_url, domain_name):
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

    url = "".join([base_url, "/api/bind/domain/get"])
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

def search_record(api_key, api_secret, base_url, domain_name, record_type, record_name):
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
        "domain" : find_domain(domain_name)
    }
    url = "".join([base_url, "/api/bind/record/searchRecord"])

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

def add_record(api_key, api_secret, base_url, domain_id, name):
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

    Raises
    ------
    Exception
        If an error occoured accessing the bind API
    """
    headers = {
        "Content-Type" : "application/json"
    }
    payload = _create_record_payload(domain_id, name, "CNAME", DNS_NAME_INGRESS)
    url = "".join([base_url, "/api/bind/record/addRecord"])

    response = requests.post(url=url, auth=(api_key, api_secret), headers=headers, json=payload)

    if response.status_code != 200:
        _handle_response(response, "Failed to add host")

    result = response.json()
    if result["result"] != "saved":
        raise Exception("Failed to add host {} to domain id {} : {}".format(name, domain_id, result))

def remove_record(api_key, api_secret, base_url, record_id):
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

    url = "".join([base_url, "/api/bind/record/delRecord/", record_id])

    response = requests.post(url=url, auth=(api_key, api_secret), json={})

    if response.status_code != 200:
        _handle_response(response, "Failed to remove host")
    
    result = response.json()
    if result["result"] != "deleted":
        raise Exception("Failed to remove host: {}".format(result))
    
def remove_host_by_domain_and_name(api_key, api_secret, base_url, domain_name, record_name):
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

    domain_id = find_domain(api_key, api_secret, base_url, domain_name)
    if domain_id == None:
        raise Exception("Domain {} unknown or not enabled".format(domain_name))
    
    record_id = search_record(api_key, api_secret, base_url, domain_name, record_name)
    if record_id == None:
        raise Exception("Record {} with type {} not found under domain {}".format(record_name, DNS_TYPE, domain_name))

    remove_record(api_key, api_secret, base_url, record_id)

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
