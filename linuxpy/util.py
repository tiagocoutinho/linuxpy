def ichunks(lst, size):
    return (lst[i : i + size] for i in range(0, len(lst), size))


def chunks(lst, size):
    return tuple(ichunks(lst, size))


def bcd_version_tuple(bcd: int):
    text = hex(bcd)[2:]
    if len(text) % 2:
        text = "0" + text
    return tuple(int(i) for i in ichunks(text, 2))


def bcd_version(bcd: int):
    return ".".join(str(i) for i in bcd_version_tuple(bcd))
