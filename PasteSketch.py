#Author-Robin Debreuil
#Description-'Pastes sketch curves, constraints, parameters and dimesions. Optionally choose a guideline to allow transformed pasting if a guideline was selected while copying.'

import adsk.core, adsk.fusion, traceback
from .lib.TurtleUtils import TurtleUtils
from .lib.TurtleUICommand import TurtleUICommand
from .lib.TurtleSketch import TurtleSketch
from .lib.SketchDecoder import SketchDecoder
from .lib.data.SketchData import SketchData

f,core,app,ui,design,root = TurtleUtils.initGlobals()

class PasteSketchCommand(TurtleUICommand):
    def __init__(self):
        cmdId = 'ddwPasteSketchId'
        cmdName = 'Paste Sketch'
        cmdDescription = 'Pastes sketch curves, constraints, parameters and dimesions. Optionally choose a guideline to allow transformed pasting if a guideline was selected while copying.'
        targetPanels = self.getTargetPanels()
        super().__init__(cmdId, cmdName, cmdDescription, False, targetPanels)

    def getTargetPanels(self):
        return ui.allToolbarPanels.itemById('SolidCreatePanel'), ui.allToolbarPanels.itemById('SketchCreatePanel')

    def onCreated(self, eventArgs:core.CommandCreatedEventArgs):
        try:
            self.isInSketch = app.activeEditObject.classType == f.Sketch.classType
            self.guideline:f.SketchLine = TurtleUtils.getSelectedTypeOrNone(f.SketchLine)
            if self.guideline:
                self.sketch = self.guideline.parentSketch
            else:
                self.sketch:f.Sketch = TurtleUtils.getTargetSketch(f.Sketch, False)
            self.decoder = None
            self.selectedProfileIndex = 0
            self.tabIndex = 0
                
            # Get the CommandInputs collection associated with the command.
            topLevelInputs = eventArgs.command.commandInputs

            tabCmdInput1 = topLevelInputs.addTabCommandInput('tabSelection', 'Target')
            inputs = tabCmdInput1.children

            # Select optional guideline.
            self.guidelineSelection = inputs.addSelectionInput('selGuideline', 'Select Guideline', 'Optional reference guideline used if transforming sketch.')
            self.guidelineSelection.setSelectionLimits(0, 0)
            self.guidelineSelection.addSelectionFilter('SketchLines')

            # Select sketch.
            self.sketchSelection = inputs.addSelectionInput('selSketch', 'Select Sketch', 'Select sketch to copy.')
            self.sketchSelection.setSelectionLimits(0,0)
            self.sketchSelection.addSelectionFilter('Sketches')

            self.sketchText = inputs.addTextBoxCommandInput('txSketch', 'Select Sketch', '<b>Auto selected.</b>', 1, True)

            # Flip checkboxes
            self.flipHSelection = inputs.addBoolValueInput('bFlipH', 'Flip Sketch', True)
            self.flipVSelection = inputs.addBoolValueInput('bFlipV', 'Mirror Sketch', True)

            if self.sketch and not self.guideline:
                tSketch = TurtleSketch.createWithSketch(self.sketch)
                lines = tSketch.getSingleLines()
                if(len(lines) == 1):
                    self.guideline = lines[0]

            # use a separate tab for profiles, this should solve the multiple kinds of selections issues
            tabCmdInput2 = topLevelInputs.addTabCommandInput('tabProfiles', 'Profiles')
            inputs = tabCmdInput2.children
            self.radioProfiles = inputs.addRadioButtonGroupCommandInput('radioProfiles', 'Named Profiles')
            self.radioProfiles.isFullWidth = True

            if self.sketch:
                self.sketchSelection.addSelection(self.sketch)

            self.resetUI()
        except:
            print('Failed:\n{}'.format(traceback.format_exc()))
        
    def onInputsChanged(self, eventArgs:core.InputChangedEventArgs):
        try:
            inputs = eventArgs.inputs
            cmdInput = eventArgs.input
            if cmdInput.id == 'selGuideline':
                if cmdInput.selectionCount > 0:
                    self.guideline = cmdInput.selection(0).entity
                    self.sketch = self.guideline.parentSketch
                    if self.sketchSelection.selectionCount == 0 or self.sketchSelection.selection(0) != self.sketch:
                        self.sketchSelection.clearSelection()
                        self.sketchSelection.addSelection(self.sketch)
                else:
                    self.guideline = None
                self.resetUI()

            elif cmdInput.id == 'selSketch':
                if self.sketchSelection.selectionCount > 0:
                    self.sketch = cmdInput.selection(0).entity
                    if(self.guideline and self.guideline.parentSketch != self.sketch):
                        self.guideline = None
                        self.guidelineSelection.clearSelection()
                else:
                    self.sketch = None
                    self.guideline = None
                    self.guidelineSelection.clearSelection()
                self.resetUI()

            elif cmdInput.id == 'radioProfiles':
                self.selectedProfileIndex = cmdInput.selectedItem.index
                if self.guideline:
                    self.guidelineSelection.clearSelection() # required to trigger preview
                    self.guidelineSelection.addSelection(self.guideline)
                else:
                    self.guidelineSelection.clearSelection() 

            elif cmdInput.id == 'APITabBar':
                self.tabIndex = 1 if self.tabIndex == 0 else 0 # not sure to tell which tab was clicked?
                if self.tabIndex == 0:
                    self._resetSelections()
                    self.resetUI()
                else:
                    self._updateProfiles()
                
        except:
            print('Failed:\n{}'.format(traceback.format_exc()))
      
    def _resetSelections(self):
        ui.activeSelections.clear()
        self.guidelineSelection.clearSelection()
        self.sketchSelection.clearSelection()
        if self.guideline:
            self.guidelineSelection.addSelection(self.guideline)
        elif self.sketch:
            self.sketchSelection.addSelection(self.sketch)

    def _updateProfiles(self):
        radioItems = self.radioProfiles.listItems
        if len(radioItems) == 0:
            radioItems.clear()
            if self.decoder and len(self.decoder.namedProfiles) > 0: 
                for i, name in enumerate(self.decoder.namedProfiles):
                    item = radioItems.add(name, i == self.selectedProfileIndex, 'resources/Profile/16x24.png')

    def onValidateInputs(self, eventArgs:core.ValidateInputsEventArgs):
        eventArgs.areInputsValid = True if self.sketch else False
        
    def onPreview(self, eventArgs:core.CommandEventArgs):
        self.onExecute(eventArgs)
        ui.activeSelections.clear()
        self._resetSelections()
        if self.tabIndex == 1 and self.decoder and len(self.decoder.namedProfiles) > 0:
            indexList = list(self.decoder.namedProfiles.values())
            for profileIndex in indexList[self.selectedProfileIndex]:
                ui.activeSelections.add(self.sketch.profiles[profileIndex])

    def onExecute(self, eventArgs:core.CommandEventArgs):
        data = self.getSketchData()
        flipX = self.flipHSelection.value
        flipY = self.flipVSelection.value
        if self.guideline:
            self.decoder = SketchDecoder.createWithGuideline(data, self.guideline, flipX, flipY)
        else:
            self.decoder = SketchDecoder.createWithSketch(data, self.sketch, flipX, flipY)



    def getSketchData(self):
        result = TurtleUtils.getClipboardText()
        if result == None or not (result.startswith("#Turtle Generated Data")):
            result = SketchData.getTestData()
        else:
            result = eval(result)
        return result
    
    def resetUI(self):
        if self.guideline or self.isInSketch:
            self.sketchSelection.isVisible = False
            self.sketchText.isVisible = True
            self.guidelineSelection.hasFocus = True 
        else:
            self.sketchSelection.isVisible = True
            self.sketchText.isVisible = False
        
        if self.guideline:
            self.flipHSelection.isEnabled = True
            self.flipVSelection.isEnabled = True
        else:
            self.flipHSelection.isEnabled = False
            self.flipVSelection.isEnabled = False

