package com.fourstar.qcmsapp;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.zip.CRC32;
import java.util.zip.Deflater;

/**
 * R39 · Minimal QR Code encoder (no library): ISO/IEC 18004 model 2, error correction level M, versions 1-40,
 * numeric / alphanumeric / byte (UTF-8) mode - the same choices as the website encoder (reportlab qrencoder, a
 * port of Kazuhiko Arase's qrcode.js used by core/qr_codes.qr_matrix): smallest version that fits, mode tried in
 * the order numeric -> alphanumeric -> byte, and the mask chosen with the same "lost point" score, so the module
 * matrix is identical to the website's QR for the same text. Pure Java (unit-testable off-device).
 *
 *   boolean[][] m = IncQrCode.encode("https://.../rmtc-records?rmtc=RMTC-0001");   // true = dark
 *   byte[] png  = IncQrCode.png(m, 10, 4);                                          // core.qr_codes.png_from_matrix
 */
final class IncQrCode {
    private IncQrCode() { }

    static final String ECC_LEVEL = "M";
    static final int MIN_VERSION = 1, MAX_VERSION = 40;
    /** Error correction codewords per block, level M, versions 1..40 (index 0 unused). */
    private static final int[] ECC_PER_BLOCK_M = {-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26,
        26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28};
    /** Number of error correction blocks, level M, versions 1..40. */
    private static final int[] BLOCKS_M = {-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16,
        17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49};
    /** Alignment pattern centres (reportlab QRUtil.PATTERN_POSITION_TABLE). */
    private static final int[][] ALIGN = {
        {}, {6, 18}, {6, 22}, {6, 26}, {6, 30}, {6, 34}, {6, 22, 38}, {6, 24, 42}, {6, 26, 46}, {6, 28, 50}, {6, 30, 54}, {6, 32, 58},
        {6, 34, 62}, {6, 26, 46, 66}, {6, 26, 48, 70}, {6, 26, 50, 74}, {6, 30, 54, 78}, {6, 30, 56, 82}, {6, 30, 58, 86}, {6, 34, 62, 90},
        {6, 28, 50, 72, 94}, {6, 26, 50, 74, 98}, {6, 30, 54, 78, 102}, {6, 28, 54, 80, 106}, {6, 32, 58, 84, 110}, {6, 30, 58, 86, 114},
        {6, 34, 62, 90, 118}, {6, 26, 50, 74, 98, 122}, {6, 30, 54, 78, 102, 126}, {6, 26, 52, 78, 104, 130}, {6, 30, 56, 82, 108, 134},
        {6, 34, 60, 86, 112, 138}, {6, 30, 58, 86, 114, 142}, {6, 34, 62, 90, 118, 146}, {6, 30, 54, 78, 102, 126, 150},
        {6, 24, 50, 76, 102, 128, 154}, {6, 28, 54, 80, 106, 132, 158}, {6, 32, 58, 84, 110, 136, 162}, {6, 26, 54, 82, 110, 138, 166},
        {6, 30, 58, 86, 114, 142, 170}};
    private static final String ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";
    private static final int ECL_M_BITS = 0;   // format information bits of level M

    // ------------------------------------------------------------------ public API
    static boolean[][] encode(String text) { return encode(text, -1); }

    /** mask -1 = best mask (lost point), 0..7 = forced (tests). */
    static boolean[][] encode(String text, int mask) {
        Segment seg = Segment.of(text == null ? "" : text);
        int version = -1;
        for (int v = MIN_VERSION; v <= MAX_VERSION; v++) {
            if (4 + seg.lengthBits(v) + seg.bitLength() <= dataCodewords(v) * 8) { version = v; break; }
        }
        if (version < 0) throw new IllegalArgumentException("Text too long for a QR code (" + seg.count + " characters).");
        byte[] codewords = interleave(version, dataBytes(seg, version));
        if (mask >= 0) return build(version, codewords, mask & 7, false);
        int best = 0, min = Integer.MAX_VALUE;
        for (int m = 0; m < 8; m++) {
            int lost = lostPoint(build(version, codewords, m, true));
            if (lost < min) { min = lost; best = m; }
        }
        return build(version, codewords, best, false);
    }

    static int version(boolean[][] matrix) { return (matrix.length - 17) / 4; }

    /** core.qr_codes.png_from_matrix: 8-bit greyscale PNG, scale px per module, quiet zone border modules. */
    static byte[] png(boolean[][] matrix, int scale, int border) {
        scale = Math.max(1, scale);
        border = Math.max(0, border);
        int modules = matrix.length;
        int size = (modules + 2 * border) * scale;
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        byte[] white = new byte[size + 1];
        for (int i = 1; i <= size; i++) white[i] = (byte) 0xFF;
        for (int i = 0; i < border * scale; i++) raw.write(white, 0, white.length);
        for (boolean[] row : matrix) {
            byte[] line = new byte[size + 1];
            int p = 1;
            for (int i = 0; i < border * scale; i++) line[p++] = (byte) 0xFF;
            for (boolean dark : row) for (int s = 0; s < scale; s++) line[p++] = dark ? 0 : (byte) 0xFF;
            while (p <= size) line[p++] = (byte) 0xFF;
            for (int s = 0; s < scale; s++) raw.write(line, 0, line.length);
        }
        for (int i = 0; i < border * scale; i++) raw.write(white, 0, white.length);
        Deflater d = new Deflater(9);
        d.setInput(raw.toByteArray());
        d.finish();
        ByteArrayOutputStream z = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        while (!d.finished()) { int n = d.deflate(buf); z.write(buf, 0, n); }
        d.end();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(new byte[]{(byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n'}, 0, 8);
        byte[] ihdr = new byte[13];
        put32(ihdr, 0, size);
        put32(ihdr, 4, size);
        ihdr[8] = 8;  // bit depth
        ihdr[9] = 0;  // greyscale
        chunk(out, "IHDR", ihdr);
        chunk(out, "IDAT", z.toByteArray());
        chunk(out, "IEND", new byte[0]);
        return out.toByteArray();
    }

    private static void put32(byte[] b, int off, int v) {
        b[off] = (byte) (v >>> 24); b[off + 1] = (byte) (v >>> 16); b[off + 2] = (byte) (v >>> 8); b[off + 3] = (byte) v;
    }

    private static void chunk(ByteArrayOutputStream out, String kind, byte[] data) {
        byte[] len = new byte[4];
        put32(len, 0, data.length);
        out.write(len, 0, 4);
        byte[] k = kind.getBytes(StandardCharsets.US_ASCII);
        out.write(k, 0, 4);
        out.write(data, 0, data.length);
        CRC32 crc = new CRC32();
        crc.update(k);
        crc.update(data);
        byte[] c = new byte[4];
        put32(c, 0, (int) crc.getValue());
        out.write(c, 0, 4);
    }

    // ------------------------------------------------------------------ data segment (reportlab QRNumber / QRAlphaNum / QR8bitByte)
    private static final class Segment {
        final int mode;      // 1 numeric, 2 alphanumeric, 4 byte
        final byte[] bytes;  // byte mode payload
        final String text;
        final int count;

        private Segment(int mode, String text, byte[] bytes, int count) { this.mode = mode; this.text = text; this.bytes = bytes; this.count = count; }

        static Segment of(String t) {
            if (t.matches("[0-9]*")) return new Segment(1, t, null, t.length());
            if (t.matches("[-0-9A-Z $%*+./:]*")) return new Segment(2, t, null, t.length());
            byte[] b = t.getBytes(StandardCharsets.UTF_8);
            return new Segment(4, t, b, b.length);
        }

        int lengthBits(int v) {
            int i = v < 10 ? 0 : v < 27 ? 1 : 2;
            if (mode == 1) return new int[]{10, 12, 14}[i];
            if (mode == 2) return new int[]{9, 11, 13}[i];
            return new int[]{8, 16, 16}[i];
        }

        int bitLength() {
            if (mode == 1) { int q = count / 3, r = count % 3; return q * 10 + (r == 1 ? 4 : r == 2 ? 7 : 0); }
            if (mode == 2) { int q = count / 2, r = count % 2; return q * 11 + (r == 1 ? 6 : 0); }
            return count * 8;
        }

        void write(Bits b, int version) {
            b.put(mode, 4);
            b.put(count, lengthBits(version));
            if (mode == 1) {
                for (int i = 0; i < count; i += 3) {
                    int n = Math.min(3, count - i);
                    b.put(Integer.parseInt(text.substring(i, i + n)), n == 3 ? 10 : n == 2 ? 7 : 4);
                }
            } else if (mode == 2) {
                for (int i = 0; i < count; i += 2) {
                    if (i + 1 < count) b.put(ALNUM.indexOf(text.charAt(i)) * 45 + ALNUM.indexOf(text.charAt(i + 1)), 11);
                    else b.put(ALNUM.indexOf(text.charAt(i)), 6);
                }
            } else {
                for (byte x : bytes) b.put(x & 0xFF, 8);
            }
        }
    }

    private static final class Bits {
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
        int length = 0, cur = 0;
        void put(int value, int bits) { for (int i = bits - 1; i >= 0; i--) bit(((value >>> i) & 1) == 1); }
        void bit(boolean on) {
            if (on) cur |= 0x80 >>> (length % 8);
            length++;
            if (length % 8 == 0) { out.write(cur); cur = 0; }
        }
        byte[] bytes() {
            ByteArrayOutputStream copy = new ByteArrayOutputStream();
            byte[] done = out.toByteArray();
            copy.write(done, 0, done.length);
            if (length % 8 != 0) copy.write(cur);
            return copy.toByteArray();
        }
    }

    // ------------------------------------------------------------------ codewords
    private static int rawDataModules(int v) {
        int result = (16 * v + 128) * v + 64;
        if (v >= 2) {
            int numAlign = v / 7 + 2;
            result -= (25 * numAlign - 10) * numAlign - 55;
            if (v >= 7) result -= 36;
        }
        return result;
    }

    static int dataCodewords(int v) { return rawDataModules(v) / 8 - ECC_PER_BLOCK_M[v] * BLOCKS_M[v]; }

    private static byte[] dataBytes(Segment seg, int v) {
        Bits b = new Bits();
        seg.write(b, v);
        int capacity = dataCodewords(v) * 8;
        if (b.length + 4 <= capacity) b.put(0, 4);  // terminator
        while (b.length % 8 != 0) b.bit(false);
        boolean ec = true;
        while (b.length < capacity) { b.put(ec ? 0xEC : 0x11, 8); ec = !ec; }
        return b.bytes();
    }

    private static byte[] interleave(int v, byte[] data) {
        int blocks = BLOCKS_M[v], ecLen = ECC_PER_BLOCK_M[v];
        int raw = rawDataModules(v) / 8;
        int numShort = blocks - raw % blocks;
        int shortLen = raw / blocks;
        byte[][] dataBlocks = new byte[blocks][];
        byte[][] ecBlocks = new byte[blocks][];
        byte[] gen = generator(ecLen);
        int k = 0;
        for (int i = 0; i < blocks; i++) {
            int dLen = shortLen - ecLen + (i < numShort ? 0 : 1);
            dataBlocks[i] = new byte[dLen];
            System.arraycopy(data, k, dataBlocks[i], 0, dLen);
            k += dLen;
            ecBlocks[i] = remainder(dataBlocks[i], gen);
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int maxData = shortLen - ecLen + 1;
        for (int i = 0; i < maxData; i++) for (int j = 0; j < blocks; j++) if (i < dataBlocks[j].length) out.write(dataBlocks[j][i]);
        for (int i = 0; i < ecLen; i++) for (int j = 0; j < blocks; j++) out.write(ecBlocks[j][i]);
        return out.toByteArray();
    }

    private static int gfMul(int x, int y) {
        int z = 0;
        for (int i = 7; i >= 0; i--) {
            z = (z << 1) ^ ((z >>> 7) * 0x11D);
            z ^= ((y >>> i) & 1) * x;
        }
        return z & 0xFF;
    }

    /** Reed-Solomon generator (coefficients without the leading 1), roots alpha^0..alpha^(degree-1). */
    private static byte[] generator(int degree) {
        byte[] r = new byte[degree];
        r[degree - 1] = 1;
        int root = 1;
        for (int i = 0; i < degree; i++) {
            for (int j = 0; j < r.length; j++) {
                r[j] = (byte) gfMul(r[j] & 0xFF, root);
                if (j + 1 < r.length) r[j] ^= r[j + 1];
            }
            root = gfMul(root, 0x02);
        }
        return r;
    }

    private static byte[] remainder(byte[] data, byte[] gen) {
        byte[] r = new byte[gen.length];
        for (byte b : data) {
            int factor = (b ^ r[0]) & 0xFF;
            System.arraycopy(r, 1, r, 0, r.length - 1);
            r[r.length - 1] = 0;
            for (int i = 0; i < r.length; i++) r[i] ^= (byte) gfMul(gen[i] & 0xFF, factor);
        }
        return r;
    }

    // ------------------------------------------------------------------ matrix
    private static boolean maskBit(int mask, int r, int c) {
        switch (mask) {
            case 0: return (r + c) % 2 == 0;
            case 1: return r % 2 == 0;
            case 2: return c % 3 == 0;
            case 3: return (r + c) % 3 == 0;
            case 4: return (r / 2 + c / 3) % 2 == 0;
            case 5: return (r * c) % 2 + (r * c) % 3 == 0;
            case 6: return ((r * c) % 2 + (r * c) % 3) % 2 == 0;
            default: return ((r * c) % 3 + (r + c) % 2) % 2 == 0;
        }
    }

    private static int bchDigit(int data) { int d = 0; while (data != 0) { d++; data >>>= 1; } return d; }

    static int formatBits(int mask) {
        int data = (ECL_M_BITS << 3) | mask;
        int d = data << 10, g15 = 0x537;
        while (bchDigit(d) - bchDigit(g15) >= 0) d ^= g15 << (bchDigit(d) - bchDigit(g15));
        return ((data << 10) | d) ^ 0x5412;
    }

    static int versionBits(int v) {
        int d = v << 12, g18 = 0x1F25;
        while (bchDigit(d) - bchDigit(g18) >= 0) d ^= g18 << (bchDigit(d) - bchDigit(g18));
        return (v << 12) | d;
    }

    /** One complete symbol; test = format / version / dark module left light (mask evaluation like the website). */
    private static boolean[][] build(int v, byte[] codewords, int mask, boolean test) {
        int n = v * 4 + 17;
        boolean[][] m = new boolean[n][n];
        boolean[][] fn = new boolean[n][n];
        finder(m, fn, 0, 0);
        finder(m, fn, n - 7, 0);
        finder(m, fn, 0, n - 7);
        for (int i = 8; i < n - 8; i++) {
            set(m, fn, i, 6, i % 2 == 0);
            set(m, fn, 6, i, i % 2 == 0);
        }
        int[] pos = ALIGN[v - 1];
        int maxpos = n - 8;
        for (int row : pos) for (int col : pos) {
            if (col <= 8 && (row <= 8 || row >= maxpos)) continue;
            if (col >= maxpos && row <= 8) continue;
            for (int dr = -2; dr <= 2; dr++) for (int dc = -2; dc <= 2; dc++)
                set(m, fn, row + dr, col + dc, Math.max(Math.abs(dr), Math.abs(dc)) != 1);
        }
        int fbits = formatBits(mask);
        for (int i = 0; i < 15; i++) {
            boolean on = !test && ((fbits >>> i) & 1) == 1;
            if (i < 6) set(m, fn, i, 8, on);
            else if (i < 8) set(m, fn, i + 1, 8, on);
            else set(m, fn, n - 15 + i, 8, on);
            if (i < 8) set(m, fn, 8, n - i - 1, on);
            else if (i < 9) set(m, fn, 8, 15 - i - 1 + 1, on);
            else set(m, fn, 8, 15 - i - 1, on);
        }
        set(m, fn, n - 8, 8, !test);
        if (v >= 7) {
            int vbits = versionBits(v);
            for (int i = 0; i < 18; i++) {
                boolean on = !test && ((vbits >>> i) & 1) == 1;
                set(m, fn, i / 3, i % 3 + n - 11, on);
                set(m, fn, i % 3 + n - 11, i / 3, on);
            }
        }
        // data (zig-zag from the bottom right, skipping function modules); remainder bits are light, everything masked
        int bit = 0, total = codewords.length * 8;
        for (int right = n - 1; right >= 1; right -= 2) {
            if (right == 6) right = 5;
            for (int vert = 0; vert < n; vert++) {
                for (int j = 0; j < 2; j++) {
                    int x = right - j;
                    boolean upward = ((right + 1) & 2) == 0;
                    int y = upward ? n - 1 - vert : vert;
                    if (fn[y][x]) continue;
                    boolean dark = bit < total && ((codewords[bit >>> 3] >>> (7 - (bit & 7))) & 1) == 1;
                    bit++;
                    m[y][x] = dark ^ maskBit(mask, y, x);
                }
            }
        }
        return m;
    }

    private static void set(boolean[][] m, boolean[][] fn, int r, int c, boolean dark) { m[r][c] = dark; fn[r][c] = true; }

    private static void finder(boolean[][] m, boolean[][] fn, int row, int col) {
        int n = m.length;
        for (int dr = -1; dr <= 7; dr++) for (int dc = -1; dc <= 7; dc++) {
            int r = row + dr, c = col + dc;
            if (r < 0 || c < 0 || r >= n || c >= n) continue;
            boolean dark = dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6
                && (dr == 0 || dr == 6 || dc == 0 || dc == 6 || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4));
            set(m, fn, r, c, dark);
        }
    }

    // ------------------------------------------------------------------ mask score (reportlab QRUtil.getLostPoint)
    static int lostPoint(boolean[][] m) {
        int n = m.length;
        boolean[][] t = new boolean[n][n];
        for (int r = 0; r < n; r++) for (int c = 0; c < n; c++) t[c][r] = m[r][c];
        // reportlab quirk kept on purpose: its vertical finder-like check compares a tuple with a list and never
        // scores, so only the horizontal rule-3 pass counts (same mask choice as the website).
        int score = rule1(m) + rule1(t) + rule2(m) + rule3(m);
        int count = 0;
        for (boolean[] row : m) for (boolean d : row) if (d) count++;
        int cells = n * n;
        score += 10 * (Math.abs(100 * count / cells - 50) / 5);
        return score;
    }

    /** maskScoreRule1vert: runs down each column of the given row list (rows compared in sequence). */
    private static int rule1(boolean[][] rows) {
        int n = rows[0].length, score = 0;
        int[] last = new int[n];
        for (int r = 1; r < rows.length; r++) {
            for (int c = 0; c < n; c++) {
                boolean changed = rows[r][c] ^ rows[r - 1][c];
                if (last[c] >= 4 && changed) score += last[c] - 1;
                last[c] = changed ? 0 : last[c] + 1;
            }
        }
        for (int b : last) if (b >= 4) score += b - 1;
        return score;
    }

    private static int rule2(boolean[][] m) {
        int score = 0;
        for (int r = 1; r < m.length; r++)
            for (int c = 1; c < m.length; c++)
                if (m[r][c] == m[r - 1][c] && m[r][c] == m[r][c - 1] && m[r][c] == m[r - 1][c - 1]) score += 3;
        return score;
    }

    private static final boolean[] RULE3 = {true, false, true, true, true, false, true, false, false, false, false};

    private static int rule3(boolean[][] rows) {
        int score = 0, len = RULE3.length;
        for (boolean[] row : rows) {
            int j = 0, maxj = row.length - len;
            while (j < maxj) {
                boolean match = true;
                for (int k = 0; k < len; k++) if (row[j + k] != RULE3[k]) { match = false; break; }
                if (match) { score += 40; j += len; } else j++;
            }
        }
        return score;
    }
}
