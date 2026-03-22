from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.registry_path_label = QLabel(self.tr("registry_label", path=self.mpid_service.REGISTRY_PATH))
        self.sync_hint_label = QLabel(self.tr("sync_folder_hint"))
        self.sync_hint_label.setWordWrap(True)
        self.sync_path_edit = QLineEdit(sync_path)
        self.sync_path_edit.setPlaceholderText(r"\\NAS\Freelancer\MPIDs")
        self.sync_browse_button = QPushButton(self.tr("choose_folder"))
        self.profile_list = QListWidget()
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

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

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(self.registry_path_label)
        root.addWidget(self.info_label)
        root.addWidget(self.sync_hint_label)

        sync_row = QWidget()
        sync_layout = QHBoxLayout(sync_row)
        sync_layout.setContentsMargins(0, 0, 0, 0)
        sync_layout.addWidget(self.sync_path_edit, 1)
        sync_layout.addWidget(self.sync_browse_button)

        sync_form = QFormLayout()
        sync_form.addRow(self.tr("sync_folder"), sync_row)
        root.addLayout(sync_form)
        root.addWidget(self.profile_list, 1)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.capture_button)
        actions_layout.addWidget(self.apply_button)
        actions_layout.addWidget(self.regenerate_button)
        actions_layout.addWidget(self.import_button)
        actions_layout.addWidget(self.export_button)
        actions_layout.addWidget(self.sync_button)
        actions_layout.addWidget(self.rename_button)
        actions_layout.addWidget(self.delete_button)
        root.addWidget(actions)
        root.addWidget(self.button_box)

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
        self.profile_list.clear()
        for profile in self._profiles:
            item = QListWidgetItem(profile.name or self.tr("unnamed_profile"))
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            item.setToolTip(self.tr("registry_values_tooltip", count=len(profile.values)))
            self.profile_list.addItem(item)

        if self.profile_list.count():
            self.profile_list.setCurrentRow(0)
        self._update_action_state()

    def _refresh_info(self) -> None:
        names = self.mpid_service.current_profile_value_names()
        if names:
            self.info_label.setText(self.tr("registry_active_summary", names=", ".join(names)))
        else:
            self.info_label.setText(self.tr("no_registry_mpid_summary"))
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

    def _capture_current_profile(self) -> None:
        values = self.mpid_service.read_current_profile_values()
        if not values or not self.mpid_service.has_mpid_values():
            QMessageBox.information(
                self,
                self.tr("no_mpid_found_title"),
                self.tr("no_mpid_found_message"),
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
