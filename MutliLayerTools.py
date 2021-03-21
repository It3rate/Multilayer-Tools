
import adsk.core, adsk.fusion, traceback, os
from .CopySketch import CopySketchCommand
from .PasteSketch import PasteSketchCommand
from .ExtrudeLayers import ExtrudeLayersCommand
from .lib.CreateShelves import CreateShelves

commandHandles = []
def run(context):
    commandHandles.append(ExtrudeLayersCommand())
    commandHandles.append(CopySketchCommand())
    commandHandles.append(PasteSketchCommand())
    #commandHandles.append(CreateShelves())

def stop(context):
    for cmd in commandHandles:
        cmd.destroyAddinUI()
    commandHandles.clear()
