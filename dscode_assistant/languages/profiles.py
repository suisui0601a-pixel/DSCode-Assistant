"""Built-in language profiles for the first Language Support release."""

from __future__ import annotations

from typing import Final

from .models import CommentSyntax, LanguageId, LanguageProfile


HASH_COMMENTS: Final = CommentSyntax(line_prefixes=("#",))
C_STYLE_COMMENTS: Final = CommentSyntax(
    line_prefixes=("//",),
    block_pairs=(("/*", "*/"),),
)


DEFAULT_LANGUAGE_PROFILES: Final[tuple[LanguageProfile, ...]] = (
    LanguageProfile(
        language_id=LanguageId.PYTHON,
        display_name="Python",
        file_extensions=(".py", ".pyi"),
        fence_aliases=("python", "py"),
        explicit_aliases=("python", "py"),
        comments=HASH_COMMENTS,
        error_keywords=("Traceback", "SyntaxError", "IndentationError", "ModuleNotFoundError"),
    ),
    LanguageProfile(
        language_id=LanguageId.C,
        display_name="C",
        file_extensions=(".c", ".h"),
        fence_aliases=("c",),
        explicit_aliases=("c", "c language"),
        comments=C_STYLE_COMMENTS,
        error_keywords=("segmentation fault", "undefined reference", "compilation failed"),
    ),
    LanguageProfile(
        language_id=LanguageId.CPP,
        display_name="C++",
        file_extensions=(".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h"),
        fence_aliases=("cpp", "c++", "cxx"),
        explicit_aliases=("c++", "cpp", "cxx"),
        comments=C_STYLE_COMMENTS,
        error_keywords=("undefined reference", "linker error", "template instantiation"),
    ),
    LanguageProfile(
        language_id=LanguageId.JAVA,
        display_name="Java",
        file_extensions=(".java",),
        fence_aliases=("java",),
        explicit_aliases=("java",),
        comments=C_STYLE_COMMENTS,
        error_keywords=("Exception in thread", "cannot find symbol", "javac"),
    ),
    LanguageProfile(
        language_id=LanguageId.JAVASCRIPT,
        display_name="JavaScript",
        file_extensions=(".js", ".jsx", ".mjs", ".cjs"),
        fence_aliases=("javascript", "js", "jsx", "node"),
        explicit_aliases=("javascript", "js", "node.js", "nodejs"),
        comments=C_STYLE_COMMENTS,
        error_keywords=("ReferenceError", "TypeError", "UnhandledPromiseRejection"),
    ),
    LanguageProfile(
        language_id=LanguageId.TYPESCRIPT,
        display_name="TypeScript",
        file_extensions=(".ts", ".tsx", ".mts", ".cts"),
        fence_aliases=("typescript", "ts", "tsx"),
        explicit_aliases=("typescript", "ts"),
        comments=C_STYLE_COMMENTS,
        error_keywords=("TypeScript error", "Cannot find name", "is not assignable to type"),
    ),
)
