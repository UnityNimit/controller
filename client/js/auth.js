/**
 * Project Controller - Pure JavaScript NIST SHA-256 & HMAC-SHA256 Auth Module
 * Compatible with all mobile edge browsers without requiring window.crypto.subtle
 */

function sha256Bytes(data) {
  function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
  function ch(x, y, z) { return (x & y) ^ (~x & z); }
  function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z); }
  function sigma0(x) { return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x); }
  function sigma1(x) { return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x); }
  function gamma0(x) { return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3); }
  function gamma1(x) { return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10); }

  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  let bytes;
  if (typeof data === "string") {
    bytes = [];
    for (let i = 0; i < data.length; i++) {
      const code = data.charCodeAt(i);
      if (code < 128) {
        bytes.push(code);
      } else if (code < 2048) {
        bytes.push(192 | (code >> 6), 128 | (code & 63));
      } else {
        bytes.push(224 | (code >> 12), 128 | ((code >> 6) & 63), 128 | (code & 63));
      }
    }
  } else {
    bytes = Array.from(data);
  }

  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while ((bytes.length + 8) % 64 !== 0) {
    bytes.push(0);
  }
  bytes.push(0, 0, 0, 0);
  bytes.push((bitLen >>> 24) & 0xff);
  bytes.push((bitLen >>> 16) & 0xff);
  bytes.push((bitLen >>> 8) & 0xff);
  bytes.push(bitLen & 0xff);

  let H = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ];

  const W = new Uint32Array(64);

  for (let i = 0; i < bytes.length; i += 64) {
    for (let t = 0; t < 16; t++) {
      W[t] = ((bytes[i + t * 4] << 24) |
             (bytes[i + t * 4 + 1] << 16) |
             (bytes[i + t * 4 + 2] << 8) |
             (bytes[i + t * 4 + 3])) >>> 0;
    }
    for (let t = 16; t < 64; t++) {
      W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = H;

    for (let t = 0; t < 64; t++) {
      const T1 = (h + sigma1(e) + ch(e, f, g) + K[t] + W[t]) >>> 0;
      const T2 = (sigma0(a) + maj(a, b, c)) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + T1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (T1 + T2) >>> 0;
    }

    H[0] = (H[0] + a) >>> 0;
    H[1] = (H[1] + b) >>> 0;
    H[2] = (H[2] + c) >>> 0;
    H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0;
    H[5] = (H[5] + f) >>> 0;
    H[6] = (H[6] + g) >>> 0;
    H[7] = (H[7] + h) >>> 0;
  }

  const out = [];
  for (let i = 0; i < 8; i++) {
    for (let j = 3; j >= 0; j--) {
      out.push((H[i] >>> (j * 8)) & 0xff);
    }
  }
  return out;
}

function hmacSha256Hex(keyStr, msgStr) {
  let keyBytes = [];
  for (let i = 0; i < keyStr.length; i++) keyBytes.push(keyStr.charCodeAt(i) & 0xff);
  if (keyBytes.length > 64) {
    keyBytes = sha256Bytes(keyBytes);
  }
  while (keyBytes.length < 64) keyBytes.push(0);

  const oPad = keyBytes.map(b => b ^ 0x5c);
  const iPad = keyBytes.map(b => b ^ 0x36);

  let msgBytes = [];
  for (let i = 0; i < msgStr.length; i++) msgBytes.push(msgStr.charCodeAt(i) & 0xff);

  const inner = sha256Bytes(iPad.concat(msgBytes));
  const outer = sha256Bytes(oPad.concat(inner));

  return outer.map(b => b.toString(16).padStart(2, "0")).join("");
}

class SecurityEngine {
  solveChallenge(nonceHex, timestamp, clientId, preferredSlot) {
    const payload = `${nonceHex}:${timestamp}`;
    const signature = hmacSha256Hex("controller-cyber-physical-key-2026", payload);
    return {
      type: "AUTH_RESPONSE",
      nonce: nonceHex,
      timestamp: timestamp,
      signature: signature,
      client_id: clientId,
      preferred_slot: preferredSlot
    };
  }
}

if (typeof window !== "undefined") {
  window.sha256Bytes = sha256Bytes;
  window.hmacSha256Hex = hmacSha256Hex;
  window.SecurityEngine = SecurityEngine;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { sha256Bytes, hmacSha256Hex, SecurityEngine };
}
