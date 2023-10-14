from .core import iter_devices


def lsusb():
    for dev in iter_devices():
        print(
            f"Bus {dev.bus_number:03d} Device {dev.device_address:03d}: ID {dev.vendor_id:04x}:{dev.product_id:04x} {dev.manufacturer} {dev.product}"
        )


if __name__ == "__main__":
    lsusb()
