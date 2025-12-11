# Ref: https://github.com/mattifestation/PIC_Bindshell/blob/master/PIC_Bindshell/AdjustStack.asm#L24    
ALIGN_STUB = r"""
    .globl AlignRSP
AlignRSP:
    push rsi
    mov  rsi, rsp
    and  rsp, -16
    sub  rsp, 0x20
    call main
    mov  rsp, rsi
    pop  rsi
    ret
"""

_META_PREFIXES = (
    ".file",
    ".ident",
    ".cfi_",
    ".loc",
    ".def",
    ".scl",
    ".type",
    ".endef",
    ".seh_",
    ".linkonce",
)

_ALIGN_PREFIXES = (
    ".p2align",
    ".align",
    ".balign",
)


def _should_drop_line(stripped: str) -> bool:
    if stripped.startswith(_META_PREFIXES):
        return True
    if stripped.startswith(".extern") or stripped.startswith("EXTERN"):
        return True
    if "__main" in stripped:
        return True
    if stripped.startswith(_ALIGN_PREFIXES):
        return True
    return False


def clean_asm_source(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    align_inserted = False

    for line in lines:
        stripped = line.lstrip()

        if _should_drop_line(stripped):
            continue

        if stripped.startswith(".section"):
            if ".rdata" in stripped or ".data" in stripped:
                line = "    .text"
            elif ".text$" in stripped or ".text.startup" in stripped:
                line = "    .text"

        if stripped.startswith(".data") or stripped.startswith(".rdata"):
            line = "    .text"

        if not align_inserted and (
            stripped.startswith(".text")
            or (stripped.startswith(".section") and ".text" in stripped)
        ):
            cleaned.append(line)
            cleaned.append(ALIGN_STUB)
            align_inserted = True
            continue

        cleaned.append(line)

    if not align_inserted:
        cleaned.append(ALIGN_STUB)

    return "\n".join(cleaned)
