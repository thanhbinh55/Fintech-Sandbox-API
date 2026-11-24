"""Vietnamese Financial Inverse Text Normalization (ITN) for ASR outputs.

Adapted and extended for fintech/MoMo domain from Zalo AI Challenge Vietnamese ITN:
- Normalizes spoken phone/account numbers ('không chín một hai...' -> '0912...')
- Normalizes Vietnamese bank & e-wallet ASR phonetic variants ('việt com banh' -> 'Vietcombank',
  'bê i đê vê' -> 'BIDV', 'tếch com' -> 'Techcombank', 'mô mô' -> 'MoMo', ...)
- Normalizes spoken Vietnamese compound numbers & financial slang ('hai lít rưỡi' -> '250000',
  'một củ rưỡi' -> '1500000', 'một trăm năm mươi ca' -> '150000')
- Restores sentence casing while preserving fintech & bank acronyms and mixed-case brand names.
"""
from __future__ import annotations

import re

ACRONYMS = {
    "SJC", "TP.HCM", "TPHCM", "ATM", "OTP", "PIN", "VND", "USD", "EUR", "SMS",
    "MOMO", "ZALOPAY", "VNPAY", "VIETQR", "QR", "VCB", "TCB", "MB", "BIDV", "ACB",
    "VPB", "TPB", "ICB", "STB", "HDB", "VIB", "OCB", "MSB", "SHB", "VBA", "LPB",
    "SEAB", "EIB", "ABB", "BVB", "NCB", "PGB", "HSBC", "UOB", "VISA", "NAPAS",
    "AI", "VAT",
}

# Unambiguous bank names & Gipformer ASR phonetic variants -> Canonical Name
UNAMBIGUOUS_BANK_VARIANTS: dict[str, str] = {
    # Big 4
    "việt com banh": "Vietcombank",
    "việt com bank": "Vietcombank",
    "viet com bank": "Vietcombank",
    "vietcombank": "Vietcombank",
    "vê xê bê": "Vietcombank",
    "vê sê bê": "Vietcombank",
    "vcb": "Vietcombank",
    "bi ai đi vi": "BIDV",
    "bê i đê vê": "BIDV",
    "bi i đê vê": "BIDV",
    "bê i đi vi": "BIDV",
    "bidv": "BIDV",
    "đầu tư và phát triển": "BIDV",
    "việt tin banh": "VietinBank",
    "việt tin bank": "VietinBank",
    "việt in banh": "VietinBank",
    "việt in bank": "VietinBank",
    "vietin bank": "VietinBank",
    "vietinbank": "VietinBank",
    "i xê bê": "VietinBank",
    "a gờ ri banh": "Agribank",
    "a gờ ri bank": "Agribank",
    "agri bank": "Agribank",
    "agribank": "Agribank",
    "vê bê a": "Agribank",
    # Popular JSBs
    "tếch com banh": "Techcombank",
    "tếch com bank": "Techcombank",
    "tét com banh": "Techcombank",
    "tét com bank": "Techcombank",
    "tech com bank": "Techcombank",
    "techcombank": "Techcombank",
    "tếch com": "Techcombank",
    "tê xê bê": "Techcombank",
    "tcb": "Techcombank",
    "em bi banh": "MB Bank",
    "em bi bank": "MB Bank",
    "mờ bê banh": "MB Bank",
    "mờ bê bank": "MB Bank",
    "mb bank": "MB Bank",
    "mb banh": "MB Bank",
    "mờ bê": "MB Bank",
    "a xê bê": "ACB",
    "a sê bê": "ACB",
    "acb": "ACB",
    "vi pi banh": "VPBank",
    "vi pi bank": "VPBank",
    "vê pê banh": "VPBank",
    "vê pê bê": "VPBank",
    "vp bank": "VPBank",
    "vpbank": "VPBank",
    "ti pi banh": "TPBank",
    "ti pi bank": "TPBank",
    "tê pê banh": "TPBank",
    "tê pê bê": "TPBank",
    "tp bank": "TPBank",
    "tpbank": "TPBank",
    "sa com banh": "Sacombank",
    "sa com bank": "Sacombank",
    "xà com banh": "Sacombank",
    "sacombank": "Sacombank",
    "hát đê banh": "HDBank",
    "hát đê bank": "HDBank",
    "hd bank": "HDBank",
    "hdbank": "HDBank",
    "vi ai bi": "VIB",
    "vê i bê": "VIB",
    "vib": "VIB",
    "ô xê bê": "OCB",
    "ô sê bê": "OCB",
    "ocb": "OCB",
    "em ét bê": "MSB",
    "mờ ét bê": "MSB",
    "msb": "MSB",
    "ét hát bê": "SHB",
    "shb": "SHB",
    "lờ pê banh": "LPBank",
    "lờ pê bank": "LPBank",
    "lp bank": "LPBank",
    "lpbank": "LPBank",
    "bưu điện liên việt": "LPBank",
    "liên việt postbank": "LPBank",
    "liên việt post bank": "LPBank",
    "si banh": "SeABank",
    "sea bank": "SeABank",
    "seabank": "SeABank",
    "ê xim banh": "Eximbank",
    "ê xim bank": "Eximbank",
    "eximbank": "Eximbank",
    "a bê banh": "ABBank",
    "a bê bank": "ABBank",
    "abbank": "ABBank",
    "bê vê banh": "BVBank",
    "bê vê bank": "BVBank",
    "bvbank": "BVBank",
    "nam á banh": "Nam A Bank",
    "nam á bank": "Nam A Bank",
    "nam a bank": "Nam A Bank",
    "bắc á banh": "Bac A Bank",
    "bắc á bank": "Bac A Bank",
    "bac a bank": "Bac A Bank",
    "đông á banh": "DongA Bank",
    "đông á bank": "DongA Bank",
    "donga bank": "DongA Bank",
    "kiên long banh": "KienlongBank",
    "kiên long bank": "KienlongBank",
    "kienlongbank": "KienlongBank",
    "việt á banh": "VietABank",
    "việt á bank": "VietABank",
    "vietabank": "VietABank",
    "bảo việt banh": "BaoViet Bank",
    "bảo việt bank": "BaoViet Bank",
    "baoviet bank": "BaoViet Bank",
    "en xê bê": "NCB",
    "nờ xê bê": "NCB",
    "ncb": "NCB",
    "pi gi banh": "PGBank",
    "pi gi bank": "PGBank",
    "pê gờ banh": "PGBank",
    "pg bank": "PGBank",
    "pgbank": "PGBank",
    "sài gòn banh": "Saigonbank",
    "sài gòn bank": "Saigonbank",
    "saigonbank": "Saigonbank",
    "việt banh": "VietBank",
    "việt bank": "VietBank",
    "vietbank": "VietBank",
    # Foreign banks in VN
    "shin han banh": "Shinhan Bank",
    "shin han bank": "Shinhan Bank",
    "xin han banh": "Shinhan Bank",
    "shinhan bank": "Shinhan Bank",
    "shinhan": "Shinhan Bank",
    "hát ét bê xê": "HSBC",
    "hsbc": "HSBC",
    "u ô bê": "UOB",
    "iu ô bi": "UOB",
    "uob": "UOB",
    "gu ri banh": "Woori Bank",
    "u ri banh": "Woori Bank",
    "woori bank": "Woori Bank",
    "woori": "Woori Bank",
    "xờ tan đát chát tơ": "Standard Chartered",
    "standard chartered": "Standard Chartered",
    # E-wallets & Digital Banks
    "ví mô mô": "MoMo",
    "mô mô": "MoMo",
    "mơ mơ": "MoMo",
    "momo": "MoMo",
    "da lô pây": "ZaloPay",
    "za lô pây": "ZaloPay",
    "zalo pay": "ZaloPay",
    "zalopay": "ZaloPay",
    "vê en pây": "VNPay",
    "vi en pây": "VNPay",
    "vn pay": "VNPay",
    "vnpay": "VNPay",
    "ti mô": "Timo",
    "timo": "Timo",
    "kếch bai vi pi banh": "Cake by VPBank",
    "cake by vpbank": "Cake by VPBank",
    "ngân hàng số cake": "Cake by VPBank",
    "ngân hàng cake": "Cake by VPBank",
    "li ô banh": "Liobank",
    "li ô bank": "Liobank",
    "liobank": "Liobank",
}

# Everyday Vietnamese phrases that mean banks ONLY in financial/banking context
CONTEXTUAL_BANK_VARIANTS: dict[str, str] = {
    "ngoại thương": "Vietcombank",
    "kỹ thương": "Techcombank",
    "đầu tư phát triển": "BIDV",
    "quân đội": "MB Bank",
    "em bi": "MB Bank",
    "công thương": "VietinBank",
    "nông nghiệp": "Agribank",
    "á châu": "ACB",
    "thịnh vượng": "VPBank",
    "tiên phong": "TPBank",
    "sài gòn thương tín": "Sacombank",
    "quốc tế": "VIB",
    "phương đông": "OCB",
    "hàng hải": "MSB",
    "sài gòn hà nội": "SHB",
    "lộc phát": "LPBank",
    "đông nam á": "SeABank",
    "xi banh": "SeABank",
    "xuất nhập khẩu": "Eximbank",
    "an bình": "ABBank",
    "bản việt": "BVBank",
    "nam á": "Nam A Bank",
    "bắc á": "Bac A Bank",
    "đông á": "DongA Bank",
    "kiên long": "KienlongBank",
    "việt á": "VietABank",
    "bảo việt": "BaoViet Bank",
    "quốc dân": "NCB",
    "việt nam thương tín": "VietBank",
    "kếch": "Cake by VPBank",
    "cake": "Cake by VPBank",
}

CANONICAL_BANK_CASING: dict[str, str] = {
    v.lower(): v
    for v in (*UNAMBIGUOUS_BANK_VARIANTS.values(), *CONTEXTUAL_BANK_VARIANTS.values())
}

_UNAMBIGUOUS_BANK_RE = re.compile(
    r"(?<!\w)("
    + "|".join(re.escape(k) for k in sorted(UNAMBIGUOUS_BANK_VARIANTS, key=len, reverse=True))
    + r")(?!\w)",
    re.IGNORECASE,
)

_BANK_LEFT_CTX = (
    r"\b(?:ngân\s+hàng(?:\s+số)?|nh|tài\s+khoản|stk|thẻ|ví|chuyển(?:\s+khoản)?|"
    r"bắn(?:\s+tiền)?|vào|qua|bằng|tới|sang|bên)"
)
_CONTEXTUAL_BANK_RE = re.compile(
    rf"(?:(?P<left>{_BANK_LEFT_CTX})\s+)?(?<!\w)("
    + "|".join(re.escape(k) for k in sorted(CONTEXTUAL_BANK_VARIANTS, key=len, reverse=True))
    + r")(?!\w)(?:\s+(?P<right>bank|banh|\d{6,})\b)?",
    re.IGNORECASE,
)

DIGIT_WORDS = {
    "không": 0, "zezo": 0, "zêrô": 0,
    "một": 1, "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4, "tư": 4,
    "năm": 5, "lăm": 5, "nhăm": 5,
    "sáu": 6,
    "bảy": 7, "bẩy": 7,
    "tám": 8,
    "chín": 9,
}

SCALE_WORDS = {"mươi", "chục", "trăm", "nghìn", "ngàn", "triệu", "tỷ", "tỉ", "k"}
ALL_NUM_TOKENS = set(DIGIT_WORDS.keys()) | SCALE_WORDS | {"mười", "linh", "lẻ", "rưỡi"}

SLANG_MULTIPLIERS = {
    "củ": 1_000_000,
    "chai": 1_000_000,
    "lít": 100_000,
    "lốp": 100_000,
    "chục": 10_000,
    "cành": 1_000,
    "ca": 1_000,
    "k": 1_000,
}


def normalize_vietnamese_banks(text: str) -> str:
    """Normalize Vietnamese bank names and ASR phonetic variants into canonical names."""
    if not text:
        return text

    res = _UNAMBIGUOUS_BANK_RE.sub(
        lambda m: UNAMBIGUOUS_BANK_VARIANTS[m.group(1).lower()],
        text,
    )

    def _replace_contextual(match: re.Match) -> str:
        left = match.group("left")
        phrase = match.group(2)
        right = match.group("right")
        if not left and not right:
            return match.group(0)
        canonical = CONTEXTUAL_BANK_VARIANTS[phrase.lower()]
        if left:
            # Drop redundant generic "ngân hàng" prefix if followed by bank suffix, keep prepositions
            return f"{left} {canonical}"
        return canonical

    res = _CONTEXTUAL_BANK_RE.sub(_replace_contextual, res)
    return res


def _parse_small_number(words: list[str]) -> int | None:
    """Parse Vietnamese number words up to 999."""
    total = 0
    current = 0
    i = 0
    n = len(words)
    while i < n:
        w = words[i].lower()
        if w in ("linh", "lẻ"):
            i += 1
            if i < n and words[i].lower() in DIGIT_WORDS:
                total += DIGIT_WORDS[words[i].lower()]
            i += 1
            continue
        if w == "trăm":
            if current == 0:
                current = 1
            total += current * 100
            current = 0
        elif w in ("mươi", "chục"):
            if current == 0:
                current = 1
            total += current * 10
            current = 0
        elif w == "mười":
            total += 10
            current = 0
        elif w in DIGIT_WORDS:
            val = DIGIT_WORDS[w]
            if i + 1 < n and words[i + 1].lower() in ("mươi", "chục", "trăm"):
                current = val
            elif current != 0 and w in ("mốt", "lăm", "nhăm"):
                total += val
                current = 0
            else:
                total += val
        elif w.isdigit():
            total += int(w)
        i += 1
    return total + current


def words_to_number(text: str) -> int | None:
    """Convert Vietnamese compound number words (e.g. 'một trăm năm mươi nghìn') to integer."""
    words = text.lower().strip().split()
    if not words:
        return None
    if len(words) == 1 and words[0] in DIGIT_WORDS:
        return DIGIT_WORDS[words[0]]

    total = 0
    current_segment: list[str] = []

    for w in words:
        if w in ("tỷ", "tỉ"):
            seg = _parse_small_number(current_segment) if current_segment else 1
            total += (seg if seg is not None else 1) * 1_000_000_000
            current_segment = []
        elif w == "triệu":
            seg = _parse_small_number(current_segment) if current_segment else 1
            total += (seg if seg is not None else 1) * 1_000_000
            current_segment = []
        elif w in ("nghìn", "ngàn", "k"):
            seg = _parse_small_number(current_segment) if current_segment else 1
            total += (seg if seg is not None else 1) * 1_000
            current_segment = []
        elif w == "rưỡi":
            if total >= 1_000_000_000:
                total += 500_000_000
            elif total >= 1_000_000:
                total += 500_000
            elif total >= 1_000:
                total += 500
        else:
            current_segment.append(w)

    if current_segment:
        remaining = _parse_small_number(current_segment)
        if remaining is not None:
            if total >= 1_000_000 and remaining < 10:
                total += remaining * 100_000
            elif total >= 1_000 and remaining < 10:
                total += remaining * 100
            else:
                total += remaining

    return total if total > 0 or "không" in words else None


def normalize_phone_numbers(text: str) -> str:
    """Normalize spoken phone/account digit sequences starting with 'không'/'0'."""
    digit_map = {k: str(v) for k, v in DIGIT_WORDS.items()}

    def _replace_phone(match: re.Match) -> str:
        raw = match.group(0)
        tokens = raw.lower().split()
        digits = []
        for t in tokens:
            if t in digit_map:
                digits.append(digit_map[t])
            elif t.isdigit():
                digits.append(t)
            else:
                return raw
        phone_str = "".join(digits)
        if 9 <= len(phone_str) <= 16 and phone_str.startswith("0"):
            return phone_str
        return raw

    pattern = re.compile(
        r"\b(?:không|0)(?:\s+(?:không|một|hai|ba|bốn|năm|sáu|bảy|bẩy|tám|chín|tư|lăm|mốt|nhăm|\d)){8,15}\b",
        re.IGNORECASE,
    )
    return pattern.sub(_replace_phone, text)


def normalize_financial_slang(text: str) -> str:
    """Normalize Vietnamese currency slang (củ, chai, lít, lốp, cành, ca, chục, k) before standard ITN."""
    num_phrase = (
        r"(?:\d+(?:[.,]\d+)?|"
        r"(?:một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|tám|chín|mười|linh|lẻ|mươi|trăm)"
        r"(?:\s+(?:một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|tám|chín|mười|linh|lẻ|mươi|trăm|chục))*)"
    )
    slang_pattern = re.compile(
        rf"\b({num_phrase})\s*(củ|chai|lít|lốp|cành|ca|k)\b(?:\s+(rưỡi))?",
        re.IGNORECASE,
    )

    def _replace_slang(match: re.Match) -> str:
        qty_raw = match.group(1).strip().lower()
        unit = match.group(2).strip().lower()
        has_ruoi = bool(match.group(3))

        # Protect common non-currency words like 'ca sáng', 'ca tối', 'ca trực'
        if unit == "ca":
            after = text[match.end() :].lstrip().lower()
            if after.startswith(("sáng", "trưa", "chiều", "tối", "đêm", "trực", "làm", "hát")):
                return match.group(0)

        if re.fullmatch(r"\d+(?:[.,]\d+)?", qty_raw):
            qty = float(qty_raw.replace(",", "."))
        else:
            parsed = _parse_small_number(qty_raw.split())
            if parsed is None or parsed == 0:
                return match.group(0)
            qty = float(parsed)

        if has_ruoi:
            qty += 0.5

        mult = SLANG_MULTIPLIERS[unit]
        val = int(round(qty * mult))
        return str(val)

    chuc_pattern = re.compile(
        rf"\b({num_phrase})\s+chục(?:\s+(rưỡi))?(?=\s*(?:đồng|tiền|vnd|$|[.,!?]))",
        re.IGNORECASE,
    )

    def _replace_chuc(match: re.Match) -> str:
        qty_raw = match.group(1).strip().lower()
        has_ruoi = bool(match.group(2))
        if re.fullmatch(r"\d+(?:[.,]\d+)?", qty_raw):
            qty = float(qty_raw.replace(",", "."))
        else:
            parsed = _parse_small_number(qty_raw.split())
            if parsed is None or parsed == 0:
                return match.group(0)
            qty = float(parsed)
        if has_ruoi:
            qty += 0.5
        return str(int(round(qty * 10_000)))

    res = slang_pattern.sub(_replace_slang, text)
    res = chuc_pattern.sub(_replace_chuc, res)
    return res


def normalize_currency_and_amounts(text: str) -> str:
    """Convert standard Vietnamese compound number phrases (nghìn, ngàn, triệu, tỷ) to digits."""
    tokens = re.findall(r"[\wà-ỹ]+|[^\w\s]", text, re.UNICODE)
    if not tokens:
        return text

    out_tokens: list[str] = []
    i = 0
    n = len(tokens)

    while i < n:
        tok_lower = tokens[i].lower()
        if tok_lower in ALL_NUM_TOKENS or tokens[i].isdigit():
            j = i
            has_scale = False
            span_words = []
            while j < n and (tokens[j].lower() in ALL_NUM_TOKENS or tokens[j].isdigit()):
                if tokens[j].lower() in SCALE_WORDS:
                    has_scale = True
                span_words.append(tokens[j])
                j += 1

            if has_scale or len(span_words) >= 2:
                num_val = words_to_number(" ".join(span_words))
                if num_val is not None:
                    suffix = ""
                    if j < n and tokens[j].lower() in ("đồng", "vnd"):
                        suffix = " " + tokens[j]
                        j += 1
                    out_tokens.append(f"{num_val}{suffix}")
                    i = j
                    continue

        out_tokens.append(tokens[i])
        i += 1

    res = ""
    for idx, tok in enumerate(out_tokens):
        if idx > 0 and not re.match(r"[.,!?;:)]", tok) and not res.endswith("("):
            res += " "
        res += tok
    return res


def restore_casing(text: str) -> str:
    """Restore sentence casing while keeping fintech acronyms and canonical bank names."""
    text = text.strip()
    if not text:
        return text

    is_all_upper = text.isupper()
    words = text.split()
    normalized = []
    for w in words:
        w_clean = re.sub(r"[^\w]", "", w).upper()
        if w_clean in ACRONYMS:
            normalized.append(w.upper() if is_all_upper else re.sub(r"[A-Za-zÀ-ỹ]+", w_clean, w, count=1))
        elif is_all_upper:
            normalized.append(w.lower())
        else:
            normalized.append(w)
    text = " ".join(normalized)

    # Restore exact mixed casing for canonical multi-word or single-word bank names
    bank_casing_re = re.compile(
        r"(?<!\w)("
        + "|".join(re.escape(k) for k in sorted(CANONICAL_BANK_CASING, key=len, reverse=True))
        + r")(?!\w)",
        re.IGNORECASE,
    )
    text = bank_casing_re.sub(lambda m: CANONICAL_BANK_CASING[m.group(1).lower()], text)
    text = re.sub(r"(?:^|[.!?]\s+)([a-zà-ỹ])", lambda m: m.group(0).upper(), text)
    return text


def normalize_vietnamese_financial_itn(text: str) -> str:
    """Full Vietnamese Financial ITN pipeline for Gipformer ASR outputs."""
    if not text or not text.strip():
        return ""
    cleaned = text.strip()
    if cleaned.isupper():
        cleaned = " ".join(
            w if re.sub(r"[^\w]", "", w).upper() in ACRONYMS else w.lower()
            for w in cleaned.split()
        )
    res = normalize_phone_numbers(cleaned)
    res = normalize_vietnamese_banks(res)
    res = normalize_financial_slang(res)
    res = normalize_currency_and_amounts(res)
    res = restore_casing(res)
    return res
