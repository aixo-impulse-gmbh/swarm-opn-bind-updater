import pytest

from requests_mock import Mocker

import src.swarm_opn_bind_updater.main as main

API_KEY = "myKey"
API_SECRET = "mySecret"

BASE_URL = "https://example.org"

BIND_DOMAIN_GET = "https://example.org/api/bind/domain/get"
BIND_RECORD_ADDRECORD = "https://example.org/api/bind/record/addRecord"
BIND_RECORD_DELRECORD = "https://example.org/api/bind/record/delRecord"

def test_can_create_record_payload():
    domain_id = "dbf3748c-ac5a-4512-8941-4b8c10d3558d"
    name = "heinz"
    type = "CNAME"
    value = "camina"

    expected = {
        "record" : {
            "enabled"   : "1",
            "domain"    : domain_id,
            "name"      : name,
            "type"      : type,
            "value"     : value
        }
    }
    actual = main._create_record_payload(domain_id, name, type, value)

    assert actual == expected

def test_find_domain_id(requests_mock : Mocker):
    domain_id = "e7079f24-aeb7-4741-bd05-e005350bb5bf"
    domain_name = "c.internal"

    payload = {
        "domain" : {
            "domains": {
                "domain" : {
                    domain_id : {
                        "enabled": "1",
                        "domainname": domain_name
                    }
                }
            }
        }
    }
    requests_mock.get(BIND_DOMAIN_GET, json=payload)

    domain_id = main.search_domain(API_KEY, API_SECRET, BASE_URL, domain_name)

    assert domain_id != None
    assert domain_id == "e7079f24-aeb7-4741-bd05-e005350bb5bf"

def test_add_host(requests_mock : Mocker):
    requests_mock.post(url=BIND_RECORD_ADDRECORD, json={ "result" : "saved" })

    main.add_record(API_KEY, API_SECRET, BASE_URL, "dbf3748c-ac5a-4512-8941-4b8c10d3558d", "blog", "CNAME", "www.example.org")

def test_add_host_failed(requests_mock : Mocker):
    requests_mock.post(url=BIND_RECORD_ADDRECORD, status_code=400, text="dah")

    with pytest.raises(Exception) as ex:
        main.add_record(API_KEY, API_SECRET, BASE_URL, "b78013ea-cdaf-4335-b429-7af99b2f9a12", "blog", "CNAME", "www.example.org")

    assert str(ex.value) == "400 - Failed to add host: dah"

def test_remove_host(requests_mock : Mocker):
    record_id = "193d655b-5d41-43ad-9683-9d74b33bf80d"
    url = "".join([BIND_RECORD_DELRECORD, "/", record_id])
    requests_mock.post(url=url, json={ "result" : "deleted" })

    main.remove_record(API_KEY, API_SECRET, BASE_URL, record_id)

def test_remove_host_not_found(requests_mock : Mocker):
    record_id = "e75bd96f-cccc-459c-af77-ccec04319b46"
    url = "".join([BIND_RECORD_DELRECORD, "/", record_id])
    requests_mock.post(url=url, json={ "result" : "not found" })

    with pytest.raises(Exception) as ex:
        main.remove_record(API_KEY, API_SECRET, BASE_URL, record_id)

    assert str(ex.value) == "Failed to remove host: {'result': 'not found'}"

def test_remove_host_failed(requests_mock : Mocker):
    record_id = "3653c244-e1c1-46c3-954f-7d5411bfe95b"
    url = "".join([BIND_RECORD_DELRECORD, "/", record_id])
    requests_mock.post(url=url, status_code=400, json={"status":400,"message":"Invalid JSON syntax"})

    with pytest.raises(Exception) as ex:
        main.remove_record(API_KEY, API_SECRET, BASE_URL, record_id)

    assert str(ex.value) == "400 - Failed to remove host: {\"status\": 400, \"message\": \"Invalid JSON syntax\"}"

def test_remove_host_failed_without_result(requests_mock : Mocker):
    record_id = "38370f5c-3027-414f-9361-da9f9a68d811"
    url = "".join([BIND_RECORD_DELRECORD, "/", record_id])
    requests_mock.post(url=url, status_code=500)

    with pytest.raises(Exception) as ex:
        main.remove_record(API_KEY, API_SECRET, BASE_URL, record_id)

    assert str(ex.value) == "500 - Failed to remove host"
