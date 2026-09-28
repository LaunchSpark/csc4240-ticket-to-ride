"""Fail when a pull request changes files its author does not own and no
other collaborator has approved it.

Usage: check_ownership.py AUTHOR OWNERS_PATH APPROVALS < changed_paths

Supports the CODEOWNERS subset this repository uses: `*` within a path
segment, `**` across segments, a leading `/` to anchor at the root, and a
trailing `/` for directories. The last matching rule wins.
"""

import re
import sys


def pattern_to_regex(pattern: str) -> re.Pattern:
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    parts = []
    i = 0
    while i < len(body):
        if body.startswith("**", i):
            parts.append(".*")
            i += 2
        elif body[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif body[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(body[i]))
            i += 1
    prefix = "^" if anchored else "^(?:.*/)?"
    # A match may also be a directory containing the path.
    return re.compile(prefix + "".join(parts) + "(?:/.*)?$")


def load_rules(path: str) -> list[tuple[re.Pattern, set[str]]]:
    rules = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            pattern, *owners = line.split()
            logins = {owner.lstrip("@").casefold() for owner in owners}
            rules.append((pattern_to_regex(pattern), logins))
    return rules


def owners_of(path: str, rules) -> set[str]:
    owners: set[str] = set()
    for regex, logins in rules:
        if regex.match(path):
            owners = logins
    return owners


def main() -> int:
    author, owners_file, approvals = sys.argv[1].casefold(), sys.argv[2], int(sys.argv[3])
    rules = load_rules(owners_file)
    paths = sorted({line.strip() for line in sys.stdin if line.strip()})
    violations = [(p, owners_of(p, rules)) for p in paths if author not in owners_of(p, rules)]

    if not violations:
        print(f"OK: @{author} owns all {len(paths)} changed file(s).")
        return 0

    print(f"@{author} changed {len(violations)} file(s) outside their own bots:")
    for path, owners in violations:
        listed = ", ".join(f"@{o}" for o in sorted(owners)) or "shared"
        print(f"  {path}  ({listed})")
    if approvals:
        print(f"\nOK: approved by {approvals} other collaborator(s) at the latest commit.")
        return 0
    print("\nNeeds an approving review from one other collaborator at the latest commit.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
