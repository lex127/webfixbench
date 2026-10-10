"""Pinned literal API instructions; explicit ordered bundles, no execution."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ConfigError, Prompt, find_root

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _validate_file(entry: Any) -> None:
    allowed = {'path', 'sha256', 'resources', 'tree_sha256'}
    if not isinstance(entry, dict) or not {'path', 'sha256'} <= set(entry) or set(entry) - allowed:
        raise ConfigError('pinned instruction file requires only path and sha256')
    path = entry['path']
    if not isinstance(path, str) or not path or Path(path).is_absolute() or '..' in Path(path).parts:
        raise ConfigError('condition path must be a repository-relative path without traversal')
    digest = entry['sha256']
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        raise ConfigError('condition sha256 must be a lowercase SHA-256 digest')
    if 'tree_sha256' in entry and (not isinstance(entry['tree_sha256'], str) or not DIGEST.fullmatch(entry['tree_sha256'])):
        raise ConfigError('tree_sha256 must be a lowercase SHA-256 digest')
    if 'resources' in entry:
        if not isinstance(entry['resources'], list):
            raise ConfigError('resources must be an ordered array')
        for resource in entry['resources']:
            if not isinstance(resource, dict) or set(resource) != {'path', 'sha256'}:
                raise ConfigError('resource entries require only path and sha256')
            _validate_file(resource)


def validate_conditions(entries: Any) -> List[Dict[str, Any]]:
    if not isinstance(entries, list) or not entries:
        raise ConfigError('conditions must be a non-empty array')
    checked = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError('each condition must be an object')
        cid = entry.get('condition_id')
        if not isinstance(cid, str) or not ID.fullmatch(cid):
            raise ConfigError('condition_id must be a safe identifier')
        if cid.casefold() in seen:
            raise ConfigError('duplicate condition_id (case-insensitive)')
        seen.add(cid.casefold())
        kind = entry.get('kind')
        fields = {'condition_id', 'kind'}
        if kind in ('single_skill', 'generic_checklist'):
            fields |= {'path', 'sha256'} | (set(entry) & {'resources', 'tree_sha256'})
            _validate_file({k: v for k, v in entry.items() if k not in ('kind', 'condition_id')})
        elif kind == 'bundle':
            fields.add('skills')
            items = entry.get('skills')
            if not isinstance(items, list) or not items:
                raise ConfigError('bundle skills must be a non-empty ordered array')
            for item in items:
                _validate_file(item)
        elif kind != 'baseline':
            raise ConfigError('unsupported condition kind')
        if set(entry) != fields:
            raise ConfigError('unknown or missing condition fields')
        checked.append(dict(entry))
    return checked


def _read_file(entry: Dict[str, Any], base: Path) -> Dict[str, Any]:
    path = (base / entry['path']).resolve()
    if not path.is_relative_to(base):
        raise ConfigError('condition path resolves outside benchmark root')
    try:
        raw = path.read_bytes()
        text = raw.decode('utf-8')
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f'cannot read condition text: {entry["path"]}') from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry['sha256']:
        raise ConfigError(f'condition SHA-256 mismatch: {entry["path"]}')
    if not text.strip():
        raise ConfigError('condition text must not be empty')
    return {**entry, 'text': text, 'bytes': len(raw)}


def fingerprint_skill_tree(directory: Path, root: Path) -> Dict[str, Any]:
    directory = directory.resolve()
    if not directory.is_relative_to(root.resolve()) or not directory.is_dir():
        raise ConfigError('skill tree must be a directory inside benchmark root')
    inventory = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ConfigError('skill tree must not contain symlinks')
        if path.is_file():
            raw = path.read_bytes()
            inventory.append({'path': path.relative_to(directory).as_posix(),
                              'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    canonical = json.dumps(inventory, sort_keys=True, separators=(',', ':'))
    return {'sha256': hashlib.sha256(canonical.encode()).hexdigest(), 'inventory': inventory}


def _materialize_skill(entry: Dict[str, Any], base: Path):
    tree = None
    if 'tree_sha256' in entry:
        tree = fingerprint_skill_tree((base / entry['path']).parent, base)
        if tree['sha256'] != entry['tree_sha256']:
            raise ConfigError('skill tree SHA-256 mismatch')
    files = [_read_file({k: entry[k] for k in ('path', 'sha256')}, base)]
    for resource in entry.get('resources', []):
        if tree is not None and not (base / resource['path']).resolve().is_relative_to((base / entry['path']).parent.resolve()):
            raise ConfigError('resource escapes pinned skill tree')
        files.append(_read_file(resource, base))
    return files, tree


def materialize_conditions(entries: Optional[List[Dict[str, Any]]], prompt: Prompt,
                           root: Optional[Path]) -> List[Dict[str, Any]]:
    if entries is None:
        return [{'condition_id': 'baseline', 'kind': 'baseline', 'prompt': prompt,
                 'text': '', 'sha256': None}]
    base = (root or find_root()).resolve()
    conditions = []
    for entry in validate_conditions(entries):
        files = []
        trees = []
        if entry['kind'] == 'bundle':
            for item in entry['skills']:
                delivered, tree = _materialize_skill(item, base)
                files.extend(delivered)
                if tree is not None:
                    trees.append(tree)
        elif entry['kind'] != 'baseline':
            delivered, tree = _materialize_skill(entry, base)
            files.extend(delivered)
            if tree is not None:
                trees.append(tree)
        text = '\n\n'.join(item['text'] for item in files)
        digest = None
        if files:
            digest = files[0]['sha256']
            if entry['kind'] == 'bundle' or len(files) > 1 or trees:
                identity = [{k: f[k] for k in ('path', 'sha256')} for f in files]
                digest = hashlib.sha256(json.dumps({'delivered_files': identity, 'trees': trees}, separators=(',', ':')).encode()).hexdigest()
        conditions.append({**entry, 'text': text, 'sha256': digest, 'files': files, 'trees': trees,
                           'instruction_bytes': len(text.encode()),
                           'prompt': Prompt(prompt.id, prompt.text, prompt.sha256, text)})
    return conditions
