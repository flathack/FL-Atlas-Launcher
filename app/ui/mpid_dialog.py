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
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import Translator
from app.models.installation import Installation
from app.models.mpid_profile import MpidProfile, MpidProfileServer, MpidServer
from app.services.mpid_service import MpidService
from app.services.mpid_transfer_service import EXPORT_FILE_NAME, MpidTransferService


class MpidDialog(QDialog):
    def __init__(
        self,
        profiles: list[MpidProfile],
        servers: list[MpidServer],
        mpid_service: MpidService,
        installation: Installation | None,
        sync_path: str,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.translator = translator
        self.setWindowTitle(self.tr("mpid_dialog_title"))
        self.resize(840, 560)

        self._profiles = deepcopy(profiles)
        self._servers = deepcopy(servers)
        self.mpid_service = mpid_service
        self.installation = installation
        self.transfer_service = MpidTransferService()

        self.sync_path_edit = QLineEdit(sync_path)
        self.sync_path_edit.setPlaceholderText(r"\\NAS\Freelancer\MPIDs")
        self.sync_browse_button = QPushButton(self.tr("choose_folder"))
        self.registry_location_label = QLabel()
        self.registry_location_label.setWordWrap(True)
        self.profile_list = QListWidget()
        self.profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.details_tabs = QTabWidget()
        self.server_details_label = QLabel(self.tr("mpid_server_characters"))
        self.server_tree = QTreeWidget()
        self.server_tree.setColumnCount(2)
        self.server_tree.setHeaderLabels([self.tr("mpid_tree_name"), self.tr("mpid_tree_type")])
        self.server_tree.header().setStretchLastSection(False)
        self.server_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.server_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
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
            [self.tr("field_name"), self.tr("field_type"), self.tr("field_value")]
        )

        self.capture_button = QPushButton(self.tr("save_current_id"))
        self.apply_button = QPushButton(self.tr("activate_selected_id"))
        self.regenerate_button = QPushButton(self.tr("remove_current_id"))
        self.import_button = QPushButton(self.tr("import"))
        self.export_button = QPushButton(self.tr("export"))
        self.sync_button = QPushButton(self.tr("sync"))
        self.rename_button = QPushButton(self.tr("rename_profile"))
        self.delete_button = QPushButton(self.tr("delete_profile"))
        self.add_server_button = QPushButton(self.tr("add_server"))
        self.add_character_button = QPushButton(self.tr("add_character"))
        self.rename_entry_button = QPushButton(self.tr("rename_entry"))
        self.delete_entry_button = QPushButton(self.tr("delete_entry"))
        self.profile_actions = QWidget()
        self.profile_actions_layout = QGridLayout(self.profile_actions)
        self.server_actions = QWidget()
        self.server_actions_layout = QGridLayout(self.server_actions)
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
    def servers(self) -> list[MpidServer]:
        return self._servers

    @property
    def sync_path(self) -> str:
        return self.sync_path_edit.text().strip()

    def tr(self, key: str, **kwargs: object) -> str:
        return self.translator.text(key, **kwargs)

    def _configure_button_styles(self) -> None:
        for button in (self.capture_button, self.apply_button):
            button.setProperty("variant", "primary")
            button.setMinimumHeight(38)

        for button in (
            self.import_button,
            self.export_button,
            self.rename_button,
            self.sync_browse_button,
            self.sync_button,
            self.add_server_button,
            self.add_character_button,
            self.rename_entry_button,
        ):
            button.setProperty("variant", "secondary")
            button.setMinimumHeight(38)

        self.sync_button.setText("")
        self.sync_button.setToolTip(self.tr("sync"))
        self.sync_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_BrowserReload))
        self.sync_button.setIconSize(QSize(18, 18))
        self.sync_button.setFixedSize(42, 38)

        for button in (self.regenerate_button, self.delete_button, self.delete_entry_button):
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
        sync_form.addRow(self.tr("registry_source"), self.registry_location_label)
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
        server_tab = QWidget()
        server_tab_layout = QVBoxLayout(server_tab)
        server_tab_layout.setContentsMargins(0, 0, 0, 0)
        server_tab_layout.setSpacing(8)
        server_tab_layout.addWidget(self.server_details_label)
        server_tab_layout.addWidget(self.server_tree, 1)

        values_tab = QWidget()
        values_tab_layout = QVBoxLayout(values_tab)
        values_tab_layout.setContentsMargins(0, 0, 0, 0)
        values_tab_layout.setSpacing(8)
        values_tab_layout.addWidget(self.value_details_label)
        values_tab_layout.addWidget(self.value_table, 1)

        self.details_tabs.addTab(server_tab, self.tr("mpid_tab_servers"))
        self.details_tabs.addTab(values_tab, self.tr("mpid_tab_id_data"))
        details_layout.addWidget(self.details_tabs, 1)
        content_layout.addWidget(details, 2)
        root.addWidget(content, 1)

        actions = QWidget()
        actions_layout = QGridLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setHorizontalSpacing(10)
        actions_layout.setVerticalSpacing(10)
        self.profile_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_actions_layout.setHorizontalSpacing(10)
        self.profile_actions_layout.setVerticalSpacing(10)
        self.profile_actions_layout.addWidget(self.capture_button, 0, 0, 1, 2)
        self.profile_actions_layout.addWidget(self.apply_button, 0, 2, 1, 2)
        self.profile_actions_layout.addWidget(self.import_button, 1, 0)
        self.profile_actions_layout.addWidget(self.export_button, 1, 1)
        self.profile_actions_layout.addWidget(self.rename_button, 1, 2)
        self.profile_actions_layout.addWidget(self.delete_button, 1, 3)
        self.profile_actions_layout.addWidget(self.regenerate_button, 1, 4)
        for column in range(5):
            self.profile_actions_layout.setColumnStretch(column, 1)

        self.server_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.server_actions_layout.setHorizontalSpacing(10)
        self.server_actions_layout.setVerticalSpacing(10)
        self.server_actions_layout.addWidget(self.add_server_button, 0, 0)
        self.server_actions_layout.addWidget(self.add_character_button, 0, 1)
        self.server_actions_layout.addWidget(self.rename_entry_button, 0, 2)
        self.server_actions_layout.addWidget(self.delete_entry_button, 0, 3)
        for column in range(4):
            self.server_actions_layout.setColumnStretch(column, 1)

        actions_layout.addWidget(self.profile_actions, 0, 0)
        actions_layout.addWidget(self.server_actions, 0, 0)
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
        self.add_server_button.clicked.connect(self._add_server)
        self.add_character_button.clicked.connect(self._add_character)
        self.rename_entry_button.clicked.connect(self._rename_selected_entry)
        self.delete_entry_button.clicked.connect(self._delete_selected_entry)
        self.profile_list.itemDoubleClicked.connect(lambda _item: self._apply_selected_profile())
        self.profile_list.currentRowChanged.connect(self._update_action_state)
        self.server_tree.itemDoubleClicked.connect(lambda _item, _column: self._rename_selected_entry())
        self.server_tree.currentItemChanged.connect(lambda _current, _previous: self._update_action_state())
        self.details_tabs.currentChanged.connect(lambda _index: self._update_action_state())
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _populate_profiles(self) -> None:
        selected_profile = self._selected_profile()
        selected_profile_id = selected_profile.id if selected_profile is not None else None
        active_profile_id = self.mpid_service.current_profile_id(self._profiles, self.installation)
        self.profile_list.clear()

        for profile in self._profiles:
            item = QListWidgetItem(profile.name or self.tr("unnamed_profile"))
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            item.setToolTip(
                self.tr(
                    "mpid_profile_tooltip",
                    count=len(profile.values),
                    servers=len(profile.servers),
                    characters=sum(len(server.characters) for server in profile.servers),
                )
            )
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
        self.regenerate_button.setEnabled(self.mpid_service.has_mpid_values(self.installation))
        self.export_button.setEnabled(bool(self._profiles or self._servers))
        self.sync_button.setEnabled(bool(self.sync_path))
        self.registry_location_label.setText(
            self.tr("registry_source_value", source=self.mpid_service.registry_location_description(self.installation))
        )

    def _selected_profile(self) -> MpidProfile | None:
        row = self.profile_list.currentRow()
        if row < 0 or row >= len(self._profiles):
            return None
        return self._profiles[row]

    def _selected_tree_entry(self) -> dict[str, object] | None:
        current_item = self.server_tree.currentItem()
        if current_item is None:
            return None
        data = current_item.data(0, Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def _selected_profile_server(self, profile: MpidProfile | None) -> tuple[int, MpidProfileServer] | None:
        if profile is None:
            return None
        entry = self._selected_tree_entry()
        if entry is None:
            return None
        server_id = str(entry.get("server_id", ""))
        for index, profile_server in enumerate(profile.servers):
            if profile_server.server_id == server_id:
                return index, profile_server
        return None

    def _global_server(self, server_id: str) -> MpidServer | None:
        return next((server for server in self._servers if server.id == server_id), None)

    def _sync_server_name_across_profiles(self, server_id: str, server_name: str) -> None:
        for profile in self._profiles:
            profile.sync_server_name(server_id, server_name)

    def _populate_server_tree(self) -> None:
        profile = self._selected_profile()
        selected_entry = self._selected_tree_entry()
        self.server_tree.blockSignals(True)
        self.server_tree.clear()

        if profile is not None:
            for profile_server in profile.servers:
                server_name = self._server_name(profile_server)
                server_item = QTreeWidgetItem([server_name, self.tr("server_label")])
                server_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"kind": "server", "server_id": profile_server.server_id},
                )
                self.server_tree.addTopLevelItem(server_item)
                for character_index, character_name in enumerate(profile_server.characters):
                    character_item = QTreeWidgetItem([character_name, self.tr("character_label")])
                    character_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {
                            "kind": "character",
                            "server_id": profile_server.server_id,
                            "character_index": character_index,
                        },
                    )
                    server_item.addChild(character_item)
                server_item.setExpanded(True)

        if selected_entry is not None:
            self._restore_tree_selection(selected_entry)
        self.server_tree.blockSignals(False)

    def _restore_tree_selection(self, entry: dict[str, object]) -> None:
        server_id = str(entry.get("server_id", ""))
        kind = str(entry.get("kind", ""))
        character_index = entry.get("character_index")
        for index in range(self.server_tree.topLevelItemCount()):
            server_item = self.server_tree.topLevelItem(index)
            server_data = server_item.data(0, Qt.ItemDataRole.UserRole) or {}
            if str(server_data.get("server_id", "")) != server_id:
                continue
            if kind == "server":
                self.server_tree.setCurrentItem(server_item)
                return
            if kind == "character" and isinstance(character_index, int) and 0 <= character_index < server_item.childCount():
                self.server_tree.setCurrentItem(server_item.child(character_index))
                return

    def _update_action_state(self) -> None:
        profile = self._selected_profile()
        has_selection = profile is not None
        has_tree_selection = self._selected_tree_entry() is not None
        is_server_tab = self.details_tabs.currentIndex() == 0
        self.apply_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.add_server_button.setEnabled(has_selection)
        self.add_character_button.setEnabled(has_selection and bool(profile.servers if profile else False))
        self.rename_entry_button.setEnabled(has_tree_selection)
        self.delete_entry_button.setEnabled(has_tree_selection)
        self.profile_actions.setVisible(not is_server_tab)
        self.server_actions.setVisible(is_server_tab)
        self._populate_server_tree()
        self._populate_value_table()

    def _populate_value_table(self) -> None:
        profile = self._selected_profile()
        values = profile.values if profile is not None else []
        self.value_table.setRowCount(len(values))
        for row, value in enumerate(values):
            self.value_table.setItem(row, 0, QTableWidgetItem(value.name))
            self.value_table.setItem(row, 1, QTableWidgetItem(self._format_value_type(value.value_type)))
            value_item = QTableWidgetItem(value.data)
            value_item.setToolTip(value.data)
            self.value_table.setItem(row, 2, value_item)
        if not values:
            self.value_table.clearContents()

    def _format_value_type(self, value_type: int) -> str:
        type_names = {1: "REG_SZ", 3: "REG_BINARY", 4: "REG_DWORD", 7: "REG_MULTI_SZ", 11: "REG_QWORD"}
        return type_names.get(value_type, self.tr("registry_type_unknown", value_type=value_type))

    def _capture_current_profile(self) -> None:
        values = self.mpid_service.read_current_profile_values(self.installation)
        if not values or not self.mpid_service.has_mpid_values(self.installation):
            QMessageBox.information(self, self.tr("no_mpid_found_title"), self.tr("no_mpid_found_message"))
            return
        existing_profile_id = self.mpid_service.current_profile_id(self._profiles, self.installation)
        if existing_profile_id is not None:
            existing_profile = next((profile for profile in self._profiles if profile.id == existing_profile_id), None)
            profile_name = existing_profile.name if existing_profile is not None else self.tr("unnamed_profile")
            QMessageBox.information(
                self, self.tr("duplicate_mpid_title"), self.tr("duplicate_mpid_message", name=profile_name)
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
            self.mpid_service.apply_profile_values(profile.values, self.installation)
        except OSError as error:
            QMessageBox.critical(self, self.tr("registry_error_title"), self.tr("registry_write_failed", error=error))
            return
        self._populate_profiles()
        self._refresh_info()
        QMessageBox.information(
            self, self.tr("mpid_activated_title"), self.tr("mpid_activated_message", name=profile.name)
        )

    def _remove_current_mpid(self) -> None:
        if not self.mpid_service.has_mpid_values(self.installation):
            QMessageBox.information(self, self.tr("no_mpid_found_title"), self.tr("no_mpid_found_message"))
            return
        answer = QMessageBox.question(
            self, self.tr("remove_mpid_confirm_title"), self.tr("remove_mpid_confirm_message")
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.mpid_service.delete_current_mpid_values(self.installation)
        except OSError as error:
            QMessageBox.critical(self, self.tr("registry_error_title"), self.tr("remove_mpid_failed", error=error))
            return
        self._populate_profiles()
        self._refresh_info()
        if deleted:
            QMessageBox.information(self, self.tr("mpid_removed_title"), self.tr("mpid_removed_message"))
        else:
            QMessageBox.information(self, self.tr("nothing_removed_title"), self.tr("nothing_removed_message"))

    def _rename_selected_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        name, accepted = QInputDialog.getText(
            self, self.tr("rename_profile_title"), self.tr("rename_profile_prompt"), text=profile.name
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
            self, self.tr("delete_profile_title"), self.tr("delete_profile_confirm", name=profile.name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self._profiles[row]
        self._populate_profiles()
        self._refresh_info()

    def _add_server(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return

        options = [self.tr("use_existing_server"), self.tr("create_new_server")]
        choice, accepted = QInputDialog.getItem(
            self,
            self.tr("add_server_title"),
            self.tr("add_server_mode_prompt"),
            options,
            editable=False,
        )
        if not accepted or not choice:
            return

        server: MpidServer | None = None
        if choice == self.tr("use_existing_server") and self._servers:
            names = [item.name or self.tr("unnamed_server") for item in self._servers]
            selected_name, name_accepted = QInputDialog.getItem(
                self,
                self.tr("choose_server_title"),
                self.tr("choose_server_prompt"),
                names,
                editable=False,
            )
            if not name_accepted or not selected_name:
                return
            server = next((item for item in self._servers if (item.name or self.tr("unnamed_server")) == selected_name), None)
        else:
            if choice == self.tr("use_existing_server") and not self._servers:
                QMessageBox.information(self, self.tr("no_global_servers_title"), self.tr("no_global_servers_message"))
                return
            name, name_accepted = QInputDialog.getText(
                self,
                self.tr("add_server_title"),
                self.tr("add_server_prompt"),
                text=f"Server {len(self._servers) + 1}",
            )
            if not name_accepted or not name.strip():
                return
            server = MpidServer.create(name.strip())
            self._servers.append(server)

        if server is None:
            return
        if any(item.server_id == server.id for item in profile.servers):
            QMessageBox.information(
                self,
                self.tr("server_already_added_title"),
                self.tr("server_already_added_message", name=server.name or self.tr("unnamed_server")),
            )
            return
        profile.servers.append(MpidProfileServer.create(server))
        profile.touch()
        self._populate_profiles()
        self._refresh_info()

    def _add_character(self) -> None:
        profile = self._selected_profile()
        selected_server = self._selected_profile_server(profile)
        if profile is None or selected_server is None:
            QMessageBox.information(self, self.tr("no_server_title"), self.tr("no_server_message"))
            return
        _, profile_server = selected_server
        name, accepted = QInputDialog.getText(
            self,
            self.tr("add_character_title"),
            self.tr("add_character_prompt", server=self._server_name(profile_server)),
        )
        if not accepted or not name.strip():
            return
        profile_server.characters.append(name.strip())
        profile.touch()
        self._populate_profiles()
        self._refresh_info()

    def _rename_selected_entry(self) -> None:
        profile = self._selected_profile()
        entry = self._selected_tree_entry()
        selected_server = self._selected_profile_server(profile)
        if profile is None or entry is None or selected_server is None:
            return
        _, profile_server = selected_server
        if str(entry.get("kind", "")) == "server":
            global_server = self._global_server(profile_server.server_id)
            if global_server is None:
                return
            name, accepted = QInputDialog.getText(
                self,
                self.tr("rename_server_title"),
                self.tr("rename_server_prompt"),
                text=global_server.name,
            )
            if not accepted or not name.strip():
                return
            global_server.name = name.strip()
            global_server.touch()
            self._sync_server_name_across_profiles(global_server.id, global_server.name)
        else:
            character_index = entry.get("character_index")
            if not isinstance(character_index, int) or not (0 <= character_index < len(profile_server.characters)):
                return
            name, accepted = QInputDialog.getText(
                self,
                self.tr("rename_character_title"),
                self.tr("rename_character_prompt"),
                text=profile_server.characters[character_index],
            )
            if not accepted or not name.strip():
                return
            profile_server.characters[character_index] = name.strip()
            profile.touch()
        self._populate_profiles()
        self._refresh_info()

    def _delete_selected_entry(self) -> None:
        profile = self._selected_profile()
        entry = self._selected_tree_entry()
        selected_server = self._selected_profile_server(profile)
        if profile is None or entry is None or selected_server is None:
            return
        server_index, profile_server = selected_server
        if str(entry.get("kind", "")) == "server":
            answer = QMessageBox.question(
                self,
                self.tr("delete_server_title"),
                self.tr("delete_server_confirm", name=self._server_name(profile_server)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            del profile.servers[server_index]
        else:
            character_index = entry.get("character_index")
            if not isinstance(character_index, int) or not (0 <= character_index < len(profile_server.characters)):
                return
            answer = QMessageBox.question(
                self,
                self.tr("delete_character_title"),
                self.tr("delete_character_confirm", name=profile_server.characters[character_index]),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            del profile_server.characters[character_index]
        profile.touch()
        self._populate_profiles()
        self._refresh_info()

    def _server_name(self, profile_server: MpidProfileServer) -> str:
        global_server = self._global_server(profile_server.server_id)
        return (global_server.name if global_server is not None else profile_server.server_name) or self.tr("unnamed_server")

    def _browse_sync_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("choose_sync_folder_dialog"),
            self.sync_path or str(Path.home()),
        )
        if directory:
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
            result = self.transfer_service.import_profiles(Path(filename), self._profiles, self._servers)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, self.tr("import_failed_title"), self.tr("import_failed_message", error=error))
            return
        self._profiles = result.profiles
        self._servers = result.servers
        self._populate_profiles()
        self._refresh_info()
        QMessageBox.information(
            self,
            self.tr("import_done_title"),
            self.tr("import_done_message", imported=result.imported, updated=result.updated),
        )

    def _export_profiles(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("export_file_dialog"),
            str(Path.home() / EXPORT_FILE_NAME),
            "JSON files (*.json)",
        )
        if not filename:
            return
        target_path = Path(filename)
        if target_path.suffix.lower() != ".json":
            target_path = target_path.with_suffix(".json")
        try:
            self.transfer_service.export_profiles(target_path, self._profiles, self._servers)
        except OSError as error:
            QMessageBox.critical(self, self.tr("export_failed_title"), self.tr("export_failed_message", error=error))
            return
        QMessageBox.information(
            self,
            self.tr("export_done_title"),
            self.tr("export_done_message", path=target_path),
        )

    def _sync_profiles(self) -> None:
        sync_path = self.sync_path
        if not sync_path:
            QMessageBox.information(self, self.tr("no_sync_folder_title"), self.tr("no_sync_folder_message"))
            return
        sync_dir = Path(sync_path)
        try:
            result = self.transfer_service.sync_profiles(sync_dir, self._profiles, self._servers)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, self.tr("sync_failed_title"), self.tr("sync_failed_message", error=error))
            return
        self._profiles = result.profiles
        self._servers = result.servers
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
