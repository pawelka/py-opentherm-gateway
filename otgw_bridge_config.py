config = {
    "otgw" : {
        "host": "192.168.2.202",
        "port": "23",
        "thermostatFirst": True
    },
    "mqtt" : {
        "host": "192.168.2.20",
        "port": 1883,
        "username": None,
        "password": None,
        "value_topic_namespace": "value/otgw",
        "set_topic_namespace": "set/otgw",
        "qos": 0,
        "retain": False
    },
    "oled" : {
        "host": "192.168.2.202"
    }
}
