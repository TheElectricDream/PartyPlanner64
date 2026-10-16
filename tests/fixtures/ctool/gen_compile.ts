// Reference outputs of utils/c-compiler.ts for the Python port's tests.
import { compile } from "../packages/lib/utils/c-compiler";
import { getDefaultAdditionalBgCode } from "../packages/lib/events/additionalbg";
import { getDefaultGetAudioCode } from "../packages/lib/events/getaudiochoice";
import { EventCodeLanguage } from "../packages/lib/types";

const sources: string[] = [
  getDefaultAdditionalBgCode(EventCodeLanguage.C),
  getDefaultGetAudioCode(EventCodeLanguage.C),
  `#include <ultra64.h>
extern int GetPlayerStruct(int);
extern void ShowMessage(int, char *, int, int, int, int, int);
int x = 5;
float f = 1.5;
char *msg = "Hello";
static short arr[4] = { 1, 2, 3, 4 };
struct S { int a; char b; } s;
void main() {
  int i;
  for (i = 0; i < 4; i++) { x += GetPlayerStruct(i) * 3 + arr[i]; }
  f = f * x - 2.0f / f;
  if (f < 3.0f && f >= -1.0f) { x = (int)f; }
  s.a = x % 7; s.b = 'c';
  ShowMessage(-1, msg, 0, 0, 0, 0, 0);
  switch (x) { case 1: x = 2; break; case 5: x = 9; break; default: x = -x; }
  while (x > 0) x >>= 1;
  do { x ^= 0xFF; } while (x & 1);
}
`,
  `// PARAM: Number|coins
// PARAM: Space|target
void main() {
  int c = COINS_PARAM;
  unsigned int u = 0xFFFFFFFF;
  u = u / 3 + (u >> 4);
  c = c ? c * 2 : -1;
}`,
  `void main() { int x = ; }`,
  `void main() { undeclared_fn_var = 3; }`,
  `int main() { return "x"; `,
  `#error nope`,
  `#include "other.h"`,
  `float div(float a, float b) { return a / b; } float neg(float a) { return -a; } int cmp(float a, float b) { return a > b; } unsigned int fu(float x) { return (unsigned int)x; } float uf(unsigned int u) { return u; }`,
  `char *s = "\\x41\\n\\t\\"q\\"";`,
  `int a; int b[10]; int *p = &a; int main(void) { b[3] = *p; return sizeof(b); }`,
];

// In node, the Emscripten glue's exit() calls process.exit; in the browser it throws.
const realExit = process.exit;
(process as any).exit = (code: number) => { throw new Error("exit(" + code + ")"); };
(async () => {
  const cases: any[] = [];
  for (const source of sources) {
    try {
      cases.push({ source, ok: await compile(source) });
    } catch (e: any) {
      cases.push({ source, error: e instanceof Error ? e.message : String(e) });
    }
  }
  process.exit = realExit;
  console.log(JSON.stringify(cases));
})();
