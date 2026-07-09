"""
CCF 等级映射模块
从 ccf_venues.json 构建 venue → level 查找表。
"""

import os
import json


class CCFMapper:
    """CCF 会议/期刊等级查找"""

    def __init__(self, json_path: str = None):
        if json_path is None:
            json_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "ccf_venues.json"
            )

        self.abbr_to_level: dict[str, str] = {}
        self.fullname_to_level: dict[str, str] = {}

        self._load(json_path)

    def _load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for category in data:
            for level in ["A", "B", "C"]:
                venues = category.get(level, [])
                for venue in venues:
                    abbr = venue.get("abbr", "").strip()
                    full_name = venue.get("full_name", "").strip()
                    if abbr:
                        self.abbr_to_level[abbr.upper()] = level
                    if full_name:
                        self.fullname_to_level[full_name.lower()] = level

    def get_level(self, venue: str) -> str | None:
        """
        查询 venue 的 CCF 等级。
        返回 "A" / "B" / "C" 或 None（未收录）。
        """
        if not venue:
            return None

        # 精确匹配缩写
        upper = venue.strip().upper()
        if upper in self.abbr_to_level:
            return self.abbr_to_level[upper]

        # 精确匹配全称
        lower = venue.strip().lower()
        if lower in self.fullname_to_level:
            return self.fullname_to_level[lower]

        # 模糊匹配：venue 包含缩写
        for abbr, level in self.abbr_to_level.items():
            if abbr in upper and len(abbr) >= 3:
                return level

        # 模糊匹配：全称包含 venue
        for full, level in self.fullname_to_level.items():
            if lower in full or full in lower:
                return level

        return None
