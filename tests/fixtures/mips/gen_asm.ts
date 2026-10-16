// Generates mips-assembler reference outputs for hand-written programs.
import { assemble } from "mips-assembler";

const progs: { name: string, asm: string | string[], opts?: any, bufLen?: number }[] = [
  { name: "readme", asm: `
  .org 0x80050000
  .definelabel ExternalPtr,0x8033C000
  .definelabel ExternalLibFn,0x80104321
  ADDIU SP SP 0xFFE0
  SW RA 0x18(SP)
  loop:
  LUI A0 hi(ExternalPtr)
  JAL ExternalLibFn
  ADDIU A0 A0 lo(ExternalPtr)
  BEQ V0 R0 loop
  NOP
  LW RA 0x18(SP)
  JR RA` },
  { name: "labels", asm: `
main:
main2: start: ADDIU SP SP -32
loop?!: JAL 0x80023456
excited!Label!: nop
12345: nop
!?!: j loop?!
  beq a0 a1 12345
  bne a0, a1, main2
  bnel a0 r0 start
  b loop` },
  { name: "local", asm: `
.org 0x80001000
Global1:
@@loc: nop
  beq a0 a0 @@loc
  nop
Global2:
@@loc: addiu a0 a0 1
  bne a0 r0 @@loc
  j @@loc
@@after: nop
  b @@after` },
  { name: "local_error", asm: `@@loc: nop` },
  { name: "local_ref_error", asm: `j @@loc` },
  { name: "statics", asm: `
.org 0x80002000
.beginfile
@stat: nop
  j @stat
.endfile
.beginfile
@stat: nop
  nop
  j @stat
.endfile
  .word org()` },
  { name: "include", asm: `
.org 0x80001000
.include "external"
  .include "external"
  jal fn
`, opts: { files: { external: `
  @s: ADDIU A0 R0 123
  .ascii "This is the external 'file'"
  .align 4
  j @s
`, other: "fn: jr ra\nnop" } } },
  { name: "include_missing", asm: `.include "nothere"`, opts: { files: {} } },
  { name: "include_nonstr", asm: `.include 5`, opts: { files: {} } },
  { name: "beginfile_unclosed", asm: `.beginfile\nnop` },
  { name: "endfile_extra", asm: `nop\n.endfile\n@x: nop` },
  { name: "data", asm: `
.org 0x80000000
label1: .word 0x12345678, -1, label1, 4294967295, 0x1FFFFFFFF
.halfword 0x1234 -2 0xFFFF 65536
.dh 1
.byte 1, 2, -3, 255 256
.db 0x7F
.dw 7
.align 4
.float 1.5, 2, -0.25, 3
.ascii "abc", 0x0A, 'xy', "q\\"uote"
.asciiz "zero\\tterm\\n\\x41\\x4A4\\101\\7\\18"
.align 8
.fill 3
.fill 2, 0xAB
.fill 1 -1
.skip 2
.align 16
.word org()
end:` },
  { name: "float_text", asm: `.float 1.5 2.25`, opts: { text: true } },
  { name: "orga", asm: `
.org 0x80000000
.orga 0x10
nop
addiu a0 a0 1
.orga 4
jr ra
.word end
end:`, bufLen: 0x20 },
  { name: "orga_small_buffer", asm: `.orga 0x100\nnop`, bufLen: 8 },
  { name: "if", asm: `
.definelabel ONE,1
.definelabel ZERO,0
.if ONE
  addiu a0 r0 1
.else
  addiu a0 r0 2
.endif
.if ZERO
  addiu a0 r0 3
.elseif 0
  addiu a0 r0 4
.elseif 1
  addiu a0 r0 5
.elseif 1
  addiu a0 r0 6
.else
  addiu a0 r0 7
.endif
.if 0
  .if 1
    addiu a0 r0 8
  .endif
  bogus instruction here
.else
  .if 1
    addiu a0 r0 9
  .else
    addiu a0 r0 10
  .endif
.endif
.if later
  nop
.endif
later: nop` },
  { name: "if_unclosed", asm: `.if 1\nnop` },
  { name: "if_noarg", asm: `.if\nnop\n.endif` },
  { name: "if_str", asm: `.if "a"\nnop\n.endif` },
  { name: "else_twice", asm: `.if 1\n.else\n.else\n.endif` },
  { name: "elseif_after_else", asm: `.if 1\n.else\n.elseif 1\n.endif` },
  { name: "endif_alone", asm: `.endif` },
  { name: "else_alone", asm: `.else` },
  { name: "if_two", asm: `.if 1 2\n.endif` },
  { name: "equ", asm: `
NumList equ 1,2,3,4
Reg equ A0
Empty equ
@Stat equ 5
.word NumList
addiu Reg Reg 4
.word @Stat
.word 9 Empty` },
  { name: "macros", asm: `
.org 0x80000000
start:
li a0, 0
li a0, -32768
li a0, 32767
li a0, 32768
li a0, 65535
li a0, 65536
li a0, 0x80000000
li a0, 0x80008000
li a0, 0x12345678
li a0, -40000
li a0, -65536
li a0, 0xFFFEFFFF
li a0, 0x8000FFFF
li a0, label_later
li v0, start
move a0, a1
beqz a0, start
bnez a0, label_later
bnezl a0 label_later
label_later: jr ra` },
  { name: "li_range", asm: `li a0 0xFFFF8000` },
  { name: "li_str", asm: `x equ "a"\nli a0 "s"` },
  { name: "li_one", asm: `li a0` },
  { name: "move_bad", asm: `move a0` },
  { name: "fns", asm: `
.org 0x80000000
.definelabel big,0x8034ABCD
.definelabel neg,-5
lui a0 hi(big)
addiu a0 a0 lo(big)
lw a1 lo(big)(a0)
lw a1 lo(0x8000)(a0)
addiu a0 r0 abs(neg)
addiu a0 r0 abs(-0x10)
.word org()
.word org(), hi(0xFFFF8000), lo(-1)
lui a0 hi(0x12347FFF)
lw a0 0x18(sp)
sw a0 -0x8(SP)
lw a0, 4 (a1)
addiu a0 r0 HI(big)` },
  { name: "fn_str", asm: `addiu a0 r0 hi("s")` },
  { name: "fn_bad", asm: `addiu a0 r0 hi(unknownlabel)` },
  { name: "comments", asm: `
nop ; comment
nop // other
/* block */ nop /* inline */
/* multi
line */ addiu a0 a0 1
.ascii "semi;colon // slashes /* not */"
.asciiz 'it''s', "a;b"
addiu a0 a0 2 /* trailing
still */ nop
nop ; /* start of block in comment
nop` },
  { name: "unclosed_block", asm: `nop /* never closed\nnop` },
  { name: "array_input", asm: ["  nop", "addiu a0 a0 1 ; c", "", "x: j x", 5 as any, "jr ra"] },
  { name: "text", asm: `
.org 0x80000000
x: addiu a0, a0, x
lw a0, lo(x)(a1)
beq a0 r0 x
.word 1
j x`, opts: { text: true } },
  { name: "syms", asm: `
.org 0x80000000
a1abel: nop
.word 5
datalabel: .word 1
.definelabel defined,0x80001234
e equ 5
last:`, opts: { symbolOutputMap: {} } },
  { name: "misaligned", asm: `.org 0x80000000\nbeq a0 a0 0x80000002` },
  { name: "bad_inst", asm: `nop\nfoo a0 a1\nnop` },
  { name: "bad_operand", asm: `addiu a0 a0 notalabel` },
  { name: "parens", asm: `lw a0 (0x10)(a1)` },
  { name: "imbalanced", asm: `lw a0 0x10(a1))` },
  { name: "imbalanced2", asm: `lw a0 0x10((a1)` },
  { name: "unterminated", asm: `.ascii "abc` },
  { name: "hex_escape_bad", asm: `.ascii "\\xZZ"` },
  { name: "align_bad", asm: `.align 3` },
  { name: "align_neg", asm: `.align -4` },
  { name: "align_zero", asm: `nop\n.byte 1\n.align 0\n.byte 2` },
  { name: "align_args", asm: `.align 4 8` },
  { name: "align_str", asm: `.align "x"` },
  { name: "org_neg", asm: `.org -1` },
  { name: "org_bad", asm: `.org foo` },
  { name: "orga_neg", asm: `.orga -1` },
  { name: "skip_neg", asm: `.skip -1` },
  { name: "fill_bad", asm: `.fill` },
  { name: "fill_bad2", asm: `.fill x` },
  { name: "fill_neg", asm: `.fill -1` },
  { name: "word_bad", asm: `.word foo` },
  { name: "byte_bad", asm: `.byte "x"` },
  { name: "halfword_bad", asm: `.halfword bar` },
  { name: "float_bad", asm: `.float bar` },
  { name: "definelabel_bad", asm: `.definelabel x,"s"` },
  { name: "definelabel_args", asm: `.definelabel x` },
  { name: "ascii_bad", asm: `.ascii zz` },
  { name: "byte_noargs", asm: `.byte` },
  { name: "bogus_directive", asm: `.bogus 1` },
  { name: "beginfile_args", asm: `.beginfile 1` },
  { name: "case", asm: `.ORG 0x80000000\nX: ADDIU A0 A0 1\n.WORD X\n.Align 8\nLI A0 0x12345\nJ X` },
  { name: "tabs", asm: `\tnop\n\taddiu\ta0,\ta0,\t1\nlbl:\tj\tlbl` },
  { name: "fpu", asm: `
.org 0x80000000
x: lwc1 f0, 0x10(a0)
c.eq.s f0 f2
bc1t x
bc1f 1 x
add.s f0 f1 f2
cvt.d.w F4 F6
mfc1 v0 f12
mtc0 k0 12
eret
nop` },
  { name: "branches_all", asm: `
.org 0x80000000
t:
bgez a0 t
bgezal a0 t
bgezall a0 t
bgezl a0 t
bgtz a0 t
bgtzl a0 t
blez a0 t
blezl a0 t
bltz a0 t
bltzal a0 t
bltzall a0 t
bltzl a0 t
bne a0 a1 t
bnel a0 a1 t
beql a0 a1 t
bc1fl t
bc1tl t` },
  { name: "buffer_inplace", asm: `.orga 4\n.word 0xDEADBEEF\n.orga 12\nnop`, bufLen: 16 },
  { name: "symbol_area", asm: `
.org 0x80000000
.definelabel area2,0x80000008
first: nop
@@l: nop
nop
@@l: nop
j @@l` },

  { name: "labels_ok", asm: `
main:
main2: start: ADDIU SP SP -32
loop?!: JAL 0x80023456
excited!Label!: nop
12345: nop
!?!: j loop?!
  beq a0 a1 12345
  bne a0, a1, main2
  bnel a0 r0 start` },
  { name: "local_ok", asm: `
.org 0x80001000
Global1:
@@loc: nop
  beq a0 a0 @@loc
  nop
Global2:
@@loc: addiu a0 a0 1
  bne a0 r0 @@loc
  j @@loc
@@after: nop
  beq r0 r0 @@after` },
  { name: "include_ok", asm: `
.org 0x80001000
.include "external"
  .include "external"
.include "other"
  jal fn
`, opts: { files: { external: `
  @s: ADDIU A0 R0 123
  .ascii "This is the external 'file'"
  .align 4
  j @s
`, other: "fn: jr ra\nnop" } } },
  { name: "if_ok", asm: `
.definelabel ONE,1
.definelabel ZERO,0
.if ONE
  addiu a0 r0 1
.else
  addiu a0 r0 2
.endif
.if ZERO
  addiu a0 r0 3
.elseif 0
  addiu a0 r0 4
.elseif 1
  addiu a0 r0 5
.elseif 1
  addiu a0 r0 6
.else
  addiu a0 r0 7
.endif
.if 0
  .if 1
    addiu a0 r0 8
  .endif
  bogus instruction here
.else
  .if 1
    addiu a0 r0 9
  .else
    addiu a0 r0 10
  .endif
.endif
.IF 1
nop
.ENDIF` },
  { name: "fns_ok", asm: `
.org 0x80000000
.definelabel big,0x8034ABCD
.definelabel neg,-5
lui a0 hi(big)
addiu a0 a0 lo(big)
lw a1 lo(big)(a0)
lw a1 lo(0x8000)(a0)
addiu a0 r0 abs(neg)
addiu a0 r0 abs(-0x10)
.word org()
.word org(), hi(0xFFFF8000), lo(-1)
lui a0 hi(0x12347FFF)
lw a0 0x18(sp)
sw a0 -0x8(SP)
lw a0, 4 (a1)` },
  { name: "fpu_ok", asm: `
.org 0x80000000
x: lwc1 f0, 0x10(a0)
c.eq.s f0 f2
bc1t x
bc1f 1 x
add.s f0 f1 f2
cvt.d.w F4 F6
mfc1 v0 f12
mfc0 k0 12
eret
nop` },
  { name: "symbol_area_ok", asm: `
.org 0x80000000
.definelabel area2,0x80000008
first: nop
@@l: nop
nop
@@l: nop
beq r0 r0 @@l` },
  { name: "numbers_ok", asm: `
.word 10, 0x10, 0b101, 0o17, x10, b11, -0x10, 1F, 010, 0, -0, 0x7fffffff, 0xffffffff
addiu a0 a0 0B1
.word 0X10` },
  { name: "numbers_ok_text", asm: `addiu a0 a0 0xFFFFFFFFF\nori a0 a0 -1\nlui a0 -0x8000\nsll a0 a0 0x21\nj 0x7FFFFFFF\naddiu a0 a0 x10`, opts: { text: true } },
  { name: "equ_in_inst", asm: `R equ a0, a1\nV equ 0x10\naddu v0 R\naddiu a0 a0 V\nlw a0 V(sp)` },
  { name: "label_only_lines", asm: `a:\nb:\nc: d:\n.word a b c d` },
  { name: "org_function_text", asm: `.org 0x80000010\nj org()\nnop\naddiu a0 r0 lo(org())`, opts: { text: true } },
  { name: "nested_fn", asm: `.definelabel x,0x80001234\nlui a0 hi(lo(x))` },
  { name: "string_escapes", asm: `.ascii "\\q\\\\\\'\\?\\r\\b\\0\\00\\000\\0000"\n.ascii 'a"b'` },
  { name: "unicode_ascii", asm: `.ascii "\u00e9\u4e2d"` },
  { name: "numbers", asm: `
.word 10, 0x10, 0b101, 0o17, x10, b11, o7, -0x10, 1F, 010, -b1, 0, -0
addiu a0 a0 0B1
.word 0X10` },
];

function run(p: any) {
  const opts = Object.assign({}, p.opts || {});
  if (opts.symbolOutputMap) opts.symbolOutputMap = Object.create(null);
  if (p.bufLen) {
    const u = new Uint8Array(p.bufLen);
    for (let i = 0; i < u.length; i++) u[i] = (i * 37 + 11) & 0xFF;
    opts.buffer = u.buffer;
  }
  try {
    const r: any = assemble(p.asm, opts);
    const out: any = opts.text ? { text: r } : { hex: Buffer.from(new Uint8Array(r)).toString("hex") };
    if (opts.symbolOutputMap) out.syms = { ...opts.symbolOutputMap };
    if (p.bufLen) out.same = r === opts.buffer;
    return out;
  } catch (e: any) {
    return { error: String(e.message) };
  }
}
console.log(JSON.stringify(progs.map(p => ({ ...p, out: run(p) }))));
