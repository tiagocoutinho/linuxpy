class Node(dict):
    def __init__(self, nid, name):
        self.id = nid
        self.name = name
        super().__init__()


class Leaf:
    __slots__ = ["id", "name"]

    def __init__(self, lid, name):
        self.id = lid
        self.name = name


class Vendor(Node):
    pass


class Product(Leaf):
    pass


class Class(Node):
    pass


class SubClass(Node):
    pass


class Protocol(Leaf):
    pass


class AudioTerminal(Leaf):
    pass


class HID(Leaf):
    pass


class HIDItem(Leaf):
    pass


class Bias(Leaf):
    pass


class Physical(Leaf):
    pass


class HUTPage(Node):
    pass


class HUT(Leaf):
    pass


class Language(Node):
    pass


class Dialect(Leaf):
    pass


class Country(Leaf):
    pass


class VideoTerminal(Leaf):
    pass
