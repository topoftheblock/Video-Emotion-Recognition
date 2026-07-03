from lxml import etree
from collections import defaultdict


class XMIParser:

    def __init__(self, filename):
        self.filename = filename

        # xmi:id -> XML Element
        self.by_id = {}

        # typename -> [elements]
        self.by_type = defaultdict(list)

    def parse(self):

        context = etree.iterparse(
            self.filename,
            events=("end",),
            recover=True
        )

        for _, elem in context:

            tag = elem.tag.split("}")[-1]

            xmi_id = elem.attrib.get("{http://www.omg.org/XMI}id")

            if xmi_id:
                self.by_id[xmi_id] = elem

            self.by_type[tag].append(elem)

            elem.clear()

        return self