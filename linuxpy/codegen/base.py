#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.


import datetime
import logging
import os
import pathlib
import platform
import re
import tempfile
import textwrap
import xml.etree.ElementTree

import black

CTYPES_MAP = {
    "char*": "ccharp",
    "unsigned char": "u8",
    "signed char": "cchar",
    "char": "cchar",
    "short unsigned int": "u16",
    "short int": "i16",
    "unsigned int": "cuint",
    "int": "cint",
    "long unsigned int": "u64",
    "long long unsigned int": "i64",
    "long int": "i64",
    "long long int": "i64",
    "void *": "cvoidp",
    "void": "None",
}

MACRO_RE = re.compile(r"#define[ \t]+(?P<name>[\w]+)[ \t]+(?P<value>.+)\s*")


class CEnum:
    def __init__(self, name, prefixes, klass=None, with_prefix=False, filter=lambda _n, _v: True):
        self.name = name
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        self.prefixes = prefixes
        if klass is None:
            klass = "IntFlag" if any("FLAG" in prefix for prefix in prefixes) else "IntEnum"
        self.klass = klass
        self.with_prefix = with_prefix
        self.values = None
        self.filter = filter

    def add_item(self, name, value):
        if self.empty:
            self.values = []
        self.values.append((name, value))

    @property
    def empty(self):
        return self.values is None

    def __repr__(self):
        if self.values:
            fields = "\n".join(f"    {name} = {value}" for name, value in self.values)
        else:
            fields = "    pass"
        return f"""\
class {self.name}(enum.{self.klass}):
{fields}
"""


class CStruct:
    def __init__(self, node, node_members, pack=False):
        self.node = node
        self.node_members = node_members
        self.pack = pack
        self.name = node.get("name")
        self.parent = None
        self.fields = []
        self.children = {}
        self.is_anonymous = not self.name
        self.anonymous_fields = []

    @property
    def type(self):
        return self.node.tag

    @property
    def id(self):
        return self.node.get("id")

    @property
    def member_ids(self):
        return self.node.get("members").split()

    @property
    def context_id(self):
        return self.node.get("context")

    @property
    def class_text(self):
        text = f"class {self.name}({self.type}):\n"
        if self.pack:
            text += "    _pack_ = True\n"
        if self.children:
            children = "\n".join(str(child) for child in self.children.values())
            text += textwrap.indent(children, 4 * " ")
            text += "\n"
        if self.anonymous_fields:
            text += f"    _anonymous_ = {tuple(self.anonymous_fields)}\n"
        if not any((self.pack, self.children, self.anonymous_fields)):
            text += "    pass"
        return text

    @property
    def fields_text(self):
        fields = ", ".join(f'("{fname}", {ftype})' for fname, ftype in self.fields)
        return f"{self.name}._fields_ = [{fields}]"

    def __repr__(self):
        return f"{self.class_text}\n{self.fields_text}\n"


def lines(filename):
    with open(filename) as source:
        for line in source:
            yield line.strip()


def macro_lines(filename):
    for line in lines(filename):
        if line.startswith("#define"):
            matches = MACRO_RE.match(line)
            if matches:
                data = matches.groupdict()
                yield data["name"], data["value"]


def decode_macro_value(value, context, name_map):
    value = value.replace("*/", "")
    value = value.replace("/*", "#")
    value = value.replace("struct ", "")
    value = value.replace("(1U", "(1")
    value = value.strip()
    for dtype in "ui":
        for size in (8, 16, 32, 64):
            typ = f"{dtype}{size}"
            value = value.replace(f"__{typ}", typ)
    for ctype, pytype in CTYPES_MAP.items():
        value = value.replace(" " + ctype, pytype)
    try:
        return f"0x{int(value):X}"
    except ValueError:
        try:
            return f"0x{int(value, 16):X}"
        except ValueError:
            for c_name, py_name in name_map.items():
                py_class, name = py_name.split(".", 1)
                if py_class == context.name:
                    py_name = name
                value = value.replace(c_name, py_name)
            return value


def find_macro_enum(name, enums):
    for cenum in enums:
        for prefix in cenum.prefixes:
            if prefix in name:
                return cenum, prefix


def fill_macros(filename, name_map, enums):
    for cname, cvalue in macro_lines(filename):
        if "PRIVATE" in cname:
            continue
        cenum = find_macro_enum(cname, enums)
        if cenum is None:
            continue
        cenum, prefix = cenum
        if not cenum.filter(cname, cvalue):
            continue
        py_value = decode_macro_value(cvalue, cenum, name_map)
        py_name = cname[0 if cenum.with_prefix else len(prefix) :]
        if py_name[0].isdigit():
            py_name = f"_{py_name}"
        cenum.add_item(py_name, py_value)
        name_map[cname] = f"{cenum.name}.{py_name}"


def find_xml_base_type(etree, context, type_id):
    while True:
        node = etree.find(f"*[@id='{type_id}']")
        if node is None:
            return
        if node.tag == "Struct":
            return node.get("name"), node.get("id")
        elif node.tag == "FundamentalType":
            return CTYPES_MAP[node.get("name")], node.get("id")
        elif node.tag == "PointerType":
            name, base_id = find_xml_base_type(etree, context, node.get("type"))
            return f"POINTER({name})".format(name), base_id
        elif node.tag == "Union":
            return node.get("name"), node.get("id")
        elif node.tag == "ArrayType":
            name, base_id = find_xml_base_type(etree, context, node.get("type"))
            if name == "u8":
                name = "cchar"
            nmax = node.get("max")
            if nmax:
                n = int(nmax) + 1
                return f"{name} * {n}", base_id
            else:
                return f"POINTER({name})", base_id

        type_id = node.get("type")


def get_structs(header_filename, xml_filename):
    etree = xml.etree.ElementTree.parse(xml_filename)
    header_tag = etree.find(f"File[@name='{header_filename}']")
    structs = {}
    if header_tag is None:
        return structs
    header_id = header_tag.get("id")
    nodes = etree.findall(f"Struct[@file='{header_id}']")
    nodes += etree.findall(f"Union[@file='{header_id}']")
    for node in nodes:
        member_ids = node.get("members").split()
        fields = (etree.find(f"*[@id='{member_id}']") for member_id in member_ids)
        fields = [field for field in fields if field.tag not in {"Union", "Struct", "Unimplemented"}]
        pack = int(node.get("align")) == 8
        struct = CStruct(node, fields, pack)
        structs[struct.id] = struct
    for struct in structs.values():
        if struct.context_id != "_1":
            parent = structs.get(struct.context_id)
            if parent:
                parent.children[struct.id] = struct
                struct.parent = parent
            else:
                logging.error("Could not find parent")
        if not struct.name and struct.parent:
            struct.name = f"M{len(struct.parent.children)}"
    for struct in structs.values():
        for node in struct.node_members:
            name = node.get("name")
            base = find_xml_base_type(etree, struct, node.get("type"))
            if base is None:
                logging.warning("unknown field for %s", struct.name)
            else:
                base_type, base_id = base
                child = struct.children.get(base_id)
                if child is not None:
                    if not name:
                        name = child.name.lower()
                        struct.anonymous_fields.append(name)
                    if not base_type:
                        base_type = f"{struct.name}.{child.name}"
            struct.fields.append((name, base_type))

    return structs


def cname_to_pyname(
    name: str,
    capitalize=True,
    splitby="_",
):
    if name.startswith("v4l2_"):
        name = name[5:]
    if capitalize:
        name = name.capitalize()
    return "".join(map(str.capitalize, name.split(splitby)))


def get_enums(header_filename, xml_filename, enums):
    etree = xml.etree.ElementTree.parse(xml_filename)
    header_tag = etree.find(f"File[@name='{header_filename}']")
    structs = {}
    if header_tag is None:
        return structs
    header_id = header_tag.get("id")
    nodes = etree.findall(f"Enumeration[@file='{header_id}']")
    for node in nodes:
        cname = node.get("name")
        py_name = cname_to_pyname(cname)
        prefix = cname.upper() + "_"
        raw_names = [child.get("name") for child in node]
        common_prefix = os.path.commonprefix(raw_names)
        values = []
        for child in node:
            name = child.get("name")
            name = name.removeprefix(prefix)
            name = name.removeprefix(common_prefix)
            if "PRIVATE" in name:
                continue
            if name[0].isdigit():
                name = f"_{name}"
            value = int(child.get("init"))
            values.append((name, value))
        enum = CEnum(py_name, prefix)
        enum.values = values
        enums.append(enum)


def run(name, headers, template, macro_enums, output=None):
    cache = {}
    temp_dir = tempfile.mkdtemp()
    logging.info("Starting %s...", name)
    structs = []
    for header in headers:
        logging.info("  Building %s for %s...", header, name)
        fill_macros(header, cache, macro_enums)
        base_header = os.path.split(os.path.splitext(header)[0])[1]
        xml_filename = os.path.join(temp_dir, base_header + ".xml")
        cmd = f"castxml --castxml-output=1.0.0 -o {xml_filename} {header}"
        assert os.system(cmd) == 0
        new_structs = get_structs(header, xml_filename)
        structs += list(new_structs.values())

        get_enums(header, xml_filename, macro_enums)

    structs_definition = "\n\n".join(struct.class_text for struct in structs if struct.parent is None)
    structs_fields = "\n".join(struct.fields_text for struct in structs if struct.parent is None)

    structs_body = "\n\n".join(str(struct) for struct in structs if struct.parent is None)
    enums_body = "\n\n".join(str(enum) for enum in macro_enums if "IOC" not in enum.name)
    iocs_body = "\n\n".join(str(enum) for enum in macro_enums if "IOC" in enum.name)

    fields = {
        "name": name,
        "date": datetime.datetime.now(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "enums_body": enums_body,
        "structs_body": structs_body,
        "structs_definition": structs_definition,
        "structs_fields": structs_fields,
        "iocs_body": iocs_body,
    }
    text = template.format(**fields)
    logging.info("  Applying black to %s...", name)
    text = black.format_str(text, mode=black.FileMode())
    logging.info("  Writting %s...", name)
    if output is None:
        print(text)
    else:
        output = pathlib.Path(output)
        with output.open("w") as fobj:
            print(text, file=fobj)
    logging.info("Finished %s!", name)
