from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.mpid_profile import MpidProfile
from app.services.mpid_service import MpidService
from app.services.mpid_transfer_service import EXPORT_FILE_NAME, MpidTransferService


class MpidDialog(QDialog):
    def __init__(
        self,
        profiles: list[MpidProfile],
        mpid_service: MpidService,
        sync_path: str,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.setWindowTitle(self.tr("mpid_dialog_title"))
        self.resize(760, 520)

        self._profiles = deepcopy(profiles)
        self.mpid_service = mpid_service
        self.transfer_service = MpidTransferService()

        self.sync_path_edit = QLineEdit(sync_path)
        self.sync_path_edit.setPlaceholderText(r"\\NAS\Freelancer\MPIDs")
        self.sync_browse_button = QPushButton(self.tr("choose_folder"))
        self.profile_list = QListWidget()
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.value_details_label = QLabel(self.tr("mpid_profile_fields"))
        self.value_table = QTableWidget(0, 3)
        self.value_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.value_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.value_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.value_table.setAlternatingRowColors(False)
        self.value_table.verticalHeader().setVisible(False)
        self.value_table.horizontalHeader().setStretchLastSection(False)
        self.value_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.value_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.value_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.value_table.setHorizontalHeaderLabels(
            [
                self.tr("field_name"),
                self.tr("field_type"),
                self.tr("field_value"),
            ]
        )

        self.capture_button = QPushButton(self.tr("save_current_id"))
        self.apply_button = QPushButton(self.tr("activate_selected_id"))
        self.regenerate_button = QPushButton(self.tr("remove_current_id"))
        self.import_button = QPushButton(self.tr("import"))
        self.export_button = QPushButton(self.tr("export"))
        self.sync_button = QPushButton(self.tr("sync"))
        self.rename_button = QPushButton(self.tr("rename"))
        self.delete_button = QPushButton(self.tr("delete"))
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._configure_button_styles()

        self._build_ui()
        self._connect_signals()
        self._populate_profiles()
        self._refresh_info()

    @property
    def profiles(self) -> list[MpidProfile]:
        return self._profiles

    @property
    def sync_path(self) -> str:
        return self.sync_path_edit.text().strip()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _configure_button_styles(self) -> None:
        for button in (self.capture_button, self.apply_button):
            button.setProperty("variant", "primary")
            button.setMinimumHeight(38)

        for button in (self.import_button, self.export_button, self.rename_button, self.sync_browse_button, self.sync_button):
            button.setProperty("variant", "secondary")
            button.setMinimumHeight(38)

        self.sync_button.setText("")
        self.sync_button.setToolTip(self.tr("sync"))
        self.sync_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))
        self.sync_button.setIconSize(QSize(18, 18))
        self.sync_button.setFixedSize(42, 38)

        for button in (self.regenerate_button, self.delete_button):
            button.setProperty("variant", "danger")
            button.setMinimumHeight(38)

        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(self.tr("save"))
            save_button.setProperty("variant", "primary")
            save_button.setMinimumHeight(38)
        if cancel_button is not None:
            cancel_button.setText(self.tr("cancel"))
            cancel_button.setProperty("variant", "secondary")
            cancel_button.setMinimumHeight(38)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)

        sync_row = QWidget()
        sync_layout = QHBoxLayout(sync_row)
        sync_layout.setContentsMargins(0, 0, 0, 0)
        sync_layout.setSpacing(10)
        sync_layout.addWidget(self.sync_path_edit, 1)
        sync_layout.addWidget(self.sync_browse_button)
        sync_layout.addWidget(self.sync_button)

        sync_form = QFormLayout()
        sync_form.addRow(self.tr("sync_folder"), sync_row)
        root.addLayout(sync_form)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        content_layout.addWidget(self.profile_list, 1)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        details_layout.addWidget(self.value_details_label)
        details_layout.addWidget(self.value_table, 1)
        content_layout.addWidget(details, 2)

        root.addWidget(content, 1)

        actions = QWidget()
        actions_layout = QGridLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setHorizontalSpacing(10)
        actions_layout.setVerticalSpacing(10)
        actions_layout.addWidget(self.capture_button, 0, 0, 1, 2)
        actions_layout.addWidget(self.apply_button, 0, 2, 1, 2)
        actions_layout.addWidget(self.import_button, 1, 0)
        actions_layout.addWidget(self.export_button, 1, 1)
        actions_layout.addWidget(self.rename_button, 1, 2)
        actions_layout.addWidget(self.delete_button, 1, 3)
        actions_layout.addWidget(self.regenerate_button, 1, 4)
        for column in range(5):
            actions_layout.setColumnStretch(column, 1)
        root.addWidget(actions)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.button_box)
        root.addWidget(footer)

    def _connect_signals(self) -> None:
        self.capture_button.clicked.connect(self._capture_current_profile)
        self.apply_button.clicked.connect(self._apply_selected_profile)
        self.regenerate_button.clicked.connect(self._remove_current_mpid)
        self.sync_browse_button.clicked.connect(self._browse_sync_directory)
        self.sync_path_edit.textChanged.connect(lambda _text: self._refresh_info())
        self.import_button.clicked.connect(self._import_profiles)
        self.export_button.clicked.connect(self._export_profiles)
        self.sync_button.clicked.connect(self._sync_profiles)
        self.rename_button.clicked.connect(self._rename_selected_profile)
        self.delete_button.clicked.connect(self._delete_selected_profile)
        self.profile_list.itemDoubleClicked.connect(lambda _item: self._apply_selected_profile())
        self.profile_list.currentRowChanged.connect(self._update_action_state)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _populate_profiles(self) -> None:
        selected_profile = self._selected_profile()
        selected_profile_id = selected_profile.id if selected_profile is not None else None
        active_profile_id = self.mpid_service.current_profile_id(self._profiles)
        self.profile_list.clear()

        for profile in self._profiles:
            item = QListWidgetItem(profile.name or self.tr("unnamed_profile"))
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            item.setToolTip(self.tr("registry_values_tooltip", count=len(profile.values)))
            if profile.id == active_profile_id:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.profile_list.addItem(item)

        if selected_profile_id is not None:
            for index in range(self.profile_list.count()):
                if self.profile_list.item(index).data(Qt.ItemDataRole.UserRole) == selected_profile_id:
                    self.profile_list.setCurrentRow(index)
                    break
            else:
                if self.profile_list.count():
                    self.profile_list.setCurrentRow(0)
        elif self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        self._update_action_state()

    def _refresh_info(self) -> None:
        self.regenerate_button.setEnabled(self.mpid_service.has_mpid_values())
        self.export_button.setEnabled(bool(self._profiles))
        self.sync_button.setEnabled(bool(self.sync_path))

    def _selected_profile(self) -> MpidProfile | None:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self._profiles):
            return None
        return self._profiles[row]

    def _update_action_state(self) -> None:
        has_selection = self._selected_profile() is not None
        self.apply_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self._populate_value_table()

    def _populate_value_table(self) -> None:
        profile = self._selected_profile()
        values = profile.values if profile is not None else []
        self.value_table.setRowCount(len(values))

        for row, value in enumerate(values):
            name_item = QTableWidgetItem(value.name)
            type_item = QTableWidgetItem(self._format_value_type(value.value_type))
            data_item = QTableWidgetItem(value.data)
            data_item.setToolTip(value.data)
            self.value_table.setItem(row, 0, name_item)
            self.value_table.setItem(row, 1, type_item)
            self.value_table.setItem(row, 2, data_item)

        if not values:
            self.value_table.clearContents()

    def _format_value_type(self, value_type: int) -> str:
        type_names = {
            1: "REG_SZ",
            3: "REG_BINARY",
            4: "REG_DWORD",
            7: "REG_MULTI_SZ",
            11: "REG_QWORD",
        }
        return type_names.get(value_type, self.tr("registry_type_unknown", value_type=value_type))

    def _capture_current_profile(self) -> None:
        values = self.mpid_service.read_current_profile_values()
        if not values or not self.mpid_service.has_mpid_values():
            QMessageBox.information(
                self,
                self.tr("no_mpid_found_title"),
                self.tr("no_mpid_found_message"),
            )
            return

        existing_profile_id = self.mpid_service.current_profile_id(self._profiles)
        if existing_profile_id is not None:
            existing_profile = next((profile for profile in self._profiles if profile.id == existing_profile_id), None)
            profile_name = existing_profile.name if existing_profile is not None else self.tr("unnamed_profile")
            QMessageBox.information(
                self,
                self.tr("duplicate_mpid_title"),
                self.tr("duplicate_mpid_message", name=profile_name),
            )
            return

        name, accepted = QInputDialog.getText(
            self,
            self.tr("profile_name_title"),
            self.tr("new_profile_name_prompt"),
            text=f"MPID {len(self._profiles) + 1}",
        )
        if not accepted or not name.strip():
            return

        self._profiles.append(MpidProfile.create(name=name, values=values))
        self._populate_profiles()
        self.profile_list.setCurrentRow(self.profile_list.count() - 1)
        self._refresh_info()

    def _apply_selected_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return

        try:
            self.mpid_service.apply_profile_values(profile.values)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("registry_error_title"),
                self.tr("registry_write_failed", error=error),
            )
            return

        self._populate_profiles()
        self._refresh_info()
        QMessageBox.information(
            self,
            self.tr("mpid_activated_title"),
            self.tr("mpid_activated_message", name=profile.name),
        )

    def _remove_current_mpid(self) -> None:
        if not self.mpid_service.has_mpid_values():
            QMessageBox.information(
                self,
                self.tr("no_mpid_found_title"),
                self.tr("no_mpid_found_message"),
            )
            return

        answer = QMessageBox.question(
            self,
            self.tr("remove_mpid_confirm_title"),
            self.tr("remove_mpid_confirm_message"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self.mpid_service.delete_current_mpid_values()
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("registry_error_title"),
                self.tr("remove_mpid_failed", error=error),
            )
            return

        self._populate_profiles()
        self._refresh_info()
        if deleted:
            QMessageBox.information(
                self,
                self.tr("mpid_removed_title"),
                self.tr("mpid_removed_message"),
            )
        else:
            QMessageBox.information(
                self,
                self.tr("nothing_removed_title"),
                self.tr("nothing_removed_message"),
            )

    def _rename_selected_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return

        name, accepted = QInputDialog.getText(
            self,
            self.tr("rename_profile_title"),
            self.tr("rename_profile_prompt"),
            text=profile.name,
        )
        if not accepted or not name.strip():
            return

        profile.name = name.strip()
        profile.touch()
        self._populate_profiles()
        self._refresh_info()

    def _delete_selected_profile(self) -> None:
        row = self.profile_list.currentRow()
        if row < 0:
            return

        profile = self._profiles[row]
        answer = QMessageBox.question(
            self,
            self.tr("delete_profile_title"),
            self.tr("delete_profile_confirm", name=profile.name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        del self._profiles[row]
        self._populate_profiles()
        self._refresh_info()

    def _browse_sync_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("choose_sync_folder_dialog"),
            self.sync_path or str(Path.home()),
        )
        if not directory:
            return

        self.sync_path_edit.setText(directory)
        self._refresh_info()

    def _import_profiles(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("import_file_dialog"),
            str(Path.home()),
            "JSON files (*.json)",
        )
        if not filename:
            return

        try:
            result = self.transfer_service.import_profiles(Path(filename), self._profiles)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self,
                self.tr("import_failed_title"),
                self.tr("import_failed_message", error=error),
            )
            return

        self._profiles = result.profiles
        self._populate_profiles()
        self._refresh_info()
        QMessageBox.information(
            self,
            self.tr("import_done_title"),
            self.tr("import_done_message", imported=result.imported, updated=result.updated),
        )

    def _export_profiles(self) -> None:
        default_name = EXPORT_FILE_NAME
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("export_file_dialog"),
            str(Path.home() / default_name),
            "JSON files (*.json)",
        )
        if not filename:
            return

        target_path = Path(filename)
        if target_path.suffix.lower() != ".json":
            target_path = target_path.with_suffix(".json")

        try:
            self.transfer_service.export_profiles(target_path, self._profiles)
        except OSError as error:
            QMessageBox.critical(
                self,
                self.tr("export_failed_title"),
                self.tr("export_failed_message", error=error),
            )
            return

        QMessageBox.information(
            self,
            self.tr("export_done_title"),
            self.tr("export_done_message", path=target_path),
        )

    def _sync_profiles(self) -> None:
        sync_path = self.sync_path
        if not sync_path:
            QMessageBox.information(
                self,
                self.tr("no_sync_folder_title"),
                self.tr("no_sync_folder_message"),
            )
            return

        sync_dir = Path(sync_path)
        try:
            result = self.transfer_service.sync_profiles(sync_dir, self._profiles)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(
                self,
                self.tr("sync_failed_title"),
                self.tr("sync_failed_message", error=error),
            )
            return

        self._profiles = result.profiles
        self._populate_profiles()
        self._refresh_info()
        QMessageBox.information(
            self,
            self.tr("sync_done_title"),
            self.tr(
                "sync_done_message",
                path=self.transfer_service.default_sync_file(sync_dir),
                imported=result.imported,
                updated=result.updated,
            ),
        )
