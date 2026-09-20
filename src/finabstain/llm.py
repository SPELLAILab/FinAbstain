from __future__ import annotations
import os
import sys
import json
import time
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests

from .config import LLMConfig, ModelConfig

def sha256_key(data: Dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def extract_balanced_json(text: str) -> Optional[Dict[str, Any]]:
    """Extracts the outermost balanced JSON object {...} from text."""
    if not text:
        return None
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()

    start_idx = cleaned.find("{")
    if start_idx == -1:
        return None

    brace_depth = 0
    in_string = False
    escape = False

    for i in range(start_idx, len(cleaned)):
        char = cleaned[i]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    json_str = cleaned[start_idx:i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        break
    # Fallback to standard regex if bracket counting failed
    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None

class LLMClient:
    def __init__(self, config: LLMConfig, cache_dir: str | Path, seed: int = 42):
        self.config = config
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.api_key = os.getenv("OLLAMA_API_KEY", "").strip()
        self.consecutive_failures = 0

        # Determine effective base_url
        env_base = os.getenv("OLLAMA_API_BASE", "").strip()
        if env_base:
            self.base_url = env_base
        elif not self.api_key and self.config.base_url == "https://ollama.com":
            # If no API key is set, check if local ollama daemon is reachable
            if self._is_local_reachable("http://127.0.0.1:11434"):
                self.base_url = "http://127.0.0.1:11434"
            else:
                self.base_url = self.config.base_url
        else:
            self.base_url = self.config.base_url

        self.tag_mapping: Dict[str, str] = {}
        if self.config.backend == "ollama":
            self._resolve_and_verify_models()

    def _is_local_reachable(self, url: str) -> bool:
        try:
            r = requests.get(f"{url}/api/tags", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def _resolve_and_verify_models(self):
        """Discovers available models and verifies configured models exist."""
        available_tags = []
        tags_url = f"{self.base_url}/api/tags"
        headers = {}
        if self.api_key and "ollama.com" in self.base_url:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = requests.get(tags_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    remote = m.get("remote_model", "")
                    model = m.get("model", "")
                    for candidate in [name, remote, model]:
                        if candidate and candidate not in available_tags:
                            available_tags.append(candidate)
            else:
                # Fallback to /v1/models
                v1_url = f"{self.base_url}/v1/models"
                resp_v1 = requests.get(v1_url, headers=headers, timeout=5)
                if resp_v1.status_code == 200:
                    for m in resp_v1.json().get("data", []):
                        mid = m.get("id", "")
                        if mid and mid not in available_tags:
                            available_tags.append(mid)
        except Exception as e:
            # If network failed and local fallback is possible
            if self.base_url != "http://127.0.0.1:11434" and self._is_local_reachable("http://127.0.0.1:11434"):
                self.base_url = "http://127.0.0.1:11434"
                return self._resolve_and_verify_models()
            raise RuntimeError(f"Could not connect to Ollama at {self.base_url}: {e}")

        # Map configured model names
        missing = []
        for role, m_cfg in self.config.models.items():
            wanted = m_cfg.name
            matched = None
            is_local = "127.0.0.1" in self.base_url or "localhost" in self.base_url
            if is_local:
                if f"{wanted}:cloud" in available_tags:
                    matched = f"{wanted}:cloud"
                elif f"{wanted}-cloud" in available_tags:
                    matched = f"{wanted}-cloud"
                elif wanted in available_tags:
                    matched = wanted
            else:
                if wanted in available_tags:
                    matched = wanted
                elif f"{wanted}:cloud" in available_tags:
                    matched = f"{wanted}:cloud"
                elif f"{wanted}-cloud" in available_tags:
                    matched = f"{wanted}-cloud"

            if not matched:
                for tag in available_tags:
                    if tag.startswith(f"{wanted}:") or tag.startswith(f"{wanted}-"):
                        matched = tag
                        break

            if matched:
                self.tag_mapping[wanted] = matched
            else:
                missing.append(wanted)

        if missing:
            msg = (
                f"Configured Ollama model tag(s) {missing} not found on {self.base_url}.\n"
                f"Available tags on {self.base_url}:\n" + "\n".join(f"  - {t}" for t in sorted(available_tags))
            )
            raise RuntimeError(msg)

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_cache(self, key: str, data: Dict[str, Any]) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def call_chat(
        self,
        model_role: str,
        messages: List[Dict[str, str]],
        json_format: bool = True,
        stats_tracker: Optional[Any] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
        """
        Calls Ollama chat endpoint.
        Returns (raw_content, parsed_json, from_cache).
        """
        if self.config.backend == "mock":
            return self._mock_call(model_role, messages, stats_tracker)

        m_cfg = self.config.models.get(model_role)
        if not m_cfg:
            raise ValueError(f"Unknown model role: {model_role}")

        resolved_model = self.tag_mapping.get(m_cfg.name, m_cfg.name)

        options: Dict[str, Any] = {
            "temperature": 0,
            "seed": self.seed,
            "num_predict": m_cfg.num_predict,
        }

        payload: Dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if json_format:
            payload["format"] = "json"
        if m_cfg.think:
            payload["think"] = m_cfg.think

        cache_key = sha256_key(payload)
        cached = self._get_cache(cache_key)
        if cached is not None:
            if stats_tracker:
                stats_tracker.cache_hits += 1
            raw_text = cached.get("content", "")
            parsed = extract_balanced_json(raw_text) if json_format else None
            return raw_text, parsed, True

        # Perform actual HTTP call with retries and backoff
        headers = {"Content-Type": "application/json"}
        if self.api_key and "ollama.com" in self.base_url:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/api/chat"
        backoffs = self.config.backoff_seconds

        for attempt in range(self.config.max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                if resp.status_code == 200:
                    self.consecutive_failures = 0
                    if stats_tracker:
                        stats_tracker.llm_calls += 1
                    data = resp.json()
                    msg_obj = data.get("message", {})
                    raw_text = msg_obj.get("content", "")
                    parsed = extract_balanced_json(raw_text) if json_format else None

                    self._save_cache(cache_key, {"content": raw_text, "raw": data})
                    return raw_text, parsed, False

                # Handle Quota / 429
                if resp.status_code in (429, 403):
                    resp_text = resp.text.lower()
                    if "quota" in resp_text or "limit" in resp_text or attempt == self.config.max_retries:
                        print("Quota hit. Rerun the same command after the usage window resets (~5 h).", file=sys.stderr)
                        sys.exit(75)

                # Retry on 5xx or transient 429
                self.consecutive_failures += 1
                if self.consecutive_failures >= 5:
                    print("Quota hit. Rerun the same command after the usage window resets (~5 h).", file=sys.stderr)
                    sys.exit(75)

            except (requests.RequestException, Exception) as e:
                self.consecutive_failures += 1
                if self.consecutive_failures >= 5:
                    print(f"Network error: {e}. Consecutive failure threshold reached.", file=sys.stderr)
                    sys.exit(75)

            # Sleep backoff
            sleep_sec = backoffs[min(attempt, len(backoffs) - 1)]
            time.sleep(sleep_sec)

        return None, None, False

    def _mock_call(
        self,
        model_role: str,
        messages: List[Dict[str, str]],
        stats_tracker: Optional[Any] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
        if stats_tracker:
            stats_tracker.llm_calls += 1

        prompt = messages[-1].get("content", "") if messages else ""

        # Mock QGEN
        if "building a reading-comprehension test" in prompt:
            parts = prompt.split("Excerpt:")
            sec_text = parts[-1].strip() if len(parts) > 1 else prompt
            lines = [l.strip() for l in sec_text.splitlines() if l.strip()]
            sample_line = lines[0] if lines else "Aldervane Holdings, Inc."
            for l in lines:
                if any(c.isdigit() for c in l) and len(l) > 10:
                    sample_line = l
                    break
            nums = re.findall(r"\(?\$?[-+]?\d[\d,]*\.?\d*%?\)?", sample_line)
            ans = nums[0] if nums else "$637,959"
            mock_obj = {
                "question": "What was the reported total for the enterprise?",
                "answer": ans,
                "evidence_span": sample_line,
                "fact_type": "amount",
            }
            return json.dumps(mock_obj), mock_obj, False

        # Mock EDIT MISSING
        elif "Remove the information that answers the question" in prompt:
            parts = prompt.split("Excerpt:")
            sec_text = parts[-1].strip() if len(parts) > 1 else prompt
            ans_match = re.search(r"Answer:\s*(.*)", prompt)
            ans = ans_match.group(1).strip() if ans_match else ""
            del_span = ans
            for l in sec_text.splitlines():
                if ans and ans in l and len(l.strip()) > 0:
                    del_span = l.strip()
                    break
            mock_obj = {"deletions": [del_span]}
            return json.dumps(mock_obj), mock_obj, False

        # Mock EDIT CONFLICT
        elif "states TWO different, contradictory values" in prompt:
            parts = prompt.split("Excerpt:")
            sec_text = parts[-1].strip() if len(parts) > 1 else prompt
            lines = [l.strip() for l in sec_text.splitlines() if len(l.strip()) > 10]
            anchor = lines[0] if lines else "Anchor line"
            mock_obj = {
                "anchor": anchor,
                "inserted_text": "In a separate note, the reported total was $895,400 million.",
                "conflicting_value": "$895,400 million",
            }
            return json.dumps(mock_obj), mock_obj, False

        # Mock EDIT AMBIGUOUS
        elif "Make the question ambiguous" in prompt:
            parts = prompt.split("Excerpt:")
            sec_text = parts[-1].strip() if len(parts) > 1 else prompt
            lines = [l.strip() for l in sec_text.splitlines() if len(l.strip()) > 10]
            anchor = lines[0] if lines else "Anchor line"
            mock_obj = {
                "anchor": anchor,
                "inserted_text": "For the secondary segment, the reported total was $410,000 million.",
                "distractor_value": "$410,000 million",
                "blurred_dimension": "segment",
                "new_question": "What was the reported total?",
                "removed_from_question": ["enterprise?"],
            }
            return json.dumps(mock_obj), mock_obj, False

        # Mock VALIDATE
        elif "expert financial evaluator" in prompt:
            parts = prompt.split("Excerpt:")
            sec_text = parts[-1].strip() if len(parts) > 1 else prompt

            if "In a separate note" in sec_text:
                cat = "conflict"
            elif "secondary segment" in sec_text:
                cat = "ambiguous"
            elif not any(c.isdigit() for c in sec_text):
                cat = "missing"
            else:
                # Check if original answer line is missing
                q_match = re.search(r"Question:\s*(.*)", prompt)
                q_str = q_match.group(1).strip() if q_match else ""
                if q_str == "What was the reported total?":
                    cat = "ambiguous"
                elif "deletions" in prompt or "deletions" in sec_text or "Note 1" not in sec_text and "Total net sales" not in sec_text:
                    cat = "missing"
                else:
                    cat = "answerable"

            mock_obj = {
                "label": cat,
                "answer": "none" if cat != "answerable" else "$637,959",
                "rationale": f"Deterministic mock validation for {cat}.",
            }
            return json.dumps(mock_obj), mock_obj, False

        return "{}", {}, False
