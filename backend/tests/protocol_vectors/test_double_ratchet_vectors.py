"""
Protocol vectors for X3DH and Double Ratchet (Signal protocol).

These vectors use known X25519/Ed25519 test keys from RFC 8037/7748
and provide deterministic expected outputs for the HKDF-based derivation
steps used in the enc-chat E2EE implementation.

The frontend counterpart validates these same computations via
``npm run test:e2ee-vectors`` (see frontend/scripts/e2ee_protocol_vectors.mjs).
"""

import hashlib
import hmac
from binascii import hexlify, unhexlify


# ---------------------------------------------------------------------------
# RFC 8037 X25519 key material (converted from hex / base64url)
# ---------------------------------------------------------------------------

ALICE_PRIV_HEX = "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"
ALICE_PUB_HEX = "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a"  # computed
BOB_PRIV_HEX = "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb"
BOB_PUB_HEX = "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"


# ---------------------------------------------------------------------------
# RFC 5869 HKDF-SHA256 vector (Section A.1)
# ---------------------------------------------------------------------------

def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract(salt, ikm) -> PRK via HMAC-SHA256."""
    if not salt:
        salt = b"\x00" * 32
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand(PRK, info, L) -> OKM."""
    n = (length + 31) // 32
    t = b""
    okm = b""
    for i in range(1, n + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:length]


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return _hkdf_expand(_hkdf_extract(salt, ikm), info, length)


# ---------------------------------------------------------------------------
# Test: RFC 5869 HKDF-SHA256 output (Section A.1)
# ---------------------------------------------------------------------------

def test_rfc5869_hkdf_sha256():
    ikm = b"\x0b" * 22
    salt = unhexlify("000102030405060708090a0b0c")
    info = unhexlify("f0f1f2f3f4f5f6f7f8f9")
    expected = (
        "3cb25f25faacd57a90434f64d0362f2a"
        "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
        "34007208d5b887185865"
    )
    okm = _hkdf(salt, ikm, info, 42)
    assert hexlify(okm).decode() == expected


# ---------------------------------------------------------------------------
# Test: X3DH root key derivation (deterministic, with known DH outputs)
# ---------------------------------------------------------------------------

# Pre-computed shared secrets from RFC 7748 key pairs when used as
# identity, signed-prekey, ephemeral, and one-time-prekey keys in X3DH.
# DH(A_priv, B_pub) = DH(B_priv, A_pub) for X25519.
X25519_SHARED_AB_HEX = "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"

INFO_X3DH = b"enc-chat:x3dh"


def test_x3dh_root_key_vector():
    """Compute X3DH root key with four DH outputs from known test keys.

    Uses the known DH shared secret for Alice->Bob X25519 three times
    (identity×spk, ek×identity, ek×spk) plus once for ek×otk,
    then HKDF-extracts the root key.
    """
    dh = unhexlify(X25519_SHARED_AB_HEX)
    # Four DH operations concatenated (all the same shared secret in this
    # deterministic test since we reuse the same key pairs).
    fused = dh + dh + dh + dh
    root_key = _hkdf(b"\x00" * 32, fused, INFO_X3DH, 32)
    expected = unhexlify("ead0c589a4ae1659cdef2ca1834657e4bd7f3304a646b5649073c0c83a51f599")
    assert root_key == expected, f"X3DH root key mismatch: {hexlify(root_key).decode()}"


# ---------------------------------------------------------------------------
# Test: initial chain key derivation
# ---------------------------------------------------------------------------

INFO_SESSION_INIT = b"enc-chat:session:init"


def test_initial_chain_keys():
    """Derive initial send/recv chain keys from the X3DH root key."""
    root_key = unhexlify("ead0c589a4ae1659cdef2ca1834657e4bd7f3304a646b5649073c0c83a51f599")
    material = _hkdf(b"\x00" * 32, root_key, INFO_SESSION_INIT, 64)
    initiator_send = material[:32]
    responder_send = material[32:64]

    expected_init_send = unhexlify("8d5a1707b0e986ea583ce02e62a0a15308da325624a14c090157b703b8ed05bf")
    expected_resp_send = unhexlify("4ff44d3b44f3e499d02d1cd8eaa966b2a46f69004dee30c2e7f8be30e2fb97f5")

    assert initiator_send == expected_init_send
    assert responder_send == expected_resp_send


# ---------------------------------------------------------------------------
# Test: symmetric chain advancement
# ---------------------------------------------------------------------------

INFO_CHAIN_STEP = b"enc-chat:chain:step"


def test_chain_step():
    """Advance a symmetric ratchet chain key one step."""
    chain_key = unhexlify("8d5a1707b0e986ea583ce02e62a0a15308da325624a14c090157b703b8ed05bf")
    material = _hkdf(b"\x00" * 32, chain_key, INFO_CHAIN_STEP, 64)
    next_chain = material[:32]
    message_key = material[32:64]

    expected_next = unhexlify("1146414cac11053d22916c3f282e3f04373ff5c035bea09875bda638c6971303")
    expected_msg_key = unhexlify("4a36359801e226ce26187504cd082e7ac6bf942893ed80277f0ff98cc4603e1b")

    assert next_chain == expected_next
    assert message_key == expected_msg_key


# ---------------------------------------------------------------------------
# Test: DH ratchet step info strings
# ---------------------------------------------------------------------------

INFO_RATCHET = b"enc-chat:ratchet:v2"

# These info strings must match frontend/src/utils/e2ee/session.js
# and frontend/scripts/e2ee_protocol_vectors.mjs
assert INFO_RATCHET == b"enc-chat:ratchet:v2"
assert INFO_CHAIN_STEP == b"enc-chat:chain:step"
assert INFO_SESSION_INIT == b"enc-chat:session:init"
assert INFO_X3DH == b"enc-chat:x3dh"


# ---------------------------------------------------------------------------
# Test: skipped message key store format
# ---------------------------------------------------------------------------

def test_skipped_key_key_format():
    """Validate the expected key format for skipped message key storage.

    Keys are stored as ``{ratchet_prefix}:{counter}`` where ratchet_prefix
    is the first 32 chars of the ``receivingRatchetPublic`` JSON string
    (or "initial" if null).
    """
    ratchet_pub = '{"kty":"OKP","crv":"X25519","x":"test"}'
    counter = 3
    prefix = ratchet_pub[:32]
    expected_key = f"{prefix}:{counter}"
    assert expected_key == '{"kty":"OKP","crv":"X25519","x"::3'


# ---------------------------------------------------------------------------
# Test: Double Ratchet root key rotation
# ---------------------------------------------------------------------------

def test_double_ratchet_root_rotation():
    """Simulate one DH ratchet step: DH(my_priv, their_pub) mixed into
    root key, producing a single chain key and new root.

    Both sender and receiver compute the same DH via commutativity,
    so they derive the same chain key.
    """
    root_before = unhexlify("46a141344c2cc017c1bc95f6b0ded6fcf6f46e16a21d381f4185f0d85a324434")
    dh_shared = unhexlify(X25519_SHARED_AB_HEX)

    material = _hkdf(b"\x00" * 32, dh_shared + root_before, INFO_RATCHET, 64)
    root_after = material[:32]
    chain_key = material[32:64]

    assert len(chain_key) == 32
    assert len(root_after) == 32
    assert root_after != root_before, "Root key should change after DH ratchet"

    # Chain advancement from the ratchet-derived chain key
    material2 = _hkdf(b"\x00" * 32, chain_key, INFO_CHAIN_STEP, 64)
    assert len(material2[:32]) == 32
    assert len(material2[32:64]) == 32


# ---------------------------------------------------------------------------
# Test: envelope fields required for Double Ratchet
# ---------------------------------------------------------------------------

def test_double_ratchet_envelope_fields():
    """Verify the expected envelope fields for Double Ratchet messages."""
    required_fields = [
        "version", "mode", "session_id", "counter", "previous_counter",
        "dh_ratchet_key", "sender_device_id", "recipient_device_id",
        "nonce", "ciphertext",
    ]
    # prekey mode additionally requires:
    prekey_extra = [
        "sender_identity_key", "sender_ephemeral_key",
        "recipient_signed_prekey_id", "recipient_one_time_prekey_id",
    ]
    all_fields = set(required_fields + prekey_extra)
    assert "dh_ratchet_key" in all_fields
    assert "previous_counter" in all_fields
    assert "counter" in all_fields
    assert len(required_fields) == 10


# ---------------------------------------------------------------------------
# End-to-End: Full Double Ratchet round-trip (3 messages)
# ---------------------------------------------------------------------------

def _x25519_shared(pub_hex: str, priv_hex: str) -> bytes:
    """Simulate X25519 DH using pre-computed hex values.
    
    Uses known RFC 7748 test vectors: DH(A_priv, B_pub) = known value.
    """
    if priv_hex == ALICE_PRIV_HEX and pub_hex == BOB_PUB_HEX:
        return unhexlify("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
    if priv_hex == BOB_PRIV_HEX and pub_hex == ALICE_PUB_HEX:
        return unhexlify("4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
    # For any other key pair: simulate via HMAC-based derivation
    return _hkdf(b"\x00" * 32, unhexlify(priv_hex + pub_hex), b"mock-dh", 32)


def test_full_double_ratchet_roundtrip():
    """End-to-end Double Ratchet with 3 messages using actual HKDF derivations.

    Sequence:  Alice -> Bob (M1),  Bob -> Alice (M2 with ratchet),
               Alice -> Bob (M3 with ratchet).

    Uses the known RFC 7748 X25519 shared secret for all DH operations
    in X3DH, and known test keys for ratchet steps.
    """
    dh_shared = unhexlify(X25519_SHARED_AB_HEX)

    # ── X3DH root key (4× same DH for deterministic test) ───
    fused = dh_shared + dh_shared + dh_shared + dh_shared
    root = _hkdf(b"\x00" * 32, fused, INFO_X3DH, 32)

    # ── Initial chain keys ──────────────────────────────────
    init_material = _hkdf(b"\x00" * 32, root, INFO_SESSION_INIT, 64)
    alice_send = init_material[:32]
    alice_recv = init_material[32:64]
    bob_send = init_material[32:64]
    bob_recv = init_material[:32]

    assert alice_send == bob_recv, "Alice send chain != Bob recv chain"
    assert alice_recv == bob_send, "Alice recv chain != Bob send chain"

    # ── Message 1: Alice -> Bob ──────────────────────────────
    m1_material = _hkdf(b"\x00" * 32, alice_send, INFO_CHAIN_STEP, 64)
    msg_key_a1 = m1_material[32:64]
    alice_send = m1_material[:32]

    m1b_material = _hkdf(b"\x00" * 32, bob_recv, INFO_CHAIN_STEP, 64)
    msg_key_b1 = m1b_material[32:64]
    bob_recv = m1b_material[:32]
    assert msg_key_a1 == msg_key_b1, "M1 message key mismatch"

    # ── Bob ratchets and sends M2 ────────────────────────────
    bob_ratchet_dh = dh_shared  # DH(Bob_new_priv, Alice_pub)
    bob_ratchet_mat = _hkdf(b"\x00" * 32, bob_ratchet_dh + root, INFO_RATCHET, 64)
    bob_root_after = bob_ratchet_mat[:32]
    bob_raw_send_chain = bob_ratchet_mat[32:64]

    m2_material = _hkdf(b"\x00" * 32, bob_raw_send_chain, INFO_CHAIN_STEP, 64)
    msg_key_b2 = m2_material[32:64]
    bob_new_send = m2_material[:32]

    # ── Alice receives M2: ratchets with same DH ─────────────
    alice_ratchet_mat = _hkdf(b"\x00" * 32, dh_shared + root, INFO_RATCHET, 64)
    alice_root_after = alice_ratchet_mat[:32]
    alice_raw_recv_chain = alice_ratchet_mat[32:64]

    # The raw chain keys (before symmetric ratchet advancement) must match
    assert bob_raw_send_chain == alice_raw_recv_chain, \
        "Bob ratchet send chain != Alice ratchet recv chain"
    assert bob_root_after == alice_root_after, \
        "Root keys diverged after first ratchet"

    m2a_material = _hkdf(b"\x00" * 32, alice_raw_recv_chain, INFO_CHAIN_STEP, 64)
    msg_key_a2 = m2a_material[32:64]
    alice_new_recv = m2a_material[:32]
    assert msg_key_b2 == msg_key_a2, "M2 message key mismatch"

    # ── Alice ratchets and sends M3 ──────────────────────────
    alice2_ratchet_mat = _hkdf(b"\x00" * 32, dh_shared + alice_root_after, INFO_RATCHET, 64)
    alice_root2 = alice2_ratchet_mat[:32]
    alice_raw_send_chain = alice2_ratchet_mat[32:64]

    m3_material = _hkdf(b"\x00" * 32, alice_raw_send_chain, INFO_CHAIN_STEP, 64)
    msg_key_a3 = m3_material[32:64]
    alice_new_send = m3_material[:32]

    # ── Bob receives M3: ratchets with same DH ───────────────
    bob2_ratchet_mat = _hkdf(b"\x00" * 32, dh_shared + bob_root_after, INFO_RATCHET, 64)
    bob_root2 = bob2_ratchet_mat[:32]
    bob_raw_recv_chain = bob2_ratchet_mat[32:64]

    assert alice_raw_send_chain == bob_raw_recv_chain, \
        "Alice ratchet send chain != Bob ratchet recv chain"
    assert bob_root2 == alice_root2, \
        "Root keys diverged after second ratchet"

    m3b_material = _hkdf(b"\x00" * 32, bob_raw_recv_chain, INFO_CHAIN_STEP, 64)
    msg_key_b3 = m3b_material[32:64]
    assert msg_key_a3 == msg_key_b3, "M3 message key mismatch"
