def hardware_id():
    import ubinascii
    import machine

    machine_id = ubinascii.hexlify(machine.unique_id()).decode("ascii")
    unit_id = "co2unit-%s" % machine_id
    return unit_id

OU_ID_PATH = "conf/ou-id.json"
OU_ID_DEFAULTS = {
            "hw_id": hardware_id(),
            "location_code": None,
        }
