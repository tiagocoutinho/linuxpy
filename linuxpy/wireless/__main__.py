from linuxpy.proc import wireless

from . import Wireless


def human_size(n: int, unit="b", div=1000, decimals=3) -> str:
    units = ["", "K", "M", "G", "T", "P"]
    template = f"{{:.{decimals}f}} {{}}{unit}"
    for u in units:
        if n < div:
            return template.format(n, u)
        n /= div

    return template.format(n, units[-1])


def human_item(key, item):
    value = item["value"]
    unit = item.get("unit")
    if unit:
        if isinstance(value, list):
            value = "; ".join(human_size(i, unit=unit, decimals=0) for i in value)
        else:
            value = human_size(value, unit=unit)
    else:
        if key == "address":
            value = ":".join(f"{i:02X}" for i in value)
        else:
            value = value.name.capitalize() if hasattr(value, "name") else value
    if key == "essid":
        name = key.upper()
    else:
        name = key.capitalize().replace("_", " ")
    return f"{name}: {value}"


def main():
    with Wireless() as scanner:
        for iw in wireless():
            iwname = iw["interface"]
            result = scanner.scan(iwname)
            print(f"{iwname}  Scan completed :")
            for key, item in result.items():
                text = human_item(key, item)
                print(f"    {text}")


if __name__ == "__main__":
    main()
