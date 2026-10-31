"""P3: the hard gate admits public/group, needs the owner for private, denies secret."""

from __future__ import annotations

from echomind.mind.disclosure import gate


def _gate(sensitivity: str, owner: str, audience: tuple[str, ...]) -> bool:
    return gate(
        sensitivity=sensitivity, owner_id=owner,
        audience=frozenset(audience), venue="g",
    ).allowed


def test_public_and_group_pass() -> None:
    assert _gate("public", "", ())
    assert _gate("group", "", ())


def test_private_needs_the_owner_present() -> None:
    assert _gate("private", "L", ("L",))
    assert not _gate("private", "L", ("M",))


def test_secret_needs_a_grant() -> None:
    assert not _gate("secret", "L", ("L",))
    assert gate(sensitivity="secret", owner_id="L", audience=frozenset({"L"}),
                venue="g", granted=True).allowed


def test_secret_and_unknown_fail_closed() -> None:
    assert not _gate("private", "", ("L",))
    assert not _gate("mystery", "L", ("L",))
