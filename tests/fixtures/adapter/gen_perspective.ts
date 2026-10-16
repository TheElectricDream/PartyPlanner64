// Reference outputs for AdapterBase._applyPerspective / _reversePerspective.
import { getAdapter } from "../packages/lib/adapter/adapters";
import "../packages/lib/events/builtin/events.include";

let seed = 12345;
function rnd() {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
}

const bgs: any = {
  mp1: { game: 1, width: 960, height: 720, fov: 17, scaleFactor: 1, cameraEyePosX: 0, cameraEyePosY: 1355, cameraEyePosZ: 1780, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
  mp1b: { game: 1, width: 960, height: 720, fov: 15.5, scaleFactor: 1, cameraEyePosX: 12.5, cameraEyePosY: 1500, cameraEyePosZ: 1700.25, lookatPointX: 3, lookatPointY: -20, lookatPointZ: 7 },
  mp2: { game: 2, width: 1152, height: 864, fov: 3, scaleFactor: 0.1, cameraEyePosX: 0, cameraEyePosY: 1570, cameraEyePosZ: 1577, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
  mp3: { game: 3, width: 1152, height: 864, fov: 15, scaleFactor: 0.1, cameraEyePosX: 0, cameraEyePosY: 300, cameraEyePosZ: 300, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
  mp3duel: { game: 3, width: 896, height: 672, fov: 15, scaleFactor: 0.1, cameraEyePosX: 0, cameraEyePosY: 210, cameraEyePosZ: 210, lookatPointX: 0, lookatPointY: 0, lookatPointZ: 0 },
};

const out: any = {};
for (const name in bgs) {
  const { game, ...bg } = bgs[name];
  const spaces = [];
  for (let i = 0; i < 40; i++) {
    spaces.push({ x: Math.round(rnd() * bg.width), y: Math.round(rnd() * bg.height), z: 0, type: 1 });
  }
  // A few fractional ones, as in user boards.
  spaces.push({ x: 100.5, y: 200.25, z: 0, type: 1 });
  spaces.push({ x: bg.width / 2, y: bg.height / 2, type: 1 });
  const adapter = getAdapter(game, {})!;
  const board: any = { game, bg: { ...bg, src: "" }, spaces: JSON.parse(JSON.stringify(spaces)) };
  adapter._reversePerspective(board);
  const reversed = JSON.parse(JSON.stringify(board.spaces));
  adapter._applyPerspective(board);
  const roundtrip = JSON.parse(JSON.stringify(board.spaces));
  // Game coordinates as read from a board def (float32 values).
  const f32 = new Float32Array(1);
  const gameSpaces = reversed.map((s: any) => {
    const r = (v: number) => { f32[0] = v; return f32[0]; };
    return { x: r(s.x), y: r(s.y), z: r(s.z), type: 1 };
  });
  const board2: any = { game, bg: { ...bg, src: "" }, spaces: JSON.parse(JSON.stringify(gameSpaces)) };
  adapter._applyPerspective(board2);
  const coords = adapter.onGetGameCoordsFromBoardCoords(10, 20, 0, board2);
  out[name] = { game, bg, spaces, reversed, roundtrip, gameSpaces, applied: board2.spaces, coords };
}
console.log(JSON.stringify(out));
