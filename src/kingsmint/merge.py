"""Keep the user's edits to generated transactions across `kingsmint reimport`.

Each generated transaction has `id` metadata; .kingsmint/base/ holds what kingsmint wrote last time, without edits.
Per id, a three-way merge of base (generated last time), mine (ledger/ now, maybe edited in Fava) and theirs
(generated now): a part the user did not change comes from theirs, a part kingsmint did not change comes from mine;
when both changed a part, mine wins and the conflict is reported. The parts: flag, payee, narration, tags and links,
the comment on the first line, each metadata key, and the postings after the first as a whole. The first posting is the
statement row (account and amount): it always comes from theirs, so a renamed account reaches edited transactions. Comments stay after the item they
followed. Parsed with tree-sitter, because Beancount's parser drops comments.
"""

import functools
import re
from pathlib import Path

BASE = Path(".kingsmint") / "base"
ORPHANS = Path(".kingsmint") / "orphans.beancount"
HEADER = ("flag", "payee", "narration", "tags_links", "comment")
BANK = "<bank>"  # the anchor of the first posting, whatever its account is called


@functools.cache
def parser():
    from tree_sitter import Parser
    from tree_sitter_language_pack import get_language
    return Parser(get_language("beancount"))  # the first call downloads the grammar to the user cache


def lines(text):
    return re.findall(r"[^\n]*\n|[^\n]+$", text)  # only \n: str.splitlines also splits on \x0b,  , ...


def end_row(n):
    return n.end_point[0] + (n.end_point[1] > 0)


def chunks(text, name="<text>"):
    """[(id or None, leading comments, entry text, first row, end row)]; ValueError when tree-sitter cannot parse."""
    tree = parser().parse(text.encode())
    if tree.root_node.has_error:
        n = tree.root_node
        while bad := [c for c in n.children if c.has_error or c.type == "ERROR" or c.is_missing]:
            n = bad[0]
        raise ValueError(f"{name}:{n.end_point[0] + 1}: cannot read this line; move a comment after metadata to its own line")
    ls, out, lead, first = lines(text), [], [], None
    for n in tree.root_node.named_children:
        if n.type == "comment":
            first = n.start_point[0] if first is None else first
            lead.append("".join(ls[n.start_point[0]:end_row(n)]))
            continue
        tid = next((v.text.decode().strip('"') for kv in n.named_children if kv.type == "key_value"
                    for k, v in [kv.named_children[:2]] if k.text == b"id"), None) if n.type == "transaction" else None
        start = n.start_point[0] if first is None else first
        out.append((tid, "".join(lead), "".join(ls[n.start_point[0]:end_row(n)]), start, end_row(n)))
        lead, first = [], None
    if lead:
        out.append((None, "".join(lead), "", first, len(ls)))
    return out


def parts(body):
    """Header fields, metadata {key: line}, postings (each with its own metadata lines), comments with their anchor.
    A comment at the end of a posting line is a comment, not a change of the posting: a rule may still change it."""
    n = parser().parse(body.encode()).root_node.named_children[0]
    ls = lines(body)
    head = {c.type if c.type != "txn" else "flag": c.text.decode() for c in n.named_children if c.start_point[0] == 0}
    meta, postings, comments, anchor = {}, [], [], ("header",)
    for c in n.named_children:
        if c.start_point[0] == 0:
            continue
        text = "".join(ls[c.start_point[0]:end_row(c)])
        if c.type == "key_value" and postings:
            postings[-1] = (postings[-1][0], postings[-1][1] + text)  # a posting's own metadata
        elif c.type == "key_value":
            key = c.named_children[0].text.decode()
            meta[key], anchor = text, ("meta", key)
        elif c.type == "posting":
            account = next(x for x in c.named_children if x.type == "account").text.decode()
            if inline := next((x for x in c.named_children if x.type == "comment"), None):
                line = ls[c.start_point[0]].encode()  # tree-sitter columns are bytes
                before = line[:inline.start_point[1]].decode()
                text = before.rstrip() + "\n" + text[len(line.decode()):]
                comments.append((("inline", account if postings else BANK), before[len(before.rstrip()):] + inline.text.decode()))
            postings.append((account if postings else BANK, text))
            anchor = ("posting", postings[-1][0])
        elif c.type == "comment":
            comments.append((anchor, text))
    return head, meta, tuple(postings), comments


def pick(base, mine, theirs, what, conflicts):
    if mine == base:
        return theirs
    if theirs not in (base, mine):
        conflicts.append(what)
    return mine


def merge_txn(base, mine, theirs):
    """(text, conflicts) for one transaction: entry texts without leading comments."""
    if mine == base:
        return theirs, []
    if theirs == mine:
        return mine, []
    (bh, bm, bp, _), (mh, mm, mp, mc), (th, tm, tp, _) = parts(base), parts(mine), parts(theirs)
    if theirs == base and mp[:1] == tp[:1]:
        return mine, []
    conflicts = []
    head = {f: pick(bh.get(f), mh.get(f), th.get(f), f, conflicts) for f in HEADER}
    meta = [(key, pick(bm.get(key), mm.get(key), tm.get(key), key, conflicts)) for key in [*tm, *(k for k in mm if k not in tm)]]
    postings = tp[:1] + pick(bp[1:], mp[1:], tp[1:], "postings", conflicts)
    return assemble(mine, th["date"], head, meta, postings), conflicts


def reset(mine, base):
    """One transaction with the postings and flag of base, what the rules decide; the rest as the user wrote it."""
    (bh, _, bp, _), (mh, mm, _, _) = parts(base), parts(mine)
    return assemble(mine, mh["date"], dict(mh, flag=bh["flag"]), list(mm.items()), bp)


def assemble(mine, date, head, meta, postings):
    """The transaction text from merged parts, with mine's comments after the item they followed."""
    mh, _, _, mc = parts(mine)
    first = " ".join(x for x in [date, *(head.get(f) for f in HEADER[:-1])] if x)
    first += f"  {head['comment']}" if head.get("comment") else ""
    out = [lines(mine)[0] if all(head.get(f) == mh.get(f) for f in HEADER) else first + "\n"]  # unchanged: as written
    after = {}  # anchor -> comments
    for anchor, text in mc:
        after.setdefault(anchor, []).append(text)
    out += after.pop(("header",), [])
    for key, line in meta:
        if line:
            out += [line, *after.pop(("meta", key), [])]
    accounts = {a for a, _ in postings}
    for anchor in [a for a in after if a[0] not in ("posting", "inline") or a[1] not in accounts]:
        out += [c if anchor[0] != "inline" else f"  {c.lstrip()}\n" for c in after.pop(anchor)]  # their item is gone: before the postings
    for account, text in postings:
        first, rest = text.split("\n", 1)
        out += [first + "".join(after.pop(("inline", account), [])) + "\n" + rest,
                *after.pop(("posting", account), [])]
    return "".join(out)


def reset_id(root, tid):
    """`kingsmint reset ID`: the transaction in ledger/ takes kingsmint's postings and flag from .kingsmint/base/."""
    found = {}
    for folder in ("ledger", BASE):
        for f in (root / folder).rglob("*.beancount"):
            for t, _, body, *_ in chunks(f.read_text(encoding="utf-8"), f.relative_to(root).as_posix()):
                if t == tid:
                    found[folder] = (f, body)
    if set(found) != {"ledger", BASE}:
        return print(f"FAIL {tid}: no transaction with this id in ledger/ and .kingsmint/base/; ids are in the `id` metadata")
    (f, mine), (_, base) = found["ledger"], found[BASE]
    text = f.read_text(encoding="utf-8")
    f.write_text(text.replace(mine, reset(mine, base), 1), encoding="utf-8")
    print(f"ok   {tid} in {f.relative_to(root).as_posix()}: postings and flag as kingsmint wrote them; "
          "`uv run kingsmint reimport` applies the current rules")


def collect(root):
    """{id: (file, base, mine lead, mine entry)} and the other edited entries of the generated files, per file.
    Run before a reimport deletes ledger/; raises ValueError when a file cannot be read."""
    base, kept, other = {}, {}, {}
    for f in (root / BASE).rglob("*.beancount"):
        for tid, _, body, *_ in chunks(f.read_text(encoding="utf-8"), f.relative_to(root).as_posix()):
            if tid:
                base[tid] = body
    for f in (root / "ledger").rglob("*.beancount"):
        text = f.read_text(encoding="utf-8")
        if not text.startswith("; generated by kingsmint"):
            continue
        b = root / BASE / f.relative_to(root)
        known = {lead + body for _, lead, body, *_ in chunks(b.read_text(encoding="utf-8"), b.relative_to(root).as_posix())} if b.exists() else set()
        for tid, lead, body, *_ in chunks(text, f.relative_to(root).as_posix()):
            if tid:  # the same id twice (overlapping statements): keep an edited copy, an other edited one is lost
                new, old = (f, base.get(tid), lead, body), kept.get(tid)
                if old and edited(old):
                    if edited(new):
                        other.setdefault(f, []).append(lead + body)
                    continue
                kept[tid] = new
            elif lead + body not in known and known:
                other.setdefault(f, []).append(lead + body)  # added by hand, not a transaction kingsmint wrote
    return kept, other


def edited(entry):
    f, base, lead, mine = entry
    return bool(lead) or mine != base


def merge_file(theirs, kept, used):
    """The generated text with the user's edits from `kept` applied; (text, messages)."""
    ls, messages = lines(theirs), []
    for tid, _, body, start, end in reversed(chunks(theirs)):
        if tid not in kept or tid in used:
            continue  # the same id twice: the edits go to the first copy only
        f, base, lead, mine = kept[tid]
        if base is None and mine != body:
            continue  # no base to tell edits from changes by kingsmint: report_orphans keeps the old text
        used.add(tid)
        text, conflicts = merge_txn(base, mine, body)
        if conflicts:
            messages.append(f"conflict {tid}: {', '.join(conflicts)} changed by hand and by kingsmint; kept the hand edit. "
                            f"To take kingsmint's postings: `uv run kingsmint reset {tid}`")
        ls[start:end] = [lead + text]
    return "".join(ls), messages


def report_orphans(root, kept, other, used, rewritten):
    """Edited transactions and hand-written entries that a rewrite dropped go to .kingsmint/orphans.beancount,
    which main.beancount does not include: copy them back by hand."""
    lost = [lead + mine for tid, (f, base, lead, mine) in kept.items()
            if f in rewritten and tid not in used and edited((f, base, lead, mine))]
    lost += [t for f, texts in other.items() if f in rewritten for t in texts]
    if lost:
        with (root / ORPHANS).open("a", encoding="utf-8") as out:
            out.write("".join(f"\n{t}" for t in lost))
        print(f"WARN {len(lost)} edited entries are no longer in ledger/; see {ORPHANS.as_posix()}")
