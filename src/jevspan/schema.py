"""Zero-shot entity schema: a name, a one-line definition and a few examples per type."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

RESERVED = {"none", "mixed", "partial", "NONE"}


@dataclass(frozen=True)
class EntityType:
    name: str
    title: str
    description: str
    examples: tuple[str, ...] = field(default_factory=tuple)
    counter_examples: tuple[str, ...] = field(default_factory=tuple)
    include_brackets: bool = False
    min_chars: int = 2

    def criterion(self, compact: bool = False) -> str:
        text = f"{self.title}：{self.description}"
        if compact:
            return text
        if self.examples:
            text += f"，例如 {'、'.join(self.examples)}"
        if self.counter_examples:
            text += f"（不包括 {'、'.join(self.counter_examples)}）"
        return text


@dataclass(frozen=True)
class Schema:
    types: tuple[EntityType, ...]

    def __post_init__(self):
        if not self.types:
            raise ValueError("schema needs at least one entity type")
        names = [t.name for t in self.types]
        if len(set(names)) != len(names):
            raise ValueError("duplicate entity type names")
        for name in names:
            if name in RESERVED:
                raise ValueError(f"'{name}' is a reserved label")

    @property
    def names(self) -> list[str]:
        return [t.name for t in self.types]

    @property
    def titles(self) -> str:
        return "/".join(t.title for t in self.types)

    def get(self, name: str) -> EntityType:
        for t in self.types:
            if t.name == name:
                return t
        raise KeyError(name)

    def criteria(self) -> dict[str, str]:
        return {t.name: t.criterion() for t in self.types}

    @classmethod
    def from_dict(cls, data: dict) -> "Schema":
        """Accepts {"entities": {name: {...}}}, {name: {...}} or {name: "description"}."""
        entities = data.get("entities", data)
        types = []
        for name, spec in entities.items():
            if isinstance(spec, str):
                spec = {"description": spec}
            types.append(
                EntityType(
                    name=name,
                    title=spec.get("title", name),
                    description=spec.get("description", ""),
                    examples=tuple(spec.get("examples", ())),
                    counter_examples=tuple(spec.get("counter_examples", ())),
                    include_brackets=bool(spec.get("include_brackets", False)),
                    min_chars=int(spec.get("min_chars", 2)),
                )
            )
        return cls(tuple(types))

    @classmethod
    def load(cls, path: str | Path) -> "Schema":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return {
            "entities": {
                t.name: {
                    "title": t.title,
                    "description": t.description,
                    "examples": list(t.examples),
                    "counter_examples": list(t.counter_examples),
                    "include_brackets": t.include_brackets,
                    "min_chars": t.min_chars,
                }
                for t in self.types
            }
        }


DEFAULT_SCHEMA = Schema(
    (
        EntityType(
            "person", "人名", "某个具体人物的姓名，不含先生/教授/经理等称谓和职务",
            ("张伟", "欧阳娜娜", "Elon Musk"),
        ),
        EntityType(
            "organization", "机构", "公司、学校、医院、银行、政府部门、协会、团体等组织的名称",
            ("北京大学", "阿里巴巴集团", "国家统计局", "Microsoft"),
        ),
        EntityType(
            "address", "地址", "国家、省、市、区县、乡镇、街道、门牌号、小区、楼宇、园区等地理位置",
            ("杭州", "上海市浦东新区世纪大道100号", "London"),
        ),
    )
)
