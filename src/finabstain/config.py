from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import yaml

@dataclass
class ModelConfig:
    name: str
    think: Optional[str] = None
    num_predict: int = 1024

@dataclass
class LLMConfig:
    backend: str = "ollama"
    base_url: str = "https://ollama.com"
    workers: int = 2
    max_retries: int = 3
    backoff_seconds: List[int] = field(default_factory=lambda: [2, 4, 8, 16, 32, 60])
    models: Dict[str, ModelConfig] = field(default_factory=dict)

@dataclass
class DataConfig:
    raw_dir: str = "data/raw"
    out_dir: str = "out"

@dataclass
class SectionsConfig:
    min_words: int = 200
    max_words: int = 600
    min_numbers: int = 3

@dataclass
class PaddingConfig:
    target_tokens: List[int] = field(default_factory=lambda: [8000])
    position: str = "random"

@dataclass
class AnonymizeConfig:
    scale_factor_range: List[float] = field(default_factory=lambda: [0.55, 1.8])
    fake_company_name: str = "Aldervane Holdings"

@dataclass
class ChecksConfig:
    conflict_min_rel_diff: float = 0.05
    max_inserted_words: int = 60
    min_kept_ratio_missing: float = 0.70

@dataclass
class AuditConfig:
    n_items: int = 20

@dataclass
class AppConfig:
    seed: int = 42
    data: DataConfig = field(default_factory=DataConfig)
    sections: SectionsConfig = field(default_factory=SectionsConfig)
    candidates_per_category: int = 40
    final_per_category: int = 25
    padding: PaddingConfig = field(default_factory=PaddingConfig)
    anonymize: AnonymizeConfig = field(default_factory=AnonymizeConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    checks: ChecksConfig = field(default_factory=ChecksConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    raw_dict: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(p, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppConfig:
        d_cfg = DataConfig(**data.get("data", {}))
        s_cfg = SectionsConfig(**data.get("sections", {}))
        p_cfg = PaddingConfig(**data.get("padding", {}))
        a_cfg = AnonymizeConfig(**data.get("anonymize", {}))
        c_cfg = ChecksConfig(**data.get("checks", {}))
        au_cfg = AuditConfig(**data.get("audit", {}))

        llm_raw = data.get("llm", {})
        models_raw = llm_raw.get("models", {})
        models_dict = {}
        for role, m_dict in models_raw.items():
            models_dict[role] = ModelConfig(
                name=m_dict.get("name", ""),
                think=m_dict.get("think"),
                num_predict=m_dict.get("num_predict", 1024),
            )

        llm_cfg = LLMConfig(
            backend=llm_raw.get("backend", "ollama"),
            base_url=llm_raw.get("base_url", "https://ollama.com"),
            workers=llm_raw.get("workers", 2),
            max_retries=llm_raw.get("max_retries", 3),
            backoff_seconds=llm_raw.get("backoff_seconds", [2, 4, 8, 16, 32, 60]),
            models=models_dict,
        )

        return cls(
            seed=data.get("seed", 42),
            data=d_cfg,
            sections=s_cfg,
            candidates_per_category=data.get("candidates_per_category", 40),
            final_per_category=data.get("final_per_category", 25),
            padding=p_cfg,
            anonymize=a_cfg,
            llm=llm_cfg,
            checks=c_cfg,
            audit=au_cfg,
            raw_dict=data,
        )
