from .core import iter_devices


def lsusb():
    for dev in iter_devices():
        desc = dev.descriptors
        vendor = desc.vendor_name or dev.manufacturer
        product = desc.product_name or dev.product
        print(
            f"Bus {dev.bus_number:03d} Device {dev.device_number:03d}: ID {desc.vendor_id:04x}:{desc.product_id:04x} {vendor} {product}"
        )


if __name__ == "__main__":
    lsusb()
