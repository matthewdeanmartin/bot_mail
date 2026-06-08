# Project Instructions

## Naming Conventions
- **No Private Underscores:** Do not use leading underscores (`_`) to denote "private" or "internal" visibility for classes, methods, functions, or attributes.
- **Underscore for Unused:** A leading underscore (e.g., `_` or `_unused_var`) MUST ONLY be used to indicate that a variable is intentionally unused (e.g., in a loop or function signature).
- **Public by Default:** All members are public by default. Use explicit `__all__` in modules to define the public API if necessary.
- **Special Methods:** Use `__dunder__` for standard Python special methods.

## Refactoring Guidelines
- When refactoring existing code, rename all `_foo` (private) to `foo` (public).
- Ensure all call sites are updated.
- Update tests to reflect the new naming.
