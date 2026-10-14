package com.fourstar.qcmsapp;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Session secrets are encrypted with an AES-256 key that lives inside the Android Keystore
 * (hardware backed on most phones). The password itself is never stored.
 */
public final class SecureStore {
    private static final String ALIAS = "qcms_session_key";
    private static final String PREFS = "qcms_secure";
    private final SharedPreferences prefs;

    public SecureStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            KeyStore.Entry entry = ks.getEntry(ALIAS, null);
            if (entry instanceof KeyStore.SecretKeyEntry) return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build());
        return generator.generateKey();
    }

    public void put(String name, String value) {
        if (value == null) {
            prefs.edit().remove(name).apply();
            return;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key());
            byte[] iv = cipher.getIV();
            byte[] data = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            prefs.edit().putString(name, Base64.encodeToString(iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(data, Base64.NO_WRAP)).apply();
        } catch (Exception e) {
            prefs.edit().remove(name).apply();
        }
    }

    public String get(String name) {
        String raw = prefs.getString(name, null);
        if (raw == null || !raw.contains(":")) return null;
        try {
            String[] parts = raw.split(":", 2);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
            return new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
        } catch (Exception e) {
            prefs.edit().remove(name).apply();
            return null;
        }
    }

    public void clear() {
        prefs.edit().clear().apply();
    }
}
