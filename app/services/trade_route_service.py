from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from app.models.installation import Installation
from app.services.cheat_service import CheatService


ParsedSection = tuple[str, list[tuple[str, str]]]


@dataclass(slots=True)
class TradeRouteShipOption:
    nickname: str
    display_name: str
    cargo_capacity: int

    @property
    def label(self) -> str:
        return f"{self.display_name} [{self.cargo_capacity}]"


@dataclass(slots=True)
class TradeRouteFactionOption:
    nickname: str
    display_name: str


@dataclass(slots=True)
class TradeRouteRow:
    source_system_nickname: str
    source_system: str
    buy_base_nickname: str
    buy_base: str
    target_system_nickname: str
    target_system: str
    sell_base_nickname: str
    sell_base: str
    commodity: str
    buy_price: int
    sell_price: int
    profit_per_unit: int
    cargo_capacity: int
    total_profit: int
    jumps: int
    path: list[str]
    path_nicknames: list[str]


@dataclass(slots=True)
class TradeRoutePreviewObject:
    nickname: str
    label: str
    archetype: str
    position: tuple[float, float]


@dataclass(slots=True)
class TradeRoutePreviewSystem:
    nickname: str
    display_name: str
    objects: list[TradeRoutePreviewObject]
    lane_edges: list[tuple[tuple[float, float], tuple[float, float]]]
    local_path: list[tuple[float, float]]
    start_position: tuple[float, float] | None
    end_position: tuple[float, float] | None


@dataclass(slots=True)
class TradeRoutePreviewData:
    commodity: str
    systems: list[TradeRoutePreviewSystem]


@dataclass(slots=True)
class TradeRouteLoopRow:
    start_system_nickname: str
    start_system: str
    route_text: str
    system_nicknames: list[str]
    commodities: list[str]
    legs: list[TradeRouteRow]
    cargo_capacity: int
    total_profit: int
    total_jumps: int


@dataclass(slots=True)
class InstallationLayout:
    freelancer_ini: Path
    goods_files: list[Path]
    market_files: list[Path]
    group_files: list[Path]
    universe_file: Path | None


@dataclass(slots=True)
class TradeRouteContext:
    layout: InstallationLayout
    commodity_prices: dict[str, int]
    commodity_names: dict[str, str]
    faction_names: dict[str, str]
    system_index: dict[str, dict[str, object]]
    base_index: dict[str, dict[str, object]]
    adjacency: dict[str, set[str]]
    market_entries: dict[str, list[dict[str, object]]]


class TradeRouteService:
    def __init__(self, cheat_service: CheatService) -> None:
        self.cheat_service = cheat_service

    def ship_options(self, installation: Installation) -> list[TradeRouteShipOption]:
        rows = self.cheat_service.ship_info_rows(installation)
        return [
            TradeRouteShipOption(
                nickname=row.nickname,
                display_name=row.display_name,
                cargo_capacity=row.cargo_capacity,
            )
            for row in rows
            if row.cargo_capacity > 0
        ]

    def faction_options(self, installation: Installation) -> list[TradeRouteFactionOption]:
        layout = self._load_layout(installation)
        resource_dlls = self.cheat_service._resource_dll_paths(installation)
        faction_names = self._load_faction_names(layout.group_files, resource_dlls)
        options = [
            TradeRouteFactionOption(nickname=nickname, display_name=display_name)
            for nickname, display_name in faction_names.items()
        ]
        options.sort(key=lambda item: item.display_name.lower())
        return options

    def best_routes_by_system(
        self,
        installation: Installation,
        *,
        cargo_capacity: int,
        max_jumps: int,
        player_reputation: dict[str, float] | None = None,
    ) -> list[TradeRouteRow]:
        context = self._build_trade_route_context(installation)
        candidate_routes = self._candidate_routes(
            context,
            cargo_capacity=cargo_capacity,
            max_jumps=max_jumps,
            player_reputation=player_reputation,
        )
        best_by_system: dict[str, TradeRouteRow] = {}
        for route in candidate_routes:
            current = best_by_system.get(route.source_system_nickname)
            if current is None or route.total_profit > current.total_profit:
                best_by_system[route.source_system_nickname] = route

        rows = list(best_by_system.values())
        rows.sort(key=lambda item: (item.total_profit, item.profit_per_unit, item.source_system), reverse=True)
        return rows

    def best_inner_system_routes(
        self,
        installation: Installation,
        *,
        cargo_capacity: int,
        player_reputation: dict[str, float] | None = None,
    ) -> list[TradeRouteRow]:
        context = self._build_trade_route_context(installation)
        candidates = self._candidate_routes(
            context,
            cargo_capacity=cargo_capacity,
            max_jumps=0,
            player_reputation=player_reputation,
        )
        candidates.sort(key=lambda item: (item.total_profit, item.profit_per_unit, item.source_system), reverse=True)
        return candidates

    def best_routes_per_base(
        self,
        installation: Installation,
        *,
        cargo_capacity: int = 1,
        max_jumps: int = 1,
    ) -> dict[str, TradeRouteRow]:
        """Return the single best outbound route per *buy* base (max 1 jump)."""
        context = self._build_trade_route_context(installation)
        candidates = self._candidate_routes(
            context,
            cargo_capacity=cargo_capacity,
            max_jumps=max_jumps,
        )
        best: dict[str, TradeRouteRow] = {}
        for route in candidates:
            key = route.buy_base_nickname.lower()
            current = best.get(key)
            if current is None or route.profit_per_unit > current.profit_per_unit:
                best[key] = route
        return best

    def best_round_trips(
        self,
        installation: Installation,
        *,
        cargo_capacity: int,
        max_jumps: int,
        leg_count: int,
        player_reputation: dict[str, float] | None = None,
        max_results: int = 20,
    ) -> list[TradeRouteLoopRow]:
        leg_count = max(3, min(int(leg_count), 6))
        context = self._build_trade_route_context(installation)
        candidate_routes = self._candidate_routes(
            context,
            cargo_capacity=cargo_capacity,
            max_jumps=max_jumps,
            player_reputation=player_reputation,
        )
        if not candidate_routes:
            return []

        best_edge_by_pair: dict[tuple[str, str], TradeRouteRow] = {}
        outgoing: dict[str, list[TradeRouteRow]] = {}
        for route in candidate_routes:
            pair_key = (route.source_system_nickname, route.target_system_nickname)
            current = best_edge_by_pair.get(pair_key)
            if current is None or route.total_profit > current.total_profit:
                best_edge_by_pair[pair_key] = route
        for route in best_edge_by_pair.values():
            outgoing.setdefault(route.source_system_nickname, []).append(route)
        for routes in outgoing.values():
            routes.sort(key=lambda item: (item.total_profit, -item.jumps), reverse=True)

        loops: list[TradeRouteLoopRow] = []
        seen_cycles: set[tuple[str, ...]] = set()

        for start_system in sorted(outgoing.keys()):
            self._search_round_trip_loops(
                start_system=start_system,
                current_system=start_system,
                leg_count=leg_count,
                visited={start_system},
                chosen_legs=[],
                outgoing=outgoing,
                seen_cycles=seen_cycles,
                result=loops,
            )

        loops.sort(key=lambda item: (item.total_profit, -item.total_jumps, item.route_text), reverse=True)
        return loops[: max(1, int(max_results))]

    def build_route_preview(self, installation: Installation, route: TradeRouteRow) -> TradeRoutePreviewData:
        context = self._build_trade_route_context(installation)
        layout = context.layout
        system_index = context.system_index
        base_index = context.base_index
        system_cache = self._build_system_visual_cache(layout, system_index, base_index)

        buy_base = base_index.get(route.buy_base_nickname.lower())
        sell_base = base_index.get(route.sell_base_nickname.lower())
        if not buy_base or not sell_base:
            raise FileNotFoundError("Source/target base could not be resolved for the selected route.")

        path_nicknames = route.path_nicknames or [route.source_system_nickname, route.target_system_nickname]
        preview_systems: list[TradeRoutePreviewSystem] = []
        for index, system_nick in enumerate(path_nicknames):
            info = system_cache.get(system_nick, self._empty_system_cache(system_nick, system_index))
            start_position: tuple[float, float] | None = None
            end_position: tuple[float, float] | None = None

            if len(path_nicknames) == 1:
                start_position = self._coerce_point(buy_base.get("pos"))
                end_position = self._coerce_point(sell_base.get("pos"))
            elif index == 0:
                start_position = self._coerce_point(buy_base.get("pos"))
                end_position = self._pick_jump_point(info, path_nicknames[index + 1], start_position)
            elif index == len(path_nicknames) - 1:
                end_position = self._coerce_point(sell_base.get("pos"))
                start_position = self._pick_jump_point(info, path_nicknames[index - 1], end_position)
            else:
                start_position = self._pick_jump_point(info, path_nicknames[index - 1], None)
                end_position = self._pick_jump_point(info, path_nicknames[index + 1], start_position)

            if start_position is None and end_position is not None:
                start_position = end_position
            if end_position is None and start_position is not None:
                end_position = start_position

            local_path = self._trade_route_local_path(info, start_position, end_position)
            preview_systems.append(
                TradeRoutePreviewSystem(
                    nickname=system_nick,
                    display_name=str(system_index.get(system_nick, {}).get("display_name", system_nick)),
                    objects=list(info["objects"]),
                    lane_edges=list(info["lane_edges"]),
                    local_path=local_path,
                    start_position=start_position,
                    end_position=end_position,
                )
            )

        return TradeRoutePreviewData(commodity=route.commodity, systems=preview_systems)

    def _build_trade_route_context(self, installation: Installation) -> TradeRouteContext:
        layout = self._load_layout(installation)
        resource_dlls = self.cheat_service._resource_dll_paths(installation)
        commodity_prices, commodity_names = self._scan_commodity_prices(layout.goods_files, resource_dlls)
        faction_names = self._load_faction_names(layout.group_files, resource_dlls)
        system_index = self._build_system_index(layout.universe_file, resource_dlls)
        base_index = self._build_base_index(layout.universe_file, resource_dlls)
        self._enrich_base_index_from_system_files(layout, system_index, base_index)
        locked_gate_hashes = self._load_locked_gate_hashes(layout.universe_file)
        adjacency = self._build_system_adjacency(layout.universe_file, locked_gate_hashes)
        market_entries = self._extract_market_entries(layout.market_files, base_index, commodity_prices)
        market_entries = self._add_implicit_base_price_sinks(market_entries, base_index, commodity_prices)
        return TradeRouteContext(
            layout=layout,
            commodity_prices=commodity_prices,
            commodity_names=commodity_names,
            faction_names=faction_names,
            system_index=system_index,
            base_index=base_index,
            adjacency=adjacency,
            market_entries=market_entries,
        )

    def _candidate_routes(
        self,
        context: TradeRouteContext,
        *,
        cargo_capacity: int,
        max_jumps: int,
        player_reputation: dict[str, float] | None = None,
    ) -> list[TradeRouteRow]:
        if not context.commodity_prices:
            return []
        normalized_reputation = self._normalize_reputation_map(player_reputation)
        routes: list[TradeRouteRow] = []
        for commodity, entries in context.market_entries.items():
            accessible_entries = [
                entry
                for entry in entries
                if self._is_market_entry_accessible(context.base_index, entry, normalized_reputation)
                and "_miner" not in str(entry.get("base_nick", "")).lower()
            ]
            sources = [entry for entry in accessible_entries if bool(entry["is_source"])] or accessible_entries
            sinks = [entry for entry in accessible_entries if not bool(entry["is_source"])]
            if not sources or not sinks:
                continue
            for source in sources:
                for sink in sinks:
                    if source["base_nick"] == sink["base_nick"]:
                        continue
                    profit_per_unit = int(round(float(sink["price"]) - float(source["price"])))
                    if profit_per_unit <= 0:
                        continue
                    source_system = str(source["system"])
                    target_system = str(sink["system"])
                    path = self._system_path_bfs(context.adjacency, source_system, target_system)
                    jumps = max(0, len(path) - 1) if path else 0
                    if source_system != target_system and not path:
                        continue
                    if jumps > max_jumps:
                        continue
                    routes.append(
                        TradeRouteRow(
                            source_system_nickname=source_system,
                            source_system=str(context.system_index.get(source_system, {}).get("display_name", source_system)),
                            buy_base_nickname=str(source["base_nick"]),
                            buy_base=str(context.base_index.get(str(source["base_nick"]).lower(), {}).get("display_name", source["base_nick"])),
                            target_system_nickname=target_system,
                            target_system=str(context.system_index.get(target_system, {}).get("display_name", target_system)),
                            sell_base_nickname=str(sink["base_nick"]),
                            sell_base=str(context.base_index.get(str(sink["base_nick"]).lower(), {}).get("display_name", sink["base_nick"])),
                            commodity=context.commodity_names.get(commodity.lower(), self._commodity_fallback_name(commodity)),
                            buy_price=int(round(float(source["price"]))),
                            sell_price=int(round(float(sink["price"]))),
                            profit_per_unit=profit_per_unit,
                            cargo_capacity=max(0, cargo_capacity),
                            total_profit=profit_per_unit * max(0, cargo_capacity),
                            jumps=jumps,
                            path=[str(context.system_index.get(node, {}).get("display_name", node)) for node in path],
                            path_nicknames=list(path),
                        )
                    )
        return routes

    def _search_round_trip_loops(
        self,
        *,
        start_system: str,
        current_system: str,
        leg_count: int,
        visited: set[str],
        chosen_legs: list[TradeRouteRow],
        outgoing: dict[str, list[TradeRouteRow]],
        seen_cycles: set[tuple[str, ...]],
        result: list[TradeRouteLoopRow],
    ) -> None:
        if len(chosen_legs) == leg_count:
            if current_system != start_system:
                return
            cycle_nodes = [start_system] + [leg.target_system_nickname for leg in chosen_legs]
            canonical = self._canonical_cycle(cycle_nodes)
            if canonical in seen_cycles:
                return
            seen_cycles.add(canonical)
            route_text = " -> ".join([chosen_legs[0].source_system] + [leg.target_system for leg in chosen_legs])
            result.append(
                TradeRouteLoopRow(
                    start_system_nickname=start_system,
                    start_system=chosen_legs[0].source_system,
                    route_text=route_text,
                    system_nicknames=cycle_nodes,
                    commodities=[leg.commodity for leg in chosen_legs],
                    legs=list(chosen_legs),
                    cargo_capacity=chosen_legs[0].cargo_capacity,
                    total_profit=sum(leg.total_profit for leg in chosen_legs),
                    total_jumps=sum(leg.jumps for leg in chosen_legs),
                )
            )
            return

        remaining_legs = leg_count - len(chosen_legs)
        for route in outgoing.get(current_system, []):
            next_system = route.target_system_nickname
            if remaining_legs == 1:
                if next_system != start_system:
                    continue
            elif next_system in visited:
                continue
            next_visited = visited if next_system == start_system else (visited | {next_system})
            self._search_round_trip_loops(
                start_system=start_system,
                current_system=next_system,
                leg_count=leg_count,
                visited=next_visited,
                chosen_legs=chosen_legs + [route],
                outgoing=outgoing,
                seen_cycles=seen_cycles,
                result=result,
            )

    def _canonical_cycle(self, cycle_nodes: list[str]) -> tuple[str, ...]:
        if len(cycle_nodes) <= 1:
            return tuple(cycle_nodes)
        core = list(cycle_nodes[:-1])
        rotations = [tuple(core[index:] + core[:index]) for index in range(len(core))]
        return min(rotations)

    def _load_layout(self, installation: Installation) -> InstallationLayout:
        freelancer_ini = self.cheat_service._freelancer_ini_path(installation)
        sections = self._parse_ini_file(freelancer_ini)
        goods_files = self._resolve_data_files(freelancer_ini, sections, "goods")
        market_files = self._resolve_data_files(freelancer_ini, sections, "markets")
        group_files = self._resolve_data_files(freelancer_ini, sections, "groups")
        universe_files = self._resolve_data_files(freelancer_ini, sections, "universe")
        return InstallationLayout(
            freelancer_ini=freelancer_ini,
            goods_files=goods_files,
            market_files=market_files,
            group_files=group_files,
            universe_file=universe_files[0] if universe_files else None,
        )

    def _load_faction_names(self, group_files: list[Path], resource_dlls: list[Path]) -> dict[str, str]:
        faction_names: dict[str, str] = {}
        for group_file in group_files:
            for section_name, entries in self._parse_ini_file(group_file):
                if section_name.lower() != "group":
                    continue
                nickname = ""
                ids_name = ""
                ids_short_name = ""
                for key, value in entries:
                    key_lower = key.lower()
                    if key_lower == "nickname":
                        nickname = value.strip().lower()
                    elif key_lower in {"ids_name", "strid_name"} and not ids_name:
                        ids_name = value.strip()
                    elif key_lower == "ids_short_name" and not ids_short_name:
                        ids_short_name = value.strip()
                if not nickname:
                    continue
                resolved_name = ""
                if ids_short_name:
                    resolved_name = self.cheat_service._resolve_ids_name(
                        self.cheat_service._parse_int(ids_short_name),
                        resource_dlls,
                    )
                if not resolved_name and ids_name:
                    resolved_name = self.cheat_service._resolve_ids_name(
                        self.cheat_service._parse_int(ids_name),
                        resource_dlls,
                    )
                faction_names[nickname] = resolved_name or nickname
        return faction_names

    def _enrich_base_index_from_system_files(
        self,
        layout: InstallationLayout,
        system_index: dict[str, dict[str, object]],
        base_index: dict[str, dict[str, object]],
    ) -> None:
        universe_root = layout.universe_file.parent if layout.universe_file is not None else None
        if universe_root is None:
            return
        for system_nick, system_info in system_index.items():
            relative_path = str(system_info.get("file", "")).strip()
            if not relative_path:
                continue
            system_file = self._ci_resolve(universe_root, relative_path)
            if system_file is None or not system_file.is_file():
                continue
            for section_name, entries in self._parse_ini_file(system_file):
                if section_name.lower() != "object":
                    continue
                values = {key.lower(): value for key, value in entries}
                base_nick = str(values.get("base") or values.get("dock_with") or "").strip().lower()
                if not base_nick or base_nick not in base_index:
                    continue
                if "pos" in values:
                    base_index[base_nick]["pos"] = self._parse_2d_position(values.get("pos", "0,0,0"))
                reputation_group = str(values.get("reputation", "")).strip().lower()
                if reputation_group:
                    base_index[base_nick]["faction"] = reputation_group
                base_index[base_nick]["system"] = system_nick

    def _resolve_data_files(self, freelancer_ini: Path, sections: list[ParsedSection], key_name: str) -> list[Path]:
        data_root = freelancer_ini.parent.parent / "DATA" if freelancer_ini.parent.name.lower() == "exe" else freelancer_ini.parent / "DATA"
        resolved: list[Path] = []
        seen: set[str] = set()
        for section_name, entries in sections:
            if section_name.lower() != "data":
                continue
            for key, value in entries:
                if key.lower() != key_name.lower():
                    continue
                candidate = self._ci_resolve(data_root, value)
                if candidate is None or not candidate.is_file():
                    continue
                candidate_key = str(candidate).lower()
                if candidate_key in seen:
                    continue
                seen.add(candidate_key)
                resolved.append(candidate)
        return resolved

    def _ci_resolve(self, base: Path, relative_path: str) -> Path | None:
        current = base
        for part in str(relative_path or "").replace("\\", "/").split("/"):
            if not part:
                continue
            if not current.exists() or not current.is_dir():
                return None
            found = next((entry for entry in current.iterdir() if entry.name.lower() == part.lower()), None)
            if found is None:
                return None
            current = found
        return current

    def _parse_ini_file(self, path: Path) -> list[ParsedSection]:
        raw_data = path.read_bytes()
        text = raw_data.decode(self.cheat_service._detect_encoding(raw_data), errors="ignore")
        sections: list[ParsedSection] = []
        current_name: str | None = None
        current_entries: list[tuple[str, str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(";") or line.startswith("//"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name is not None:
                    sections.append((current_name, current_entries))
                current_name = line[1:-1].strip()
                current_entries = []
                continue
            if current_name is None or "=" not in line:
                continue
            if ";" in line:
                line = line.split(";", 1)[0].strip()
            key, _, value = line.partition("=")
            current_entries.append((key.strip(), value.strip()))
        if current_name is not None:
            sections.append((current_name, current_entries))
        return sections

    def _scan_commodity_prices(
        self,
        goods_files: list[Path],
        resource_dlls: list[Path],
    ) -> tuple[dict[str, int], dict[str, str]]:
        prices: dict[str, int] = {}
        names: dict[str, str] = {}
        for goods_file in goods_files:
            for section_name, entries in self._parse_ini_file(goods_file):
                if section_name.lower() != "good":
                    continue
                nickname = ""
                price = 0
                ids_name = ""
                for key, value in entries:
                    key_lower = key.lower()
                    if key_lower == "nickname":
                        nickname = value.strip()
                    elif key_lower == "price":
                        try:
                            price = int(float(value.strip()))
                        except ValueError:
                            price = 0
                    elif key_lower in {"ids_name", "strid_name"} and not ids_name:
                        ids_name = value.strip()
                if not nickname.lower().startswith("commodity_"):
                    continue
                prices[nickname] = price
                resolved_name = ""
                if ids_name:
                    resolved_name = self.cheat_service._resolve_ids_name(
                        self.cheat_service._parse_int(ids_name),
                        resource_dlls,
                    )
                names[nickname.lower()] = resolved_name or self._commodity_fallback_name(nickname)
        return prices, names

    def _extract_market_entries(
        self,
        market_files: list[Path],
        base_index: dict[str, dict[str, object]],
        commodity_prices: dict[str, int],
    ) -> dict[str, list[dict[str, object]]]:
        by_commodity: dict[str, list[dict[str, object]]] = {}
        for market_file in market_files:
            for section_name, entries in self._parse_ini_file(market_file):
                if section_name.lower() != "basegood":
                    continue
                base_nick = ""
                for key, value in entries:
                    if key.lower() == "base":
                        base_nick = value.strip().lower()
                        break
                if not base_nick or base_nick not in base_index:
                    continue
                for key, value in entries:
                    if key.lower() != "marketgood":
                        continue
                    fields = [field.strip() for field in value.split(",")]
                    if len(fields) < 7:
                        continue
                    commodity = fields[0]
                    commodity_lower = commodity.lower()
                    if not commodity_lower.startswith("commodity_") or commodity_lower.startswith("commodity_pilot_"):
                        continue
                    try:
                        required_level = int(float(fields[1]))
                        required_reputation = float(fields[2])
                        relation_flag = int(float(fields[5]))
                        multiplier = float(fields[6])
                    except ValueError:
                        continue
                    if multiplier <= 0.0:
                        continue
                    base_price = commodity_prices.get(commodity, 0)
                    if base_price <= 0:
                        continue
                    by_commodity.setdefault(commodity, []).append(
                        {
                            "base_nick": base_nick,
                            "system": str(base_index[base_nick].get("system", "")).upper(),
                            "price": float(base_price) * multiplier,
                            "required_level": required_level,
                            "required_reputation": required_reputation,
                            "is_source": relation_flag == 0,
                        }
                    )
        return by_commodity

    def _add_implicit_base_price_sinks(
        self,
        entries_by_commodity: dict[str, list[dict[str, object]]],
        base_index: dict[str, dict[str, object]],
        commodity_prices: dict[str, int],
    ) -> dict[str, list[dict[str, object]]]:
        result = {commodity: list(entries) for commodity, entries in entries_by_commodity.items()}
        base_nicknames = sorted(base_index.keys())
        for commodity, base_price in commodity_prices.items():
            if int(base_price or 0) <= 0:
                continue
            entries = result.setdefault(commodity, [])
            explicit_bases = {
                str(entry.get("base_nick", "")).strip().lower()
                for entry in entries
                if str(entry.get("base_nick", "")).strip()
            }
            for base_nick in base_nicknames:
                if base_nick in explicit_bases:
                    continue
                entries.append(
                    {
                        "base_nick": base_nick,
                        "system": str(base_index[base_nick].get("system", "")).upper(),
                        "price": float(base_price),
                        "required_level": 0,
                        "required_reputation": -1.0,
                        "is_source": False,
                    }
                )
        return result

    def _normalize_reputation_map(self, player_reputation: dict[str, float] | None) -> dict[str, float]:
        normalized: dict[str, float] = {}
        if not isinstance(player_reputation, dict):
            return normalized
        for faction, value in player_reputation.items():
            try:
                normalized[str(faction).strip().lower()] = max(-1.0, min(1.0, float(value)))
            except (TypeError, ValueError):
                continue
        return normalized

    def _is_market_entry_accessible(
        self,
        base_index: dict[str, dict[str, object]],
        entry: dict[str, object],
        player_reputation: dict[str, float],
    ) -> bool:
        base_nick = str(entry.get("base_nick", "")).strip().lower()
        base_info = base_index.get(base_nick, {})
        faction = str(base_info.get("faction", "")).strip().lower()
        current_reputation = float(player_reputation.get(faction, 0.0)) if faction else 0.0
        required_reputation = float(entry.get("required_reputation", -1.0) or -1.0)
        if faction and current_reputation < 0.0:
            return False
        if required_reputation > -1.0 and current_reputation < required_reputation:
            return False
        return True

    def _build_system_index(self, universe_file: Path | None, resource_dlls: list[Path]) -> dict[str, dict[str, object]]:
        if universe_file is None or not universe_file.exists():
            return {}
        result: dict[str, dict[str, object]] = {}
        for section_name, entries in self._parse_ini_file(universe_file):
            if section_name.lower() != "system":
                continue
            values = {key.lower(): value for key, value in entries}
            nickname = values.get("nickname", "").strip().upper()
            if not nickname:
                continue
            display_name = self.cheat_service._resolve_ids_name(
                self.cheat_service._parse_int(values.get("ids_name") or values.get("strid_name")),
                resource_dlls,
            )
            result[nickname] = {
                "nickname": nickname,
                "display_name": display_name or nickname,
                "file": values.get("file", ""),
            }
        return result

    def _build_base_index(self, universe_file: Path | None, resource_dlls: list[Path]) -> dict[str, dict[str, object]]:
        if universe_file is None or not universe_file.exists():
            return {}
        result: dict[str, dict[str, object]] = {}
        for section_name, entries in self._parse_ini_file(universe_file):
            if section_name.lower() != "base":
                continue
            values = {key.lower(): value for key, value in entries}
            nickname = values.get("nickname", "").strip().lower()
            if not nickname:
                continue
            system_nick = values.get("system", "").strip().upper()
            display_name = self.cheat_service._resolve_ids_name(
                self.cheat_service._parse_int(values.get("strid_name") or values.get("ids_name")),
                resource_dlls,
            )
            result[nickname] = {
                "display_name": display_name or nickname,
                "system": system_nick,
            }
        return result

    def _build_system_adjacency(
        self,
        universe_file: Path | None,
        locked_gate_hashes: set[int] | None = None,
    ) -> dict[str, set[str]]:
        if universe_file is None or not universe_file.exists():
            return {}
        systems_dir = universe_file.parent / "SYSTEMS"
        adjacency: dict[str, set[str]] = {}
        if not systems_dir.exists():
            return adjacency
        locked = locked_gate_hashes or set()
        for system_dir in systems_dir.iterdir():
            if not system_dir.is_dir():
                continue
            system_file = next(
                (
                    candidate
                    for candidate in system_dir.iterdir()
                    if candidate.is_file()
                    and candidate.suffix.lower() == ".ini"
                    and candidate.stem.lower() == system_dir.name.lower()
                ),
                None,
            )
            if system_file is None:
                continue
            current_system = system_dir.name.upper()
            adjacency.setdefault(current_system, set())
            for section_name, entries in self._parse_ini_file(system_file):
                if section_name.lower() != "object":
                    continue
                nickname = ""
                goto_value = ""
                for key, value in entries:
                    key_lower = key.lower()
                    if key_lower == "nickname":
                        nickname = value.strip()
                    elif key_lower == "goto":
                        goto_value = value.strip()
                if not goto_value:
                    continue
                if locked and nickname:
                    obj_hash = self._fl_hash_nickname(nickname)
                    if obj_hash in locked:
                        continue
                target = goto_value.split(",", 1)[0].strip().upper()
                if not target:
                    continue
                adjacency.setdefault(current_system, set()).add(target)
                adjacency.setdefault(target, set()).add(current_system)
        return adjacency

    def _system_path_bfs(self, adjacency: dict[str, set[str]], src: str, dst: str) -> list[str]:
        src_upper = str(src).upper()
        dst_upper = str(dst).upper()
        if not src_upper or not dst_upper:
            return []
        if src_upper == dst_upper:
            return [src_upper]
        queue: deque[str] = deque([src_upper])
        previous: dict[str, str | None] = {src_upper: None}
        while queue:
            current = queue.popleft()
            for next_system in sorted(adjacency.get(current, set())):
                if next_system in previous:
                    continue
                previous[next_system] = current
                if next_system == dst_upper:
                    path: list[str] = []
                    node: str | None = dst_upper
                    while node is not None:
                        path.append(node)
                        node = previous.get(node)
                    return list(reversed(path))
                queue.append(next_system)
        return []

    def _commodity_fallback_name(self, nickname: str) -> str:
        raw = str(nickname or "").strip()
        if raw.lower().startswith("commodity_"):
            raw = raw[len("commodity_") :]
        parts = [part for part in raw.split("_") if part]
        return " ".join(part[:1].upper() + part[1:] for part in parts) or nickname

    # ------------------------------------------------------------------
    # Freelancer nickname hash (CreateID) – used for locked-gate lookup
    # ------------------------------------------------------------------
    _FL_HASH_TABLE: list[int] | None = None

    @classmethod
    def _fl_hash_table(cls) -> list[int]:
        if cls._FL_HASH_TABLE is not None:
            return cls._FL_HASH_TABLE
        poly = (0xA001 << (30 - 16)) & 0xFFFFFFFF
        table: list[int] = []
        for i in range(256):
            c = i
            for _ in range(8):
                c = ((c >> 1) ^ poly) if (c & 1) else (c >> 1)
            table.append(c & 0xFFFFFFFF)
        cls._FL_HASH_TABLE = table
        return table

    @classmethod
    def _fl_hash_nickname(cls, nickname: str) -> int:
        txt = str(nickname or "").strip().lower()
        if not txt:
            return 0
        table = cls._fl_hash_table()
        h = 0
        for b in txt.encode("latin1", errors="ignore"):
            h = ((h >> 8) ^ table[(h ^ b) & 0xFF]) & 0xFFFFFFFF
        h = ((h >> 24) | ((h >> 8) & 0x0000FF00) | ((h << 8) & 0x00FF0000) | ((h << 24) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = ((h >> (32 - 30)) | 0x80000000) & 0xFFFFFFFF
        return int(h)

    def _load_locked_gate_hashes(self, universe_file: Path | None) -> set[int]:
        if universe_file is None:
            return set()
        data_dir = universe_file.parent.parent
        iw_file = self._ci_resolve(data_dir, "initialworld.ini")
        if iw_file is None or not iw_file.is_file():
            return set()
        hashes: set[int] = set()
        for section_name, entries in self._parse_ini_file(iw_file):
            if section_name.lower() != "locked_gates":
                continue
            for key, value in entries:
                if key.lower() != "locked_gate":
                    continue
                try:
                    hashes.add(int(value.strip()))
                except ValueError:
                    continue
        return hashes

    def _build_system_visual_cache(
        self,
        layout: InstallationLayout,
        system_index: dict[str, dict[str, object]],
        base_index: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        universe_root = layout.universe_file.parent if layout.universe_file is not None else None
        for system_nick, system_info in system_index.items():
            relative_path = str(system_info.get("file", "")).strip()
            if not relative_path or universe_root is None:
                result[system_nick] = self._empty_system_cache(system_nick, system_index)
                continue
            system_file = self._ci_resolve(universe_root, relative_path)
            if system_file is None or not system_file.is_file():
                result[system_nick] = self._empty_system_cache(system_nick, system_index)
                continue

            objects: list[TradeRoutePreviewObject] = []
            jump_links: dict[str, list[tuple[float, float]]] = {}
            lane_map: dict[str, tuple[float, float]] = {}
            lane_next: list[tuple[str, str]] = []
            for section_name, entries in self._parse_ini_file(system_file):
                if section_name.lower() != "object":
                    continue
                values = {key.lower(): value for key, value in entries}
                nickname = str(values.get("nickname", "")).strip()
                archetype = str(values.get("archetype", "")).strip().lower()
                position = self._parse_2d_position(values.get("pos", "0,0,0"))
                label = nickname

                base_nick = str(values.get("base") or values.get("dock_with") or "").strip().lower()
                if base_nick and base_nick in base_index:
                    label = str(base_index[base_nick].get("display_name") or nickname)
                    base_index[base_nick]["pos"] = position

                goto_value = str(values.get("goto", "")).strip()
                if goto_value:
                    destination_system = goto_value.split(",", 1)[0].strip().upper()
                    if destination_system:
                        jump_links.setdefault(destination_system, []).append(position)

                if "trade_lane_ring" in archetype or "tradelane_ring" in archetype:
                    lane_map[nickname.lower()] = position
                    next_ring = str(values.get("next_ring", "")).strip().lower()
                    if next_ring:
                        lane_next.append((nickname.lower(), next_ring))

                objects.append(
                    TradeRoutePreviewObject(
                        nickname=nickname,
                        label=label,
                        archetype=archetype,
                        position=position,
                    )
                )

            lane_edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
            for start_key, next_key in lane_next:
                if start_key in lane_map and next_key in lane_map:
                    lane_edges.append((lane_map[start_key], lane_map[next_key]))

            result[system_nick] = {
                "nickname": system_nick,
                "display_name": str(system_info.get("display_name", system_nick)),
                "objects": objects,
                "jump_links": jump_links,
                "lane_edges": lane_edges,
            }
        return result

    def _empty_system_cache(self, system_nick: str, system_index: dict[str, dict[str, object]]) -> dict[str, object]:
        return {
            "nickname": system_nick,
            "display_name": str(system_index.get(system_nick, {}).get("display_name", system_nick)),
            "objects": [],
            "jump_links": {},
            "lane_edges": [],
        }

    def _coerce_point(self, value: object) -> tuple[float, float] | None:
        if isinstance(value, tuple) and len(value) >= 2:
            return (float(value[0]), float(value[1]))
        return None

    def _parse_2d_position(self, raw_value: object) -> tuple[float, float]:
        parts = [part.strip() for part in str(raw_value or "0,0,0").split(",")]
        if len(parts) < 3:
            parts += ["0"] * (3 - len(parts))
        try:
            return (float(parts[0]), float(parts[2]))
        except ValueError:
            return (0.0, 0.0)

    def _pick_jump_point(
        self,
        system_info: dict[str, object],
        target_system_nick: str,
        anchor: tuple[float, float] | None,
    ) -> tuple[float, float] | None:
        candidates = list(system_info.get("jump_links", {}).get(str(target_system_nick).upper(), []))
        if not candidates:
            return None
        if anchor is None:
            return tuple(candidates[0])
        best_candidate: tuple[float, float] | None = None
        best_distance: float | None = None
        for candidate in candidates:
            distance = self._distance2d(candidate, anchor)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_candidate = tuple(candidate)
        return best_candidate

    def _trade_route_local_path(
        self,
        system_info: dict[str, object],
        start_pt: tuple[float, float] | None,
        end_pt: tuple[float, float] | None,
    ) -> list[tuple[float, float]]:
        if start_pt is None and end_pt is None:
            return []
        if start_pt is None:
            return [end_pt] if end_pt is not None else []
        if end_pt is None:
            return [start_pt]

        lane_edges = list(system_info.get("lane_edges", []))
        nodes: list[tuple[float, float]] = [start_pt, end_pt]
        node_index: dict[tuple[int, int], int] = {
            (int(round(start_pt[0] * 10)), int(round(start_pt[1] * 10))): 0,
            (int(round(end_pt[0] * 10)), int(round(end_pt[1] * 10))): 1,
        }

        def add_node(point: tuple[float, float]) -> int:
            key = (int(round(point[0] * 10)), int(round(point[1] * 10)))
            if key in node_index:
                return node_index[key]
            node_index[key] = len(nodes)
            nodes.append(point)
            return node_index[key]

        for edge_start, edge_end in lane_edges:
            add_node(edge_start)
            add_node(edge_end)

        adjacency: list[list[tuple[int, float]]] = [[] for _ in range(len(nodes))]

        def link(a_index: int, b_index: int, weight: float) -> None:
            adjacency[a_index].append((b_index, weight))
            adjacency[b_index].append((a_index, weight))

        link(0, 1, self._distance2d(start_pt, end_pt))
        for node in range(2, len(nodes)):
            link(0, node, self._distance2d(start_pt, nodes[node]))
            link(1, node, self._distance2d(end_pt, nodes[node]))

        for edge_start, edge_end in lane_edges:
            a_index = add_node(edge_start)
            b_index = add_node(edge_end)
            link(a_index, b_index, self._distance2d(edge_start, edge_end) * 0.35)

        distances = [float("inf")] * len(nodes)
        previous = [-1] * len(nodes)
        visited = [False] * len(nodes)
        distances[0] = 0.0
        for _ in range(len(nodes)):
            current = -1
            best_distance = float("inf")
            for index, value in enumerate(distances):
                if not visited[index] and value < best_distance:
                    best_distance = value
                    current = index
            if current < 0 or current == 1:
                break
            visited[current] = True
            for next_index, weight in adjacency[current]:
                candidate_distance = distances[current] + weight
                if candidate_distance < distances[next_index]:
                    distances[next_index] = candidate_distance
                    previous[next_index] = current

        if previous[1] < 0:
            return [start_pt, end_pt]

        ordered_indices = [1]
        current = 1
        while current != 0 and current >= 0:
            current = previous[current]
            if current >= 0:
                ordered_indices.append(current)
        ordered_indices.reverse()
        return [nodes[index] for index in ordered_indices]

    def _distance2d(self, first: tuple[float, float], second: tuple[float, float]) -> float:
        dx = float(first[0]) - float(second[0])
        dy = float(first[1]) - float(second[1])
        return (dx * dx + dy * dy) ** 0.5
