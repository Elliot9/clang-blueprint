"""
ast_parser.py — Libclang-based AST scanner for clang-blueprint.

Walks C/C++ translation units and extracts class/struct information matching
the blueprint_index schema.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import clang.cindex as cindex
    from clang.cindex import (
        CursorKind,
        TokenKind,
        TranslationUnitLoadError,
        conf,
    )
except ImportError as e:
    raise ImportError(
        "libclang Python bindings not found. Install with: pip install libclang"
    ) from e



# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Dependency:
    target: str
    type: str  # composition | inheritance | association | dependency
    cardinality: Optional[str] = None


@dataclass
class BlueprintEntry:
    className: str
    responsibility: str
    dependencies: list[Dependency]
    interfaces: list[str]
    fileLocation: str
    lineNumber: int
    namespace: str
    baseClasses: list[str]
    templateParams: list[str]
    attributes: list[str] = field(default_factory=list)
    # UI-08: per-method line numbers for click-to-source
    interfaceMeta: list[dict] = field(default_factory=list)  # [{signature, lineNumber, usedTypes}]
    # P8-04: typedef/using aliases for this entry's scope
    typeAliases: list[dict] = field(default_factory=list)    # [{alias, canonical, depType}]
    # P10-01: protected/private methods (public ones stay in interfaces/interfaceMeta)
    privateMethods: list[dict] = field(default_factory=list)  # [{signature, lineNumber, access, usedTypes, callSequence}]

    def to_dict(self) -> dict[str, Any]:
        return {
            "className": self.className,
            "responsibility": self.responsibility,
            "dependencies": [
                {
                    "target": d.target,
                    "type": d.type,
                    **({"cardinality": d.cardinality} if d.cardinality else {}),
                }
                for d in self.dependencies
            ],
            "attributes": self.attributes,
            "interfaces": self.interfaces,
            "interfaceMeta": self.interfaceMeta,
            "typeAliases": self.typeAliases,
            "privateMethods": self.privateMethods,
            "fileLocation": self.fileLocation,
            "lineNumber": self.lineNumber,
            "namespace": self.namespace,
            "baseClasses": self.baseClasses,
            "templateParams": self.templateParams,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BUILTIN_TYPES = frozenset(
    {
        "void", "bool", "char", "short", "int", "long", "float", "double",
        "unsigned", "signed", "size_t", "uint8_t", "uint16_t", "uint32_t",
        "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t", "ptrdiff_t",
        "nullptr_t", "string", "wstring", "u16string", "u32string",
        "auto", "decltype",
    }
)

_STL_PREFIXES = (
    "std::", "__gnu_cxx::", "__cxx11::", "boost::", "absl::",
)


def _is_trivial_type(name: str) -> bool:
    """Return True if the type name is a built-in or STL type we can ignore."""
    stripped = name.lstrip(":").split("<")[0].strip()
    if stripped in _BUILTIN_TYPES:
        return True
    for prefix in _STL_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


def _canonical_type_name(cursor: Any) -> str:
    """Extract a clean type name from a cursor's type."""
    t = cursor.type
    # Unwrap pointers/refs/arrays
    while t.kind in (
        cindex.TypeKind.POINTER,
        cindex.TypeKind.LVALUEREFERENCE,
        cindex.TypeKind.RVALUEREFERENCE,
        cindex.TypeKind.INCOMPLETEARRAY,
        cindex.TypeKind.CONSTANTARRAY,
        cindex.TypeKind.VARIABLEARRAY,
    ):
        t = t.get_pointee() if hasattr(t, "get_pointee") else t.element_type
    name = t.spelling
    # Strip cv-qualifiers
    name = re.sub(r"\bconst\b|\bvolatile\b|\brestrict\b", "", name).strip()
    # Strip leading "::"
    name = name.lstrip(":")
    return name


def _get_namespace(cursor: Any) -> str:
    """Walk parent cursors to build the fully-qualified namespace string."""
    parts: list[str] = []
    parent = cursor.semantic_parent
    while parent and parent.kind not in (
        CursorKind.TRANSLATION_UNIT,
        CursorKind.INVALID_FILE,
    ):
        if parent.kind == CursorKind.NAMESPACE and parent.spelling:
            parts.append(parent.spelling)
        parent = parent.semantic_parent
    parts.reverse()
    return "::".join(parts)


def _cursor_is_in_main_file(cursor: Any, tu_file: str) -> bool:
    """Check whether a cursor lives in the file being parsed (not a header)."""
    loc = cursor.location
    if not loc.file:
        return False
    return os.path.abspath(loc.file.name) == os.path.abspath(tu_file)


def _is_definition_in_project(path: str, project_root: str) -> bool:
    """
    True if `path` (a class/struct definition site) lies under `project_root`.

    System and third-party headers live outside this tree and must not be
    indexed as blueprint classes.
    """
    try:
        abs_path = os.path.realpath(path)
        root = os.path.realpath(project_root)
    except OSError:
        return False
    if abs_path == root:
        return True
    root_prefix = root if root.endswith(os.sep) else root + os.sep
    return abs_path.startswith(root_prefix)


def _field_access_symbol(cursor: Any) -> str:
    """Mermaid-style visibility prefix: + public, # protected, - private."""
    acc = cursor.access_specifier
    if acc == cindex.AccessSpecifier.PUBLIC:
        return "+"
    if acc == cindex.AccessSpecifier.PROTECTED:
        return "#"
    return "-"


def _method_signature(cursor: Any) -> str:
    """Build a readable method signature string."""
    params = []
    for arg in cursor.get_arguments():
        params.append(f"{arg.type.spelling} {arg.spelling}".strip())
    param_str = ", ".join(params)

    if cursor.kind == CursorKind.CONSTRUCTOR:
        # libclang reports a bogus 'void' result type for constructors.
        name = cursor.spelling or ""
        return f"{name}({param_str})"

    if cursor.kind == CursorKind.DESTRUCTOR:
        name = cursor.spelling
        if not name or not name.startswith("~"):
            parent = cursor.semantic_parent
            pname = parent.spelling if parent and parent.spelling else ""
            name = f"~{pname}" if pname else "~"
        return f"{name}({param_str})"

    ret = cursor.result_type.spelling if cursor.result_type.spelling else "void"
    name = cursor.spelling
    return f"{ret} {name}({param_str})"


# ---------------------------------------------------------------------------
# P8-02: typedef / using alias collection
# ---------------------------------------------------------------------------

def _extract_inner_type(cursor: Any) -> str:
    """
    For a TYPEDEF_DECL or TYPE_ALIAS_DECL cursor, return the underlying
    canonical type spelling (stripped of cv-qualifiers and leading '::').
    """
    try:
        t = cursor.underlying_typedef_type
        # Walk through pointer/ref wrappers to get the pointee if desired,
        # but keep the raw spelling for template args (e.g. shared_ptr<Foo>)
        spelling = t.spelling if t else ""
        spelling = re.sub(r"\bconst\b|\bvolatile\b|\brestrict\b", "", spelling).strip()
        return spelling.lstrip(":")
    except Exception:
        return ""


def _dep_type_from_template(canonical: str) -> str:
    """Infer dependency type from a template alias like shared_ptr<T>, unique_ptr<T>."""
    c = canonical.replace(" ", "")
    if re.search(r"\bunique_ptr\b", c):
        return "composition"
    if re.search(r"\b(shared_ptr|weak_ptr)\b", c):
        return "aggregation"
    if "*" in canonical or re.search(r"\b(raw_ptr|ptr)\b", c):
        return "aggregation"
    return "association"


def _inner_template_arg(canonical: str) -> str:
    """Extract T from shared_ptr<T>, unique_ptr<T>, etc."""
    m = re.search(r"<([^<>]+)>", canonical)
    if not m:
        return ""
    # Strip pointer/ref/cv off the inner type
    inner = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", m.group(1)).strip().lstrip(":")
    # Handle nested namespaces: take the last component for matching
    return inner


def collect_type_aliases(tu_cursor: Any) -> dict[str, dict]:
    """
    P8-02: Walk the translation unit (including namespaces) and collect all
    typedef/using aliases.

    Returns a dict: alias_name → {canonical, depType, innerType}
    """
    aliases: dict[str, dict] = {}

    def _walk(cursor: Any) -> None:
        for child in cursor.get_children():
            if child.kind in (CursorKind.TYPEDEF_DECL, CursorKind.TYPE_ALIAS_DECL):
                alias_name = child.spelling
                if not alias_name:
                    continue
                canonical = _extract_inner_type(child)
                if not canonical:
                    continue
                inner = _inner_template_arg(canonical)
                dep_type = _dep_type_from_template(canonical)
                aliases[alias_name] = {
                    "canonical": canonical,
                    "innerType": inner,
                    "depType":   dep_type,
                }
            elif child.kind == CursorKind.NAMESPACE:
                _walk(child)

    _walk(tu_cursor)
    return aliases


# ---------------------------------------------------------------------------
# Core visitor
# ---------------------------------------------------------------------------

class ASTVisitor:
    """Visits a single translation unit and builds BlueprintEntry objects."""

    def __init__(self, source_file: str, project_root: str):
        self.source_file = os.path.abspath(source_file)
        self.project_root = os.path.abspath(project_root)
        self.entries: dict[str, BlueprintEntry] = {}  # className → entry
        self._current_class_stack: list[str] = []
        # P8-02: typedef/using alias map built at TU parse time
        self._type_aliases: dict[str, dict] = {}
        # P8-05/06: synthetic entries for free functions, keyed by group key
        self._free_fn_entries: dict[str, BlueprintEntry] = {}

    def _rel_path(self, abs_path: str) -> str:
        try:
            return os.path.relpath(abs_path, self.project_root)
        except ValueError:
            return abs_path

    def _class_key(self, cursor: Any) -> str:
        """Unique key for a class cursor (qualified name)."""
        parts = []
        c = cursor
        while c and c.kind not in (CursorKind.TRANSLATION_UNIT,):
            if c.spelling:
                parts.append(c.spelling)
            c = c.semantic_parent
        parts.reverse()
        return "::".join(parts) if parts else cursor.spelling

    def visit(self, cursor: Any, depth: int = 0) -> None:
        """Recursively visit AST nodes."""
        # P8-02: collect typedef/using aliases once for the whole TU
        if depth == 0:
            self._type_aliases = collect_type_aliases(cursor)

        # Index class/struct defs only when the definition sits under
        # project_root (_visit_class). The TU still includes system headers so
        # member types and bases on project classes resolve.
        if cursor.kind in (
            CursorKind.CLASS_DECL,
            CursorKind.STRUCT_DECL,
            CursorKind.CLASS_TEMPLATE,
            CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        ):
            self._visit_class(cursor)
            return  # _visit_class recurses into children itself

        # P8-05: index free (non-member) functions defined in the project
        if cursor.kind == CursorKind.FUNCTION_DECL:
            self._visit_free_function(cursor)
            return

        for child in cursor.get_children():
            self.visit(child, depth + 1)

        # P8-06: after the full TU walk, promote free-function entries
        if depth == 0:
            self.entries.update(self._free_fn_entries)

    def _visit_class(self, cursor: Any) -> None:
        """Process a class/struct cursor."""
        # Skip forward declarations (no definition body)
        if not cursor.is_definition():
            # Still recurse in case of nested types inside headers we own
            for child in cursor.get_children():
                if child.kind in (
                    CursorKind.CLASS_DECL,
                    CursorKind.STRUCT_DECL,
                    CursorKind.CLASS_TEMPLATE,
                ):
                    self._visit_class(child)
            return

        loc = cursor.location
        if not loc.file:
            return

        # Only index classes defined in the scanned project tree (not STL/SDK).
        file_abs = os.path.abspath(loc.file.name)
        if not _is_definition_in_project(file_abs, self.project_root):
            return

        raw_name = cursor.spelling
        if not raw_name:
            # Anonymous struct/union — give it a synthetic name
            raw_name = f"__anonymous_{loc.line}"

        class_key = self._class_key(cursor)
        namespace = _get_namespace(cursor)
        template_params: list[str] = []
        base_classes: list[str] = []
        attributes: list[str] = []
        interfaces: list[str] = []
        interface_meta: list[dict] = []
        private_methods: list[dict] = []     # P10-01: protected/private methods
        dependencies: list[Dependency] = []
        seen_deps: set[tuple[str, str]] = set()
        type_aliases_used: list[dict] = []   # P8-04: aliases referenced by this class

        def _add_dep(target: str, dep_type: str) -> None:
            if not target or _is_trivial_type(target):
                return
            key = (target, dep_type)
            if key not in seen_deps:
                seen_deps.add(key)
                # Don't add self-reference
                if target != raw_name and target != class_key:
                    dependencies.append(Dependency(target=target, type=dep_type))

        # --- Template parameters ---
        for child in cursor.get_children():
            if child.kind in (
                CursorKind.TEMPLATE_TYPE_PARAMETER,
                CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
                CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
            ):
                template_params.append(child.spelling)

        # --- Base classes → inheritance dependencies ---
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_BASE_SPECIFIER:
                base_name = child.type.spelling
                base_name = re.sub(r"\bclass\b|\bstruct\b", "", base_name).strip()
                base_classes.append(base_name)
                _add_dep(base_name, "inheritance")

        # --- Member fields → attributes + composition / aggregation dependencies ---
        for child in cursor.get_children():
            if child.kind == CursorKind.FIELD_DECL:
                fname = child.spelling
                if fname:
                    ftype = re.sub(r"\s+", " ", (child.type.spelling or "")).strip()
                    attributes.append(f"{_field_access_symbol(child)}{ftype} {fname}")

                spelling = child.type.spelling  # e.g. "std::unique_ptr<NVMeDriver>"
                # Smart pointer → extract inner type, classify by ownership semantics
                unique_m = re.search(r"unique_ptr\s*<\s*([^,>\s]+)", spelling)
                shared_m = re.search(r"(?:shared_ptr|weak_ptr)\s*<\s*([^,>\s]+)", spelling)
                vector_m = re.search(r"(?:vector|list|deque|set|unordered_set)\s*<\s*([^,>\s]+)", spelling)
                map_m    = re.search(r"(?:map|unordered_map|multimap)\s*<\s*[^,>]+,\s*([^,>\s]+)", spelling)
                if unique_m:
                    inner = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", unique_m.group(1)).strip()
                    if inner and not _is_trivial_type(inner):
                        _add_dep(inner, "composition")
                elif shared_m:
                    inner = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", shared_m.group(1)).strip()
                    if inner and not _is_trivial_type(inner):
                        _add_dep(inner, "aggregation")
                elif vector_m or map_m:
                    inner_raw = (vector_m or map_m).group(1)
                    inner = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", inner_raw).strip()
                    if inner and not _is_trivial_type(inner):
                        dep = Dependency(target=inner, type="aggregation", cardinality="1..*")
                        key = (inner, "aggregation")
                        if key not in seen_deps and inner not in (raw_name, class_key):
                            seen_deps.add(key)
                            dependencies.append(dep)
                else:
                    # P8-03: check if the field type is a known typedef/using alias
                    # e.g. md_dg_t → shared_ptr<MDDriveGroup> → aggregation to MDDriveGroup
                    bare_field_type = re.sub(
                        r"\bconst\b|\bvolatile\b|\*|&|\s", "",
                        (child.type.spelling or "").split("<")[0]
                    ).lstrip(":")
                    alias_info = self._type_aliases.get(bare_field_type)
                    if alias_info and alias_info.get("innerType"):
                        inner = alias_info["innerType"]
                        dep_type = alias_info["depType"]
                        if inner and not _is_trivial_type(inner):
                            _add_dep(inner, dep_type)
                            # Record this alias for the P8-04 typeAliases field
                            alias_entry = {
                                "alias": bare_field_type,
                                "canonical": alias_info["canonical"],
                            }
                            if alias_entry not in type_aliases_used:
                                type_aliases_used.append(alias_entry)
                    else:
                        type_name = _canonical_type_name(child)
                        if type_name and not _is_trivial_type(type_name):
                            raw_type = child.type
                            if raw_type.kind in (
                                cindex.TypeKind.POINTER,
                                cindex.TypeKind.LVALUEREFERENCE,
                                cindex.TypeKind.RVALUEREFERENCE,
                            ):
                                # Raw pointer/ref → aggregation (borrowing, no ownership)
                                _add_dep(type_name, "aggregation")
                            else:
                                # Value member → composition (owns by value)
                                _add_dep(type_name, "composition")

        # --- Public methods → interfaces ---
        for child in cursor.get_children():
            if child.kind in (
                CursorKind.CXX_METHOD,
                CursorKind.CONSTRUCTOR,
                CursorKind.DESTRUCTOR,
                CursorKind.FUNCTION_TEMPLATE,
            ):
                # Helper: collect used types from a method cursor
                def _collect_used_types(mc: Any) -> list[str]:
                    ut: list[str] = []
                    for p in mc.get_arguments():
                        t = _canonical_type_name(p)
                        if t and not _is_trivial_type(t) and t not in ut:
                            ut.append(t)
                    if mc.result_type and mc.result_type.spelling:
                        r = mc.result_type.spelling
                        r = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", r).strip().lstrip(":")
                        if r and not _is_trivial_type(r) and r not in ut:
                            ut.append(r)
                    return ut

                if child.access_specifier == cindex.AccessSpecifier.PUBLIC:
                    sig = _method_signature(child)
                    interfaces.append(sig)
                    used_types = _collect_used_types(child)
                    # P9-02: ordered call/field-access sequence from method body
                    call_seq = self._scan_method_accesses(child, raw_name)
                    interface_meta.append({
                        "signature": sig,
                        "lineNumber": child.location.line,
                        "usedTypes": used_types,
                        "callSequence": call_seq,
                    })
                elif child.access_specifier in (
                    cindex.AccessSpecifier.PROTECTED,
                    cindex.AccessSpecifier.PRIVATE,
                ):
                    # P10-01: capture protected/private methods
                    sig = _method_signature(child)
                    acc = (
                        "protected"
                        if child.access_specifier == cindex.AccessSpecifier.PROTECTED
                        else "private"
                    )
                    used_types = _collect_used_types(child)
                    call_seq = self._scan_method_accesses(child, raw_name)
                    private_methods.append({
                        "signature":    sig,
                        "lineNumber":   child.location.line,
                        "access":       acc,
                        "usedTypes":    used_types,
                        "callSequence": call_seq,
                    })

                # Inspect method parameters for association dependencies
                for param in child.get_arguments():
                    type_name = _canonical_type_name(param)
                    if type_name and not _is_trivial_type(type_name):
                        _add_dep(type_name, "association")

                # Inspect return type for association
                if child.result_type and child.result_type.spelling:
                    ret_name = child.result_type.spelling
                    ret_name = re.sub(r"\bconst\b|\bvolatile\b|\*|&", "", ret_name).strip()
                    if ret_name and not _is_trivial_type(ret_name):
                        _add_dep(ret_name, "association")

            # Nested class declarations
            elif child.kind in (
                CursorKind.CLASS_DECL,
                CursorKind.STRUCT_DECL,
                CursorKind.CLASS_TEMPLATE,
            ):
                self._visit_class(child)

        # --- Local variable types in method bodies → dependency ---
        for child in cursor.get_children():
            if child.kind in (CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR):
                self._scan_body_for_deps(child, seen_deps, dependencies, raw_name, class_key)

        # Build responsibility from doxygen/comment if present, else synthesize
        responsibility = self._extract_responsibility(cursor, raw_name, interfaces)

        rel_file = self._rel_path(file_abs)
        entry = BlueprintEntry(
            className=raw_name,
            responsibility=responsibility,
            dependencies=dependencies,
            interfaces=interfaces,
            interfaceMeta=interface_meta,
            typeAliases=type_aliases_used,
            privateMethods=private_methods,
            fileLocation=rel_file,
            lineNumber=loc.line,
            namespace=namespace,
            baseClasses=base_classes,
            templateParams=template_params,
            attributes=attributes,
        )
        # Use qualified name as key to avoid collisions
        self.entries[class_key] = entry

    def _scan_body_for_deps(
        self,
        method_cursor: Any,
        seen_deps: set[tuple[str, str]],
        dependencies: list[Dependency],
        raw_name: str,
        class_key: str,
    ) -> None:
        """Scan method body for local variable declarations that introduce dependencies."""
        for child in method_cursor.get_children():
            if child.kind == CursorKind.VAR_DECL:
                type_name = _canonical_type_name(child)
                if type_name and not _is_trivial_type(type_name):
                    key = (type_name, "dependency")
                    if key not in seen_deps and type_name not in (raw_name, class_key):
                        seen_deps.add(key)
                        dependencies.append(Dependency(target=type_name, type="dependency"))
            # Recurse into compound statements
            self._scan_body_for_deps(child, seen_deps, dependencies, raw_name, class_key)

    # P9-02: ordered call/field-access sequence from method body
    def _scan_method_accesses(
        self,
        method_cursor: Any,
        self_class_name: str,
    ) -> list[dict]:
        """
        Walk a method body for MEMBER_REF_EXPR / CALL_EXPR to build an ordered
        sequence of accesses to members of OTHER classes.

        Returns list of {order, targetClass, member, kind} dicts, deduplicated
        by (targetClass, member) keeping the first occurrence.
        """
        seen: list[tuple[str, str]] = []
        result: list[dict] = []

        # P11-01: cursor kinds that indicate the MEMBER_REF_EXPR is being written to
        _WRITE_PARENT_KINDS = frozenset({
            CursorKind.BINARY_OPERATOR,
            CursorKind.COMPOUND_ASSIGNMENT_OPERATOR,
        })
        _UNARY_WRITE_OPS = frozenset({
            CursorKind.UNARY_OPERATOR,  # ++/-- on the member
        })

        def _is_write(c: Any, parent: Any) -> bool:
            """Heuristic: is this MEMBER_REF_EXPR the target of a write?"""
            if parent is None:
                return False
            if parent.kind in _UNARY_WRITE_OPS:
                return True
            if parent.kind in _WRITE_PARENT_KINDS:
                # Write only if this node is the FIRST child (LHS)
                try:
                    children = list(parent.get_children())
                    if children and children[0].location == c.location:
                        return True
                except Exception:
                    pass
            return False

        def _walk(c: Any, parent: Any = None) -> None:
            if c.kind == CursorKind.MEMBER_REF_EXPR:
                try:
                    ref = c.referenced
                    if not ref:
                        pass
                    else:
                        parent_cls = ref.semantic_parent
                        cls_name = parent_cls.spelling if parent_cls else ""
                        if cls_name and cls_name != self_class_name and not _is_trivial_type(cls_name):
                            # Restrict to project-owned classes
                            ok = True
                            if parent_cls and parent_cls.location.file:
                                ok = _is_definition_in_project(
                                    os.path.abspath(parent_cls.location.file.name),
                                    self.project_root,
                                )
                            if ok:
                                member = ref.spelling or ""
                                key = (cls_name, member)
                                if key not in seen:
                                    seen.append(key)
                                    is_field = ref.kind == CursorKind.FIELD_DECL
                                    kind = "field" if is_field else "call"
                                    # P11-01: detect write access
                                    is_write = is_field and _is_write(c, parent)
                                    result.append({
                                        "order":       len(result) + 1,
                                        "targetClass": cls_name,
                                        "member":      member,
                                        "kind":        kind,
                                        "isWrite":     is_write,
                                    })
                except Exception:
                    pass
            for child in c.get_children():
                _walk(child, c)

        _walk(method_cursor)
        return result

    # P8-05/06/07: index free (non-member) functions
    def _visit_free_function(self, cursor: Any) -> None:
        """
        Process a top-level FUNCTION_DECL and accumulate it into a synthetic
        BlueprintEntry keyed by namespace (or bare filename when no namespace).
        """
        if not cursor.is_definition():
            return

        loc = cursor.location
        if not loc.file:
            return
        file_abs = os.path.abspath(loc.file.name)
        if not _is_definition_in_project(file_abs, self.project_root):
            return

        ns = _get_namespace(cursor)
        if ns:
            group_key = ns
            display_name = ns
        else:
            basename = os.path.splitext(os.path.basename(file_abs))[0]
            display_name = basename
            group_key = f"__file__{file_abs}"

        sig = _method_signature(cursor)

        # Collect non-trivial parameter types as P8-07 dependencies
        param_types: list[str] = []
        for arg in cursor.get_arguments():
            t = _canonical_type_name(arg)
            if t and not _is_trivial_type(t) and t not in param_types:
                param_types.append(t)

        if group_key not in self._free_fn_entries:
            rel_file = self._rel_path(file_abs)
            self._free_fn_entries[group_key] = BlueprintEntry(
                className=display_name,
                responsibility="Free Functions",
                dependencies=[],
                interfaces=[],
                interfaceMeta=[],
                fileLocation=rel_file,
                lineNumber=loc.line,
                namespace=ns,
                baseClasses=[],
                templateParams=[],
            )

        entry = self._free_fn_entries[group_key]
        if sig not in entry.interfaces:
            entry.interfaces.append(sig)
            entry.interfaceMeta.append({
                "signature": sig,
                "lineNumber": loc.line,
                "usedTypes": param_types,
            })

        # Add association dependencies for param types
        seen = {(d.target, d.type) for d in entry.dependencies}
        for t in param_types:
            k = (t, "association")
            if k not in seen:
                seen.add(k)
                entry.dependencies.append(Dependency(target=t, type="association"))

    # Naming-convention → responsibility label (T-12)
    _RESPONSIBILITY_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"Manager$"),    "Resource Lifecycle"),
        (re.compile(r"Handler$"),    "Event Processing"),
        (re.compile(r"Provider$"),   "Data Supply"),
        (re.compile(r"Factory$"),    "Object Creation"),
        (re.compile(r"Driver$"),     "Hardware Abstraction"),
        (re.compile(r"Scheduler$"),  "Task Ordering"),
        (re.compile(r"Controller$"), "Orchestration"),
        (re.compile(r"Dispatcher$"), "Event Routing"),
        (re.compile(r"Observer$"),   "Event Observation"),
        (re.compile(r"Builder$"),    "Object Construction"),
        (re.compile(r"Parser$"),     "Data Parsing"),
        (re.compile(r"Serializer$"), "Data Serialization"),
        (re.compile(r"Validator$"),  "Data Validation"),
        (re.compile(r"Pool$"),       "Resource Pooling"),
        (re.compile(r"Cache$|Cach"), "Data Caching"),
        (re.compile(r"Queue$"),      "Work Queuing"),
        (re.compile(r"Listener$"),   "Event Listening"),
        (re.compile(r"Engine$"),     "Core Processing"),
        (re.compile(r"Service$"),    "Service Provision"),
        (re.compile(r"Repository$"), "Data Storage"),
        (re.compile(r"Adapter$"),    "Interface Adaptation"),
        (re.compile(r"Proxy$"),      "Access Proxying"),
    ]

    def _extract_responsibility(
        self, cursor: Any, class_name: str, interfaces: list[str]
    ) -> str:
        """Attempt to extract a responsibility description from the raw comment."""
        raw_comment = cursor.raw_comment
        if raw_comment:
            # Strip comment markers
            cleaned = re.sub(r"/\*+|/\*|\*/|//+", "", raw_comment)
            cleaned = re.sub(r"\s*\*\s*", " ", cleaned)
            cleaned = re.sub(r"@\w+[^\n]*", "", cleaned)
            cleaned = " ".join(cleaned.split())
            if len(cleaned) > 10:
                return cleaned[:200]

        # Naming-convention regex mapping (T-12)
        for pattern, label in self._RESPONSIBILITY_PATTERNS:
            if pattern.search(class_name):
                return label

        # Synthesize from class name and public interface
        iface_names = [sig.split("(")[0].split()[-1] for sig in interfaces[:3]]
        if iface_names:
            return f"Provides {', '.join(iface_names)} functionality"
        return f"Manages {class_name} operations"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_compile_commands(compile_commands_path: str) -> dict[str, list[str]]:
    """
    Parse compile_commands.json and return a mapping of
    {absolute_file_path: [compiler_args]}.
    """
    path = Path(compile_commands_path)
    if not path.exists():
        return {}
    with open(path) as f:
        entries = json.load(f)

    result: dict[str, list[str]] = {}
    for entry in entries:
        file_path = entry.get("file", "")
        directory = entry.get("directory", "")
        command = entry.get("command", "")
        arguments = entry.get("arguments", [])

        if not file_path:
            continue
        if not os.path.isabs(file_path):
            file_path = os.path.join(directory, file_path)
        file_path = os.path.abspath(file_path)

        if arguments:
            # arguments list — skip the compiler executable itself
            args = arguments[1:] if arguments else []
        elif command:
            import shlex
            args = shlex.split(command)[1:]
        else:
            args = []

        # Filter out source file and output flags that confuse libclang
        filtered: list[str] = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg in ("-o", "-MF", "-MT", "-MQ"):
                skip_next = True
                continue
            if arg == file_path or arg.endswith(".o"):
                continue
            filtered.append(arg)

        result[file_path] = filtered

    return result


def _darwin_libclang_sysroot_args() -> list[str]:
    """
    On macOS, libclang needs the same SDK + Clang resource directory as the
    Xcode/CLT driver.  Only -isysroot is not enough: SDK headers pull in
    <stdarg.h>, which lives under the compiler's -resource-dir, not in the SDK.
    """
    args: list[str] = []
    try:
        sdk = subprocess.run(
            ["xcrun", "--sdk", "macosx", "--show-sdk-path"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if sdk.returncode == 0:
            p = sdk.stdout.strip()
            if p:
                args.extend(["-isysroot", p])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        rd = subprocess.run(
            ["xcrun", "--sdk", "macosx", "--run", "clang", "-print-resource-dir"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if rd.returncode == 0:
            r = rd.stdout.strip()
            if r:
                args.extend(["-resource-dir", r])
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # libc++ is the default for Apple clang; makes <string> resolve consistently.
    if args:
        args.append("-stdlib=libc++")

    return args


# Flags that GCC accepts but clang/libclang does not — strip them from
# compile_commands.json args before handing to libclang.
_GCC_ONLY_FLAG_RE = re.compile(
    r"^-(?:"
    r"Werror=stringop-overflow|"
    r"Werror=stringop-truncation|"
    r"Werror=implicit-fallthrough=\d*|"
    r"fstack-protector-strong|"
    r"fstack-clash-protection|"
    r"fcf-protection(?:=\w+)?|"
    r"fno-semantic-interposition|"
    r"mno-omit-leaf-frame-pointer|"
    r"Wno-error=deprecated-declarations|"
    r"fvar-tracking-assignments"
    r")$"
)


def _filter_gcc_flags(args: list[str]) -> list[str]:
    """Remove GCC-specific flags that libclang (clang) does not recognise."""
    return [a for a in args if not _GCC_ONLY_FLAG_RE.match(a)]


def _linux_clang_resource_dir_args() -> list[str]:
    """
    On Linux, libclang needs -resource-dir to find built-in headers like
    stddef.h, stdarg.h, etc.

    Strategy (in order):
    1. Ask a clang binary via -print-resource-dir
    2. Ask llvm-config for the prefix and derive the path
    3. Glob common well-known paths under /usr/lib/clang/ and /usr/lib/llvm-*
    4. Derive from the pip-installed libclang package location
    """
    # 1. Try clang binary
    for binary in ("clang", "clang-18", "clang-17", "clang-16", "clang-15", "clang-14"):
        try:
            result = subprocess.run(
                [binary, "-print-resource-dir"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                r = result.stdout.strip()
                if r and os.path.isdir(r):
                    return ["-resource-dir", r]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue

    # 2. Try llvm-config
    for binary in ("llvm-config", "llvm-config-18", "llvm-config-17", "llvm-config-16",
                   "llvm-config-15", "llvm-config-14"):
        try:
            result = subprocess.run(
                [binary, "--prefix"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                prefix = result.stdout.strip()
                # Resource dir is typically <prefix>/lib/clang/<version>
                clang_lib = os.path.join(prefix, "lib", "clang")
                if os.path.isdir(clang_lib):
                    versions = sorted(os.listdir(clang_lib), reverse=True)
                    for v in versions:
                        rd = os.path.join(clang_lib, v)
                        if os.path.isdir(rd):
                            return ["-resource-dir", rd]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue

    # 3. Glob common system paths
    import glob as _glob
    for pattern in (
        "/usr/lib/clang/*/",
        "/usr/lib/llvm-*/lib/clang/*/",
    ):
        matches = sorted(_glob.glob(pattern), reverse=True)
        for m in matches:
            m = m.rstrip("/")
            if os.path.isdir(m):
                return ["-resource-dir", m]

    # 4. Derive from pip-installed libclang package (cindex.py location)
    try:
        import clang as _clang_pkg
        pkg_dir = os.path.dirname(_clang_pkg.__file__)
        for rel in ("lib/clang", "clang"):
            candidate = os.path.join(pkg_dir, rel)
            if os.path.isdir(candidate):
                versions = sorted(os.listdir(candidate), reverse=True)
                for v in versions:
                    rd = os.path.join(candidate, v)
                    if os.path.isdir(rd):
                        return ["-resource-dir", rd]
    except Exception:
        pass

    return []


def _linux_gcc_builtin_include_args() -> list[str]:
    """
    When no clang resource-dir is available, fall back to GCC's built-in
    include directory (contains stddef.h, stdarg.h, stdbool.h, etc.).
    Used on systems that build with GCC but have no clang binary installed.
    """
    for gcc in ("gcc", "gcc-13", "gcc-12", "gcc-11", "gcc-10"):
        try:
            result = subprocess.run(
                [gcc, "-print-file-name=include"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                p = result.stdout.strip()
                # Sanity check: must be an actual directory under a gcc path
                if p and os.path.isdir(p) and "gcc" in p:
                    return ["-I", p]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return []


def _default_clang_args(extra_args: Optional[list[str]]) -> list[str]:
    """Compile flags for TUs that are not listed in compile_commands.json."""
    if extra_args:
        core = list(extra_args)
    else:
        core = ["-std=c++17", "-x", "c++"]
    if sys.platform == "darwin":
        return _darwin_libclang_sysroot_args() + core
    # Linux: inject resource-dir (clang) or GCC built-in include as fallback
    res = _linux_clang_resource_dir_args()
    if not res:
        res = _linux_gcc_builtin_include_args()
    return res + core + ["-Wno-error", "-Wno-unknown-warning-option", "-ferror-limit=0"]


def parse_files(
    source_files: list[str],
    project_root: str,
    compile_commands_path: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    Parse a list of C/C++ source files with libclang and return a list of
    blueprint_index schema dictionaries.

    Args:
        source_files: Absolute or relative paths to .cpp/.h/.hpp/.c files.
        project_root: Root directory of the project (for relative fileLocation).
        compile_commands_path: Path to compile_commands.json (optional).
        extra_args: Additional compiler arguments to pass to libclang.

    Returns:
        List of dicts matching the blueprint_index entry schema.
    """
    _exclude_patterns: list[str] = list(exclude_patterns) if exclude_patterns else []

    index = cindex.Index.create()
    compile_db: dict[str, list[str]] = {}
    if compile_commands_path:
        compile_db = load_compile_commands(compile_commands_path)

    default_args = _default_clang_args(extra_args)

    # Precompute Linux resource-dir (or GCC include) args for compile_commands entries
    if sys.platform != "darwin":
        _linux_res = _linux_clang_resource_dir_args() or _linux_gcc_builtin_include_args()
    else:
        _linux_res = []

    # These flags must come AFTER compile_commands args so they override -Werror:
    # -Wno-error                  : neutralise any -Werror from compile_commands
    # -Wno-unknown-warning-option : silence "unknown warning option" for GCC flags
    # -ferror-limit=0             : never stop mid-file due to error count
    _tail_flags = ["-Wno-error", "-Wno-unknown-warning-option", "-ferror-limit=0"]

    all_entries: dict[str, BlueprintEntry] = {}

    for src in source_files:
        src_abs = os.path.abspath(src)
        raw_args = compile_db.get(src_abs, default_args)
        # Filter GCC-only flags; append analysis flags AFTER so they win
        if raw_args is not default_args:
            args = _linux_res + _filter_gcc_flags(raw_args) + _tail_flags
        else:
            args = raw_args

        try:
            tu = index.parse(
                src_abs,
                args=args,
                options=(
                    cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
                    | cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
                    # Don't skip function bodies for dependency detection
                ),
            )
        except TranslationUnitLoadError as e:
            print(f"[ast_parser] WARNING: Failed to parse {src}: {e}", file=sys.stderr)
            continue

        # Report diagnostics at warning level — only for files inside project_root
        # and not matching exclude patterns. Third-party headers pulled in via
        # #include will still be processed by libclang but their warnings are
        # suppressed here to avoid noise from vendored code.
        _sev_names = {
            cindex.Diagnostic.Warning: "WARNING",
            cindex.Diagnostic.Error: "ERROR",
            cindex.Diagnostic.Fatal: "FATAL",
        }
        for diag in tu.diagnostics:
            if diag.severity >= cindex.Diagnostic.Warning:
                diag_file = str(diag.location.file) if diag.location.file else ""
                # Skip diagnostics from outside the project (transitive headers)
                if diag_file and not _is_definition_in_project(diag_file, project_root):
                    continue
                # Skip diagnostics from excluded paths
                if diag_file and _is_excluded(diag_file, project_root, _exclude_patterns):
                    continue
                sev = _sev_names.get(diag.severity, "NOTE")
                print(
                    f"[ast_parser] {sev}: {diag.spelling} "
                    f"({diag.location.file}:{diag.location.line})",
                    file=sys.stderr,
                )

        visitor = ASTVisitor(src_abs, project_root)
        visitor.visit(tu.cursor)
        all_entries.update(visitor.entries)

    return [entry.to_dict() for entry in all_entries.values()]


# ---------------------------------------------------------------------------
# P6-02/04: Exclude-path helpers
# ---------------------------------------------------------------------------

def load_blueprintignore(project_root: str) -> list[str]:
    """
    P6-04: Read .blueprintignore from project_root.
    Format: one glob pattern per line; '#' comments and blank lines are ignored.
    Returns a list of patterns (may be empty if file doesn't exist).
    """
    ignore_path = Path(project_root) / ".blueprintignore"
    if not ignore_path.is_file():
        return []
    patterns: list[str] = []
    with open(ignore_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    return patterns


def _is_excluded(file_path: str, project_root: str, patterns: list[str]) -> bool:
    """
    Return True if `file_path` matches any exclude pattern.

    Patterns are matched against:
    1. The relative path from project_root (e.g. "third_party/foo/bar.cpp")
    2. Each individual directory component (for simple name patterns like "build")

    Supports standard glob wildcards: *, **, ?, [seq].
    """
    if not patterns:
        return False
    root = Path(project_root).resolve()
    try:
        rel = str(Path(file_path).resolve().relative_to(root))
    except ValueError:
        rel = file_path
    # Normalise separators
    rel = rel.replace("\\", "/")

    for pat in patterns:
        pat_norm = pat.replace("\\", "/")
        # 1. Match against full relative path (supports "third_party/**", "src/gen/*.cpp")
        if fnmatch.fnmatch(rel, pat_norm):
            return True
        # 2. Also try matching with "**/" prefix so bare name "build" matches "build/…"
        if fnmatch.fnmatch(rel, f"**/{pat_norm}") or fnmatch.fnmatch(rel, f"{pat_norm}/**"):
            return True
        # 3. Match each path component for simple directory names (e.g. "vendor")
        parts = rel.split("/")
        if any(fnmatch.fnmatch(part, pat_norm) for part in parts):
            return True
    return False


def scan_directory(
    project_root: str,
    compile_commands_path: Optional[str] = None,
    extensions: tuple[str, ...] = (".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx"),
    exclude_patterns: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """
    Recursively scan an entire project directory for C/C++ source files
    and parse them all.

    Args:
        project_root: Root directory to scan.
        compile_commands_path: Optional path to compile_commands.json.
        extensions: File extensions to include.
        exclude_patterns: Glob patterns for paths to exclude. If None, reads
            .blueprintignore and applies built-in defaults
            (third_party, vendor, extern, build, .git).

    Returns:
        List of blueprint_index entry dicts.
    """
    _DEFAULT_EXCLUDES = ["third_party", "vendor", "extern", "build", ".git"]

    if exclude_patterns is None:
        patterns = _DEFAULT_EXCLUDES + load_blueprintignore(project_root)
    else:
        patterns = list(exclude_patterns) + load_blueprintignore(project_root)

    root = Path(project_root)
    source_files: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if _is_excluded(str(path), project_root, patterns):
            continue
        source_files.append(str(path))

    print(
        f"[ast_parser] Found {len(source_files)} source files under {project_root}",
        file=sys.stderr,
    )

    return parse_files(
        source_files,
        project_root=project_root,
        compile_commands_path=compile_commands_path,
        exclude_patterns=patterns,
    )
