# -*- encoding: utf-8 -*-

import html

from qtpy import QtWidgets
from qtpy.QtCore import Qt

from .escapable_qlist_widget import EscapableQListWidget


class UniqueLabelQListWidget(EscapableQListWidget):
    def mousePressEvent(self, event):
        super(UniqueLabelQListWidget, self).mousePressEvent(event)
        if not self.indexAt(event.pos()).isValid():
            self.clearSelection()

    def findItemByLabel(self, label):
        for row in range(self.count()):
            item = self.item(row)
            if item.data(Qt.UserRole) == label:
                return item

    def createItemFromLabel(self, label):
        if self.findItemByLabel(label):
            raise ValueError("Item for label '{}' already exists".format(label))

        item = QtWidgets.QListWidgetItem()
        item.setData(Qt.UserRole, label)
        return item

    def setItemLabel(self, item, label, color=None):
        qlabel = QtWidgets.QLabel()
        # Rich text (the <font> tag below) doesn't reliably inherit the
        # app-wide stylesheet's text color, so set it explicitly here to
        # match the modern theme instead of falling back to Qt's default
        # (black, invisible against the dark background).
        qlabel.setStyleSheet("color: #dcdcdc; background: transparent;")
        if color is None:
            qlabel.setText("{}".format(label))
        else:
            qlabel.setText(
                '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                    html.escape(label), *color
                )
            )
        qlabel.setAlignment(Qt.AlignBottom)

        # The app stylesheet gives QListWidget::item padding (see
        # styles/modern.qss). For items with a custom item widget, Qt
        # carves that padding out of the reserved size-hint rect rather
        # than growing the row to fit it, which without this compensation
        # squeezes the label down to just a few pixels tall and clips the
        # text away. Pad the hint so the label keeps its natural size.
        size_hint = qlabel.sizeHint()
        size_hint.setWidth(size_hint.width() + 12)
        size_hint.setHeight(size_hint.height() + 12)
        item.setSizeHint(size_hint)

        self.setItemWidget(item, qlabel)
