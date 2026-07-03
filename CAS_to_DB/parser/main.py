from parser import XMIParser
from importer import Importer
from database import Session

parser = XMIParser("bundestag_full.xmi").parse()

db = Session()

Importer(parser, db).run()