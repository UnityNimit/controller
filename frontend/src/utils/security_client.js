/**
 * Project Controller - Client-Side Cryptographic Security Module
 * Computes HMAC-SHA256 Challenge-Response signatures via Web Cryptography API.
 */

const DEFAULT_SECRET = "controller-cyber-physical-key-2026";

export class SecurityClient {
  constructor(secret = DEFAULT_SECRET) {
    this.secret = secret;
    this.clientId = this._getOrCreateClientId();
  }

  _getOrCreateClientId() {
    let id = localStorage.getItem("controller_client_id");
    if (!id) {
      const arr = new Uint8Array(8);
      window.crypto.getRandomValues(arr);
      id = "node_" + Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
      localStorage.setItem("controller_client_id", id);
    }
    return id;
  }

  /**
   * Responds to gateway AUTH_CHALLENGE:
   * Computes HMAC-SHA256(secret, nonce + ":" + timestamp)
   */
  async solveChallenge(nonce, timestamp) {
    const payload = `${nonce}:${timestamp}`;
    const encoder = new TextEncoder();
    const keyData = encoder.encode(this.secret);
    const msgData = encoder.encode(payload);

    try {
      const cryptoKey = await window.crypto.subtle.importKey(
        "raw",
        keyData,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
      );

      const signatureBuffer = await window.crypto.subtle.sign(
        "HMAC",
        cryptoKey,
        msgData
      );

      const hashArray = Array.from(new Uint8Array(signatureBuffer));
      const hexSignature = hashArray.map(b => b.toString(16).padStart(2, "0")).join("");

      return {
        type: "AUTH_RESPONSE",
        client_id: this.clientId,
        nonce: nonce,
        timestamp: timestamp,
        signature: hexSignature
      };
    } catch (err) {
      console.error("[Security] Crypto error:", err);
      return {
        type: "AUTH_RESPONSE",
        client_id: this.clientId,
        nonce: nonce,
        timestamp: timestamp,
        signature: "crypto_unsupported"
      };
    }
  }
}
