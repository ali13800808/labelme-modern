import re

from loguru import logger
from qtpy import QT_VERSION
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

import labelme.utils

QT5 = QT_VERSION[0] == "5"


# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.


class LabelQLineEdit(QtWidgets.QLineEdit):
    def setListWidget(self, list_widget):
        self.list_widget = list_widget

    def keyPressEvent(self, e):
        if e.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            self.list_widget.keyPressEvent(e)
        else:
            super(LabelQLineEdit, self).keyPressEvent(e)
            # Update text direction after key press
            self._update_text_direction()

    def _update_text_direction(self):
        """Automatically detect and set text direction based on content"""
        text = self.text()

        if not text:
            # Empty field: use LTR as default
            self.setLayoutDirection(QtCore.Qt.LeftToRight)
            self.setAlignment(QtCore.Qt.AlignLeft)
        elif self._contains_rtl(text):
            # Contains RTL characters: switch to RTL
            self.setLayoutDirection(QtCore.Qt.RightToLeft)
            self.setAlignment(QtCore.Qt.AlignRight)
        else:
            # Only LTR characters: use LTR
            self.setLayoutDirection(QtCore.Qt.LeftToRight)
            self.setAlignment(QtCore.Qt.AlignLeft)

    def _contains_rtl(self, text):
        """Check if text contains RTL characters (Persian, Arabic, Hebrew)"""
        for char in text:
            if "\u0600" <= char <= "\u06FF":  # Arabic/Persian
                return True
            if "\u0750" <= char <= "\u077F":  # Arabic Supplement
                return True
            if "\u0590" <= char <= "\u05FF":  # Hebrew
                return True
            if "\uFB50" <= char <= "\uFDFF":  # Arabic Presentation Forms-A
                return True
            if "\uFE70" <= char <= "\uFEFF":  # Arabic Presentation Forms-B
                return True
        return False


class LabelQTextEdit(QtWidgets.QTextEdit):
    """QTextEdit with automatic RTL/LTR detection"""

    def __init__(self, *args, **kwargs):
        super(LabelQTextEdit, self).__init__(*args, **kwargs)
        self._updating_direction = False
        self.textChanged.connect(self._update_text_direction)

    def _update_text_direction(self):
        # setAlignment() edits the document, which emits textChanged again and
        # would re-enter this slot without end (stack overflow on Windows).
        if self._updating_direction:
            return
        self._updating_direction = True
        try:
            self._apply_text_direction()
        finally:
            self._updating_direction = False

    def _apply_text_direction(self):
        """Automatically detect and set text direction based on content"""
        text = self.toPlainText()

        if not text:
            # Empty field: use LTR as default
            self.setLayoutDirection(QtCore.Qt.LeftToRight)
            self.setAlignment(QtCore.Qt.AlignLeft)
        elif self._contains_rtl(text):
            # Contains RTL characters: switch to RTL
            self.setLayoutDirection(QtCore.Qt.RightToLeft)
            self.setAlignment(QtCore.Qt.AlignRight)
        else:
            # Only LTR characters: use LTR
            self.setLayoutDirection(QtCore.Qt.LeftToRight)
            self.setAlignment(QtCore.Qt.AlignLeft)

    def _contains_rtl(self, text):
        """Check if text contains RTL characters (Persian, Arabic, Hebrew)"""
        for char in text:
            if "\u0600" <= char <= "\u06FF":  # Arabic/Persian
                return True
            if "\u0750" <= char <= "\u077F":  # Arabic Supplement
                return True
            if "\u0590" <= char <= "\u05FF":  # Hebrew
                return True
            if "\uFB50" <= char <= "\uFDFF":  # Arabic Presentation Forms-A
                return True
            if "\uFE70" <= char <= "\uFEFF":  # Arabic Presentation Forms-B
                return True
        return False


class LabelDialog(QtWidgets.QDialog):
    def __init__(
        self,
        text="Enter object label",
        parent=None,
        labels=None,
        sort_labels=True,
        show_text_field=True,
        completion="startswith",
        fit_to_content=None,
        flags=None,
    ):
        if fit_to_content is None:
            fit_to_content = {"row": False, "column": True}
        self._fit_to_content = fit_to_content

        super(LabelDialog, self).__init__(parent)
        self.edit = LabelQLineEdit()
        # Enable bidirectional text support (RTL + LTR)
        self.edit.setCursorPosition(0)
        self.edit.setPlaceholderText(text)
        self.edit.setValidator(labelme.utils.labelValidator())
        self.edit.editingFinished.connect(self.postProcess)
        if flags:
            self.edit.textChanged.connect(self.updateFlags)
        self.edit_group_id = QtWidgets.QLineEdit()
        self.edit_group_id.setPlaceholderText("Group ID")
        self.edit_group_id.setValidator(
            QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None)
        )
        layout = QtWidgets.QVBoxLayout()
        if show_text_field:
            layout_edit = QtWidgets.QHBoxLayout()
            layout_edit.addWidget(self.edit, 6)
            layout_edit.addWidget(self.edit_group_id, 2)
            layout.addLayout(layout_edit)
        # buttons
        self.buttonBox = bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.button(bb.Ok).setIcon(labelme.utils.newIcon("done"))
        bb.button(bb.Cancel).setIcon(labelme.utils.newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        # label_list
        self.labelList = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.labelList.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        if self._fit_to_content["column"]:
            self.labelList.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._sort_labels = sort_labels
        if labels:
            self.labelList.addItems(labels)
        if self._sort_labels:
            self.labelList.sortItems()
        else:
            self.labelList.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.labelList.currentItemChanged.connect(self.labelSelected)
        self.labelList.itemDoubleClicked.connect(self.labelDoubleClicked)
        self.labelList.setFixedHeight(150)
        self.edit.setListWidget(self.labelList)
        layout.addWidget(self.labelList)
        # label_flags
        if flags is None:
            flags = {}
        self._flags = flags
        self.flagsLayout = QtWidgets.QVBoxLayout()
        self.resetFlags()
        layout.addItem(self.flagsLayout)
        self.edit.textChanged.connect(self.updateFlags)
        # text edit
        self.editDescription = LabelQTextEdit()
        self.editDescription.setAcceptRichText(False)
        self.editDescription.setPlaceholderText("Label description")
        self.editDescription.setFixedHeight(50)
        layout.addWidget(self.editDescription)
        self.setLayout(layout)
        # completion
        completer = QtWidgets.QCompleter()
        if not QT5 and completion != "startswith":
            logger.warning(
                "completion other than 'startswith' is only "
                "supported with Qt5. Using 'startswith'"
            )
            completion = "startswith"
        if completion == "startswith":
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            # Default settings.
            # completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        elif completion == "contains":
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            completer.setFilterMode(QtCore.Qt.MatchContains)
        else:
            raise ValueError("Unsupported completion: {}".format(completion))
        completer.setModel(self.labelList.model())
        self.edit.setCompleter(completer)

    def addLabelHistory(self, label):
        if self.labelList.findItems(label, QtCore.Qt.MatchExactly):
            return
        self.labelList.addItem(label)
        if self._sort_labels:
            self.labelList.sortItems()

    def removeLabelHistory(self, label):
        for item in self.labelList.findItems(label, QtCore.Qt.MatchExactly):
            self.labelList.takeItem(self.labelList.row(item))

    def labelSelected(self, item):
        self.edit.setText(item.text())

    def validate(self):
        if not self.edit.isEnabled():
            self.accept()
            return

        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        if text:
            self.accept()

    def labelDoubleClicked(self, item):
        self.validate()

    def postProcess(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        self.edit.setText(text)

    def updateFlags(self, label_new):
        # keep state of shared flags
        flags_old = self.getFlags()

        flags_new = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label_new):
                for key in keys:
                    flags_new[key] = flags_old.get(key, False)
        self.setFlags(flags_new)

    def deleteFlags(self):
        for i in reversed(range(self.flagsLayout.count())):
            item = self.flagsLayout.itemAt(i).widget()
            self.flagsLayout.removeWidget(item)
            item.setParent(None)

    def resetFlags(self, label=""):
        flags = {}
        for pattern, keys in self._flags.items():
            if re.match(pattern, label):
                for key in keys:
                    flags[key] = False
        self.setFlags(flags)

    def setFlags(self, flags):
        self.deleteFlags()
        for key in flags:
            item = QtWidgets.QCheckBox(key, self)
            item.setChecked(flags[key])
            self.flagsLayout.addWidget(item)
            item.show()

    def getFlags(self):
        flags = {}
        for i in range(self.flagsLayout.count()):
            item = self.flagsLayout.itemAt(i).widget()
            flags[item.text()] = item.isChecked()
        return flags

    def getGroupId(self):
        group_id = self.edit_group_id.text()
        if group_id:
            return int(group_id)
        return None

    def popUp(self, text=None, move=True, flags=None, group_id=None, description=None):
        if self._fit_to_content["row"]:
            self.labelList.setMinimumHeight(
                self.labelList.sizeHintForRow(0) * self.labelList.count() + 2
            )
        if self._fit_to_content["column"]:
            self.labelList.setMinimumWidth(self.labelList.sizeHintForColumn(0) + 2)
        # if text is None, the previous label in self.edit is kept
        if text is None:
            text = self.edit.text()
        # description is always initialized by empty text c.f., self.edit.text
        if description is None:
            description = ""
        self.editDescription.setPlainText(description)
        if flags:
            self.setFlags(flags)
        else:
            self.resetFlags(text)
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))
        if group_id is None:
            self.edit_group_id.clear()
        else:
            self.edit_group_id.setText(str(group_id))
        items = self.labelList.findItems(text, QtCore.Qt.MatchFixedString)
        if items:
            if len(items) != 1:
                logger.warning("Label list has duplicate '{}'".format(text))
            self.labelList.setCurrentItem(items[0])
            row = self.labelList.row(items[0])
            self.edit.completer().setCurrentRow(row)
        self.edit.setFocus(QtCore.Qt.PopupFocusReason)
        if move:
            self.move(QtGui.QCursor.pos())
        if self.exec_():
            return (
                self.edit.text(),
                self.getFlags(),
                self.getGroupId(),
                self.editDescription.toPlainText(),
            )
        else:
            return None, None, None, None
