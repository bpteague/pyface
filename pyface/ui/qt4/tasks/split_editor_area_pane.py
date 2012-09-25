# Standard library imports.
import sys

# Enthought library imports.
from pyface.tasks.i_editor_area_pane import IEditorAreaPane, \
    MEditorAreaPane
from traits.api import implements, on_trait_change, Instance, List

# System library imports.
from pyface.qt import QtCore, QtGui
from pyface.action.api import Action, Group
from pyface.tasks.editor import Editor
from traitsui.api import Menu

# Local imports.
from task_pane import TaskPane
from util import set_focus
from canopy.ui.widget_events import ContextMenuEvent, set_context_menu_emit
from encore.events.api import BaseEventManager

###############################################################################
# 'SplitEditorAreaPane' class.
###############################################################################

class SplitEditorAreaPane(TaskPane, MEditorAreaPane):
    """ The toolkit-specific implementation of a SplitEditorAreaPane.

    See the IEditorAreaPane interface for API documentation.
    """

    implements(IEditorAreaPane)

    #### SplitEditorAreaPane interface #############################################

    # Currently active tabwidget
    active_tabwidget = Instance(QtGui.QTabWidget)

    # tree based layout object 
    #layout = Instance(EditorAreaLayout) 

    ###########################################################################
    # 'TaskPane' interface.
    ###########################################################################

    def create(self, parent):
        """ Create and set the toolkit-specific control that represents the
            pane.
        """
        # Create and configure the Editor Area Widget.
        self.control = SplitAreaWidget(self, parent)
        self.active_tabwidget = self.control.tabwidget()
        self.drag_info = {}

        # handle application level focus changes
        QtGui.QApplication.instance().focusChanged.connect(self._focus_changed)

        # handle context menu events to display split/collapse actions
        em = self.task.window.application.get_service(BaseEventManager)
        em.connect(ContextMenuEvent, func=self.on_context_menu)

        # set key bindings
        self.set_key_bindings()

    def destroy(self):
        """ Destroy the toolkit-specific control that represents the pane.
        """        
        for editor in self.editors:
            self.remove_editor(editor)

        super(SplitEditorAreaPane, self).destroy()

    ###########################################################################
    # 'IEditorAreaPane' interface.s
    ###########################################################################

    def activate_editor(self, editor):
        """ Activates the specified editor in the pane.
        """
        self.active_editor = editor
        editor.control.setFocus()
        editor.control.raise_()
        self.active_tabwidget = editor.control.parent().parent()
        self.active_tabwidget.setCurrentWidget(editor.control)
        
    def add_editor(self, editor):
        """ Adds an editor to the active_tabwidget
        """
        editor.editor_area = self
        editor.create(self.active_tabwidget)
        index = self.active_tabwidget.addTab(editor.control, self._get_label(editor))
        self.active_tabwidget.setTabToolTip(index, editor.tooltip)
        self.editors.append(editor)

    def remove_editor(self, editor):
        """ Removes an editor from the associated tabwidget
        """
        self.editors.remove(editor)
        tabwidget = editor.control.parent().parent()
        assert isinstance(tabwidget, QtGui.QTabWidget)
        tabwidget.removeTab(tabwidget.indexOf(editor.control))
        editor.destroy()
        editor.editor_area = None
        if not self.editors:
            self.active_editor = None


    ##########################################################################
    # 'SplitEditorAreaPane' interface.
    ##########################################################################

    def get_layout(self):
        """ Returns a LayoutItem that reflects the current state of the 
        tabwidgets in the split framework.
        """
        return self.control.get_layout()


    def set_layout(self, layout):
        """ Applies a LayoutItem to the tabwidgets in the pane.
        """
        self.control.set_layout(layout)

    ###########################################################################
    # Protected interface.
    ###########################################################################

    def _get_label(self, editor):
        """ Return a tab label for an editor.
        """
        label = editor.name
        if editor.dirty:
            label = '*' + label
        return label

    def _get_editor(self, editor_widget):
        """ Returns the editor corresponding to editor_widget
        """
        for editor in self.editors:
            if editor.control is editor_widget:
                return editor
        return None

    def set_key_bindings(self):
        """ Set keyboard shortcuts for tabbed navigation
        """
        # Add shortcuts for scrolling through tabs.
        if sys.platform == 'darwin':
            next_seq = 'Ctrl+}'
            prev_seq = 'Ctrl+{'
        elif sys.platform.startswith('linux'):
            next_seq = 'Ctrl+PgDown'
            prev_seq = 'Ctrl+PgUp'
        else:
            next_seq = 'Alt+n'
            prev_seq = 'Alt+p'
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(next_seq), self.control)
        shortcut.activated.connect(self._next_tab)
        shortcut = QtGui.QShortcut(QtGui.QKeySequence(prev_seq), self.control)
        shortcut.activated.connect(self._previous_tab)

        # Add shortcuts for switching to a specific tab.
        mod = 'Ctrl+' if sys.platform == 'darwin' else 'Alt+'
        mapper = QtCore.QSignalMapper(self.control)
        mapper.mapped.connect(self._activate_tab)
        for i in xrange(1, 10):
            sequence = QtGui.QKeySequence(mod + str(i))
            shortcut = QtGui.QShortcut(sequence, self.control)
            shortcut.activated.connect(mapper.map)
            mapper.setMapping(shortcut, i - 1)

    def _activate_tab(self, index):
        """ Activates the tab with the specified index, if there is one.
        """
        self.active_tabwidget.setCurrentIndex(index)

    def _next_tab(self):
        """ Activate the tab after the currently active tab.
        """
        index = self.active_tabwidget.currentIndex()
        new_index = index + 1 if index < self.active_tabwidget.count() - 1 else 0
        self.active_tabwidget.setCurrentIndex(new_index)

    def _previous_tab(self):
        """ Activate the tab before the currently active tab.
        """
        index = self.active_tabwidget.currentIndex()
        new_index = index - 1 if index > 0  else self.active_tabwidget.count() - 1
        self.active_tabwidget.setCurrentIndex(new_index)

    #### Trait change handlers ################################################

    @on_trait_change('editors:[dirty, name]')
    def _update_label(self, editor, name, new):
        index = self.active_tabwidget.indexOf(editor.control)
        self.active_tabwidget.setTabText(index, self._get_label(editor))

    @on_trait_change('editors:tooltip')
    def _update_tooltip(self, editor, name, new):
        index = self.active_tabwidget.indexOf(editor.control)
        self.active_tabwidget.setTabToolTip(index, self._get_label(editor))

    #### Signal handlers ######################################################

    def _focus_changed(self, old, new):
        """ Handle an application-level focus change to set the active_tabwidget
        """
        if new:
            if isinstance(new, DraggableTabWidget):
                self.active_tabwidget = new
            elif isinstance(new, QtGui.QTabBar):
                self.active_tabwidget = new.parent()
            else:
                # check if any of the editor widgets (or their focus proxies) have
                # focus. If yes, make it active
                for editor in self.editors:
                    # hasFocus is True if control or it's focusproxy has focus
                    if editor.control.hasFocus():
                        self.activate_editor(editor)
                        break


    def on_context_menu(self, event):
        """ Adds split/collapse context menu actions
        """
        if isinstance(event.source, QtGui.QTabWidget):
            tabwidget = event.source
        elif isinstance(event.source, Editor):
            tabwidget = event.source.control.parent().parent()
        else:
            return

        splitter = tabwidget.parent()

        # add this group only if it has not been added before
        if not event.menu.find_group(id='split'):
            # add split actions (only show for non-empty tabwidgets)
            if not splitter.is_empty():
                actions = [Action(id='split_hor', name='Split horizontally', 
                           on_perform=lambda : splitter.split(orientation=
                            QtCore.Qt.Horizontal)),
                           Action(id='split_ver', name='Split vertically', 
                           on_perform=lambda : splitter.split(orientation=
                            QtCore.Qt.Vertical))]

                splitgroup = Group(*actions, id='split')
                event.menu.append(splitgroup)

        # add this group only if it has not been added before
        if not event.menu.find_group(id='collapse'):
            # add collapse action (only show for collapsible splitters)
            if splitter.is_collapsible():
                actions = [Action(id='merge', name='Collapse split', 
                            on_perform=lambda : splitter.collapse())]

                collapsegroup = Group(*actions, id='collapse')
                event.menu.append(collapsegroup)


###############################################################################
# Auxillary classes.
###############################################################################

class SplitAreaWidget(QtGui.QSplitter):
    """ Container widget to hold a QTabWidget which are separated by other 
    QTabWidgets via splitters.  
    
    An SplitAreaWidget is essentially a Node object in the editor area layout 
    tree.
    """

    def __init__(self, editor_area, parent=None, tabwidget=None):
        """ Creates an SplitAreaWidget object.

        editor_area : global SplitEditorAreaPane instance
        parent : parent splitter
        tabwidget : tabwidget object contained by this splitter

        """
        super(SplitAreaWidget, self).__init__(parent=parent)
        self.editor_area = editor_area
        
        if not tabwidget:
            tabwidget = DraggableTabWidget(editor_area=self.editor_area, parent=self)

        # add the tabwidget to the splitter
        self.addWidget(tabwidget)
        
        # Initializes left and right children to None (since no initial splitter
        # children are present) 
        self.leftchild = None 
        self.rightchild = None

    def get_layout(self):
        """ Returns the layout of the current splitter node in the following dict 
        format:
        {
        'leftchild': similar layout for left child if it has one, else None,
        'rightchild': similar layout for left child if it has one, else None,
        'orientation': QtCore.Qt.Horizontal or QtCore.Qt.Vertical orientation, 
        'sizes': sizes of it's children (width for horizontal splitter, 
                height for vertical)
        'editor_states': editor states for open editors on current tabwidget (None, 
            if self is a non-leaf splitter)
        'currentIndex': currently active index (if leaf, else None)
        }
        """
        orientation_code = {QtCore.Qt.Horizontal: 'h', 
                            QtCore.Qt.Vertical: 'v'}

        return {'leftchild'    : (None if self.is_leaf() else 
                                  self.leftchild.get_layout()),
                'rightchild'   : (None if self.is_leaf() else 
                                  self.rightchild.get_layout()),
                'orientation'  :  orientation_code[self.orientation()],
                'sizes'         : self.sizes(),
                'editor_states': (None if not self.is_leaf() else 
                                  self.tabwidget().get_editor_states()),
                'currentIndex' : (None if not self.is_leaf() else 
                                  self.tabwidget().currentIndex())
                }

    def set_layout(self, layout):
        """ Sets the layout of the current splitter based on layout object
        """
        orientation_decode = {'h': QtCore.Qt.Horizontal, 
                              'v': QtCore.Qt.Vertical}
        # if not a leaf splitter
        if layout['leftchild']:
            self.split(orientation=orientation_decode[layout['orientation']])
            #from IPython.core.debugger import Tracer; Tracer()()
            self.leftchild.set_layout(layout=layout['leftchild'])
            self.rightchild.set_layout(layout=layout['rightchild'])
            self.setSizes(layout['sizes'])

        # if it is a leaf splitter 
        else:
            # sets the current tabwidget active, so that the files open in this 
            # tabwidget only
            self.editor_area.active_tabwidget = self.tabwidget()
            # open necessary files
            for editor_state in layout['editor_states']:
                self.editor_area.task.edit(editor_state[0], editor_factory=None, 
                                        **editor_state[1])
            # make appropriate widget active
            self.tabwidget().setCurrentIndex(layout['currentIndex'])

    def tabwidget(self):
        """ Obtain the tabwidget associated with current SplitAreaWidget
        """
        for child in self.children():
            if isinstance(child, QtGui.QTabWidget):
                return child
        return None

    def brother(self):
        """ Returns another child of its parent. Returns None if it can't find any 
        brother.
        """
        parent = self.parent()

        if self.is_root():
            return None

        if self is parent.leftchild:
            return parent.rightchild
        elif self is parent.rightchild:
            return parent.leftchild

    def is_root(self):
        """ Returns True if the current SplitAreaWidget is the root widget.
        """
        parent = self.parent()
        if isinstance(parent, SplitAreaWidget):
            return False
        else:
            return True

    def is_leaf(self):
        """ Returns True if the current SplitAreaWidget is a leaf, i.e., it has a 
        tabwidget as one of it's immediate child.
        """
        # a leaf has it's leftchild and rightchild None
        if not self.leftchild and not self.rightchild:
            return True
        return False

    def is_empty(self):
        """ Returns True if the current splitter's tabwidget doesn't contain any 
        tab.
        """
        return not bool(self.tabwidget().count())

    def is_collapsible(self):
        """ Returns True if the current splitter can be collapsed to its brother, i.e.
        if it is a) either empty, or b) it has a brother which is a leaf.
        """
        if self.is_root():
            return False
        
        if self.is_empty():
            return True
        
        parent = self.parent()
        brother = self.brother()
            
        if brother.is_leaf():
            return True
        else:
            return False

    def split(self, orientation=QtCore.Qt.Horizontal):
        """ Split the current splitter into two children splitters. The tabwidget is 
        moved to the left child while a new empty tabwidget is added to the right 
        child.
        
        orientation : whether to split horizontally or vertically
        """
        # set splitter orientation
        self.setOrientation(orientation)
        orig_size = self.sizes()[0]

        # create new children
        self.leftchild = SplitAreaWidget(self.editor_area, tabwidget=self.tabwidget())
        self.rightchild = SplitAreaWidget(self.editor_area, tabwidget=None)

        # add newly generated children
        self.addWidget(self.leftchild)
        self.addWidget(self.rightchild)

        # set equal sizes of splits
        self.setSizes([orig_size/2,orig_size/2])
        
        # make the rightchild's tabwidget active
        self.editor_area.active_tabwidget = self.rightchild.tabwidget()

    def collapse(self):
        """ Collapses the current splitter and its brother splitter to their 
        parent splitter. Merges together the tabs of both's tabwidgets. 

        Does nothing if the current splitter is not collapsible.
        """
        if not self.is_collapsible():
            return 

        parent = self.parent()
        brother = self.brother()

        # this will happen only if self is empty, else it will not be collapsible at all
        if brother and (not brother.is_leaf()):
            parent.setOrientation(brother.orientation())
            # reparent brother's children to parent
            parent.addWidget(brother.leftchild)
            parent.addWidget(brother.rightchild)
            parent.leftchild = brother.leftchild
            parent.rightchild = brother.rightchild
            self.deleteLater()
            brother.deleteLater()
            return

        # save original currentwidget to make active later
        # (if one of them is empty, make the currentwidget of brother active)
        orig_currentWidget = (self.tabwidget().currentWidget() or \
                            brother.tabwidget().currentWidget())

        left = parent.leftchild.tabwidget()
        right = parent.rightchild.tabwidget()
        target = DraggableTabWidget(editor_area=self.editor_area, parent=parent)

        # add tabs of left and right tabwidgets to target
        for source in (left, right):
            # Note: addTab removes widgets from source tabwidget, so 
            # grabbing all the source widgets beforehand
            widgets = [source.widget(i) for i in range(source.count())]
            for editor_widget in widgets:
                editor = self.editor_area._get_editor(editor_widget)
                target.addTab(editor_widget, 
                            self.editor_area._get_label(editor))                    

        # add target to parent
        parent.addWidget(target)

        # make target the new active tabwidget and make the original focused widget
        # active in the target too
        self.editor_area.active_tabwidget = target
        target.setCurrentWidget(orig_currentWidget)


        # remove parent's splitter children
        self.deleteLater()
        brother.deleteLater()
        parent.leftchild = None
        parent.rightchild = None
    

class DraggableTabWidget(QtGui.QTabWidget):
    """ Implements a QTabWidget with event filters for tab drag and drop
    """

    def __init__(self, editor_area, parent):
        """ 
        editor_area : global SplitEditorAreaPane instance
        parent : parent of the tabwidget
        """
        super(DraggableTabWidget, self).__init__(parent)
        self.editor_area = editor_area

        # configure QTabWidget
        self.setTabBar(DraggableTabBar(editor_area=editor_area, parent=self))
        self.setDocumentMode(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFocusProxy(None)
        self.setMovable(False) # handling move events myself
        self.setTabsClosable(True)
        self.setUsesScrollButtons(True)

        # set drop and context menu policies
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)

        # connecting signals
        self.tabCloseRequested.connect(self._close_requested)

    def get_names(self):
        """ Utility function to return names of all the editors open in the 
        current tabwidget.
        """
        names = []
        for i in range(self.count()):
            editor_widget = self.widget(i)
            editor = self.editor_area._get_editor(editor_widget)
            names.append(editor.name)
        return names

    def get_editor_states(self):
        """ Utility function to return editor_states by calling get_editor_args
        on all the editors open in the current tabwidget.
        """
        editor_states = []
        for i in range(self.count()):
            editor_widget = self.widget(i)
            editor = self.editor_area._get_editor(editor_widget)
            if callable(getattr(editor, 'get_editor_args', None)):
                # NOTE: get_editor_args() method must return either a jsonable
                # object or a list of which the first element is a jsonable
                # object and the second argument is a dictionary of additional
                # keyword arguments.
                args = editor.get_editor_args()
                if args is not None:
                    if not isinstance(args, list):
                        args = [args, {}]
                    editor_states.append(args)
        return editor_states


    ###### Signal handlers #####################################################

    def _close_requested(self, index):
        """ Re-implemented to close the editor when it's tab is closed
        """
        #from IPython.core.debugger import Tracer; Tracer()()
        # grab the editor widget
        editor_widget = self.widget(index)
        
        # remove tab
        self.removeTab(index)
        
        # collapse if necessary
        if self.count()==0:
            self.parent().collapse()

        # close editor
        editor = self.editor_area._get_editor(editor_widget)
        editor.close()

    ##### Event handlers #######################################################

    def contextMenuEvent(self, event):
        """ To fire ContextMenuEvent even on empty tabwidgets
        """
        parent = self.parent()
        if parent.is_empty():
            menu = Menu()
            em = (self.editor_area.task.window.application.
                    get_service(BaseEventManager))
            evt = ContextMenuEvent(source=self, widget=parent, 
                                pos=event.pos(), menu=menu)
            em.emit(evt)
            qmenu = menu.create_menu(self)
            qmenu.show()
        return super(DraggableTabWidget, self).contextMenuEvent(event)            

    def dragEnterEvent(self, event):
        """ Re-implemented to handle drag enter events 
        """
        if self.editor_area.drag_info:
            event.acceptProposedAction()
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

        return super(DraggableTabWidget, self).dropEvent(event)

    def dropEvent(self, event):
        """ Re-implemented to handle drop events
        """
        # accept drops only if a drag is active
        if self.editor_area.drag_info:
            # extract drag info
            from_index = self.editor_area.drag_info['from_index'] 
            widget = self.editor_area.drag_info['widget']
            from_tabwidget = self.editor_area.drag_info['from_tabwidget']

            # extract drag widget label
            editor = self.editor_area._get_editor(widget)
            label = self.editor_area._get_label(editor)

            # if drop occurs at a tab bar, insert the tab at that position
            if not self.tabBar().tabAt(event.pos())==-1:
                index = self.tabBar().tabAt(event.pos())
                self.insertTab(index, widget, label)

            else:
                # if the drag initiated from the same tabwidget, put the tab 
                # back at the original index
                if self is from_tabwidget:
                    self.insertTab(from_index, widget, label)
                # else, just add it at the end
                else:
                    self.addTab(widget, label)
            
            # make the dropped widget active
            self.setCurrentWidget(widget)

            # Note: insertTab/addTab automatically remove tab from source tabwidget
            # However, we want that if we remove the last tab from source, we should 
            # also collapse that unnecessary split
            if from_tabwidget.count()==0:
                from_tabwidget.parent().collapse()

            # empty out drag info, making the drag inactive again
            self.editor_area.drag_info = {}
            event.acceptProposedAction()

        # handle file drops events
        if event.mimeData().hasUrls():
            # Build list of accepted files.
            extensions = tuple(self.editor_area.file_drop_extensions)
            file_paths = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.endswith(extensions):
                    file_paths.append(file_path)

            # dispatch file drop event
            for file_path in file_paths:
                self.editor_area.file_dropped = file_path


class DraggableTabBar(QtGui.QTabBar):
    """ Implements a QTabBar with event filters for tab drag and drop
    """
    def __init__(self, editor_area, parent):
        super(DraggableTabBar, self).__init__(parent)
        self.editor_area = editor_area

    def mousePressEvent(self, event):
        if event.button()==QtCore.Qt.LeftButton:
            self.editor_area.drag_info['start_pos'] = event.pos()
            self.editor_area.drag_info['from_index'] = from_index = self.tabAt(event.pos())
            self.editor_area.drag_info['widget'] = widget = self.parent().widget(from_index)
            self.editor_area.drag_info['from_tabwidget'] = self.parent()
            self.editor_area.drag_info['pixmap'] = QtGui.QPixmap.grabWidget(widget)
        return super(DraggableTabBar, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # is the left mouse button still pressed?
        if not event.buttons()==QtCore.Qt.LeftButton:
            pass
        # has the mouse been dragged for sufficient distance?
        if ((event.pos() - self.editor_area.drag_info['start_pos']).manhattanLength()
            < QtGui.QApplication.startDragDistance()):
            pass
        # initiate drag
        else:
            drag = QtGui.QDrag(self.editor_area.drag_info['widget'])
            mimedata = QtCore.QMimeData()
            drag.setPixmap(self.editor_area.drag_info['pixmap'])
            drag.setMimeData(mimedata)
            drag.exec_()
            return True
        return super(DraggableTabBar, self).mouseMoveEvent(event)
