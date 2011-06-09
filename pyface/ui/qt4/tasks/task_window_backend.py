# System library imports.
from traits.qt import QtCore, QtGui

# Enthought library imports.
from traits.api import Instance, List

# Local imports.
from dock_pane import AREA_MAP
from main_window_layout import MainWindowLayout
from pyface.tasks.i_task_window_backend import MTaskWindowBackend
from pyface.tasks.task_layout import PaneItem, TaskLayout

# Constants.
CORNER_MAP = { 'top_left'     : QtCore.Qt.TopLeftCorner,
               'top_right'    : QtCore.Qt.TopRightCorner,
               'bottom_left'  : QtCore.Qt.BottomLeftCorner,
               'bottom_right' : QtCore.Qt.BottomRightCorner }


class TaskWindowBackend(MTaskWindowBackend):
    """ The toolkit-specific implementation of a TaskWindowBackend.

    See the ITaskWindowBackend interface for API documentation.
    """

    #### Private interface ####################################################

    _main_window_layout = Instance(MainWindowLayout)

    ###########################################################################
    # 'ITaskWindowBackend' interface.
    ###########################################################################

    def create_contents(self, parent):
        """ Create and return the TaskWindow's contents.
        """
        return QtGui.QStackedWidget(parent)

    def hide_task(self, state):
        """ Assuming the specified TaskState is active, hide its controls.
        """
        # Save the task's layout in case it is shown again later.
        self._active_state.layout = self.get_layout()

        # Now hide its controls.
        self.control.centralWidget().removeWidget(state.central_pane.control)
        for dock_pane in state.dock_panes:
            # Warning: The layout behavior is subtly different (and wrong!) if
            # the order of these two statement is switched.
            dock_pane.control.hide()
            self.control.removeDockWidget(dock_pane.control)

    def show_task(self, state):
        """ Assumming no task is currently active, show the controls of the
            specified TaskState.
        """
        # Show the central pane.
        self.control.centralWidget().addWidget(state.central_pane.control)

        # Show the dock panes.
        self._layout_state(state)

        # OSX-specific: if there is only a single tool bar, it doesn't matter if
        # the user can drag it around or not. Therefore, we can combine it with
        # the title bar, which is idiomatic on the Mac.
        self.control.setUnifiedTitleAndToolBarOnMac(
            len(state.tool_bar_managers) <= 1)

    #### Methods for saving and restoring the layout ##########################

    def get_layout(self):
        """ Returns a TaskLayout for the current state of the window.
        """
        self._main_window_layout.state = self.window._active_state
        return self._main_window_layout.get_layout()

    def set_layout(self, layout):
        """ Applies a TaskLayout (which should be suitable for the active task)
            to the window.
        """
        self.window._active_state.layout = layout
        self._layout_state(self.window._active_state)

    ###########################################################################
    # Private interface.
    ###########################################################################

    def _layout_state(self, state):
        """ Layout the dock panes in the specified TaskState using its
            TaskLayout.
        """
        # Assign the window's corners to the appropriate dock areas.
        for name, corner in CORNER_MAP.iteritems():
            area = getattr(state.layout, name + '_corner')
            self.control.setCorner(corner, AREA_MAP[area])

        # Add all panes in the TaskLayout.
        self._main_window_layout.state = state
        self._main_window_layout.set_layout(state.layout)

        # Add all panes not assigned an area by the TaskLayout.
        for dock_pane in state.dock_panes:
            if dock_pane.control not in self._main_window_layout.consumed:
                self.control.addDockWidget(AREA_MAP[dock_pane.dock_area],
                                           dock_pane.control)
                # By default, these dock panes are not visible. But if the
                # developer explicitly requests them to be visible, ensure
                # that they are.
                if dock_pane.visible:
                    dock_pane.control.show()

    #### Trait initializers ###################################################

    def __main_window_layout_default(self):
        return TaskWindowLayout(control=self.control)


class TaskWindowLayout(MainWindowLayout):
    """ A MainWindowLayout for a TaskWindow.
    """

    #### 'TaskWindowLayout' interface #########################################

    consumed = List
    state = Instance('pyface.tasks.task_window.TaskState')

    ###########################################################################
    # 'MainWindowLayout' interface.
    ###########################################################################

    def set_layout(self, layout):
        """ Applies a LayoutContainer consisting of DockAreas.
        """
        self.consumed = []
        super(TaskWindowLayout, self).set_layout(layout)

    ###########################################################################
    # 'MainWindowLayout' abstract interface.
    ###########################################################################

    def _get_dock_widget(self, pane):
        """ Returns the QDockWidget associated with a PaneItem.
        """
        for dock_pane in self.state.dock_panes:
            if dock_pane.id == pane.id:
                self.consumed.append(dock_pane.control)
                return dock_pane.control
        return None

    def _get_pane(self, dock_widget):
        """ Returns a PaneItem for a QDockWidget.
        """
        for dock_pane in self.state.dock_panes:
            if dock_pane.control == dock_widget:
                return PaneItem(id=dock_pane.id)
        return None
