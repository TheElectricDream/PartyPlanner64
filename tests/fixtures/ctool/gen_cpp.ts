// Reference outputs of cpp.js and utils/c-preprocessor.ts for the Python port's tests.
import * as cpp from "../packages/lib/lib/cppjs/cppjs";
import { preprocess } from "../packages/lib/utils/c-preprocessor";

const inputs: string[] = [
  `\n#define PI 3.14159\n\nint main () {\n    cout << "Value of PI :" << PI << endl;\n    return 0;\n}\n`,
  `\n#define MIN(a,b) (((a)<(b)) ? a : b)\n\nint main () {\n    int i, j;\n    i = 100;\n    j = 30;\n    cout <<"The minimum is " << MIN(i, j) << endl;\n    return 0;\n}`,
  `#include "test.h"\n\nint main () {\n    return 0;\n}`,
  `#include <ultra64.h>\nvoid main() { u8 x = TRUE; s32 y = FALSE; void *p = NULL; }`,
  `#define STR(x) #x\n#define XSTR(x) STR(x)\n#define CAT(a, b) a ## b\n#define V 42\nchar *s = STR(hello   world);\nchar *t = XSTR(V);\nint CAT(foo, bar) = CAT(1, 2);\nint q = CAT(V, x);`,
  `#define A 1\n#if A\nyes\n#else\nno\n#endif\n#ifdef A\nyes2\n#endif\n#ifndef A\nno2\n#elif 1\nyes3\n#endif\n#if 0\n#if 1\nnested\n#endif\n#elif A == 1 && !defined(B)\nyes4\n#else\nno4\n#endif`,
  `#if 1/2\nhalf\n#endif\n#if 3 % 2 == 1 && (1 << 3) == 8 && ~0 == -1 && 010 == 8 && 0x10 == 16 && 10UL == 10\nmath\n#endif\n#if defined X || defined(Y) || UNDEFINED\nno\n#else\nelse\n#endif`,
  `/* block\n comment */ int a; // line comment\nint b = 1 + \\\n 2;\nchar *c = "// not a comment";\nchar d = '/';\n`,
  `#define EMPTY\n#define F() 5\n#define G(x) x EMPTY x\nint a = F();\nint b = G(1);\nint c = G();\n`,
  `#define REC REC + 1\nint x = REC;\n#define A B\n#define B A\nint y = A;\n`,
  `#define SQ(x) ((x)*(x))\n#define TWICE(f, v) f(f(v))\nint z = TWICE(SQ, 3);\nint w = SQ(SQ(2));\nint s = SQ("a,b");\n`,
  `#undef NOTHING\n#define X 1\n#undef X\nint x = X;\n#define X 2\n#define X 3\nint y = X;\n`,
  `#pragma once\n#warning hi\n#line 5\nint a;\n`,
  `#error This is bad`,
  `#if 1\nint unclosed;`,
  `#endif`,
  `#include "missing.h"\nint a;`,
  `#define F(a,b) a+b\nint x = F(1);\n`,
  `#define F(a) a\nint x = F(1;\n`,
  `#if "str"\n#endif`,
  `#if X = 1\n#endif`,
  `#if X++\n#endif`,
  `#if 1 +\n#endif`,
  `#define 1abc 2`,
  `#define F(x x\n`,
  `int main() {\n  #define LOCAL 7\n  return LOCAL;\n}`,
  `#define P(x) _Pragma("message") x\nint a = P(3);\n`,
  `#define HASH # ## #\nint a = HASH;\n#define J(a) a ## \nint b = J(1);\n`,
  `#define bull 1\n#if bull\nyes\n#endif\n#if defined( bull )\nspaced\n#endif`,
  `#define ADDR 0x800C\n#define CALL(fn, arg) fn(arg)\nvoid f() { CALL(PlaySound, ADDR); CALL( Foo ,  1 + 2 ); }\n`,
  `#define LONGNAME_MACRO 1\n#define LONG 2\nint a = LONGNAME_MACRO + LONG + LONGER;\n`,
  `#define S "a string with MACRO"\n#define MACRO 9\nchar *s = S; int m = MACRO; char *t = "MACRO";\n`,
  `\r\n#define X 1\r\nint x = X;\r\n`,
  `#if defined(A) == 0 && 5 > 3 ? 1 : 0\nternary\n#endif\n#if (2 + 3) * 4 == 20 && -1 < 0 && !0\nprec\n#endif`,
  ``,
  `   `,
  `#define X(a) [a]\nX(X(1))\nX((1,2))\nX("(")\n`,
  `#include <ultra64.h>\n#include "ultra64.h"\nint after;`,
  `#ifdef\n#endif`,
  `#if\n#endif`,
  `#else\n#endif`,
  `#define M 1\n#if M\n#define N 2\n#endif\nint v = N + M;\n#unknown directive\n`,
];

function runCpp(text: string) {
  const warns: string[] = [];
  const errors: string[] = [];
  let completed: string | null = null;
  try {
    const inst = cpp.create({
      include_func: (file, isGlobal, resumer) => {
        if (file === "test.h") resumer("int test = 0;");
        else if (file.toLowerCase() === "ultra64.h") resumer("#define TRUE 1\n#define FALSE 0\ntypedef int s32;");
        else resumer(null);
      },
      completion_func: (t) => { completed = t; },
      warn_func: (m) => { warns.push(m); },
      error_func: (m) => { errors.push(m); },
    });
    const ret = inst.run(text);
    return { ret, completed, warns, errors };
  } catch (e: any) {
    return { thrown: String(e), completed, warns, errors };
  }
}

(async () => {
  const cases: any[] = [];
  for (const text of inputs) {
    let pre: any;
    try { pre = { ok: await preprocess(text) }; } catch (e: any) { pre = { error: String(e) }; }
    cases.push({ text, cpp: runCpp(text), pre });
  }
  console.log(JSON.stringify(cases));
})();
