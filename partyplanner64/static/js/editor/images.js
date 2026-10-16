// The images the board renderer draws (images.ts): loaded once, then the editor redraws.
import { IMG } from './constants.js';

const sources = {
  toadImg: 'editor/toad.png',
  mstarImg: 'editor/mstar.png',
  bowserImg: 'editor/bowser.png',
  koopaImg: 'editor/koopa.png',
  booImg: 'editor/boo.png',
  goombaImg: 'editor/goomba.png',
  eventImg: 'editor/event.png',
  eventErrorImg: 'editor/eventerrors.png',
  starImg: 'editor/star.png',
  bank2Img: 'editor/bank2.png',
  bank3Img: 'editor/bank.png',
  bankcoinImg: 'editor/bankcoin.png',
  itemShop2Img: 'editor/itemshop2.png',
  itemShop3Img: 'editor/itemshop.png',
  gateImg: 'editor/gate.png',

  spaceBowser: 'editor/spaces/bowser.png',
  spaceItem2: 'editor/spaces/item2.png',

  spaceBlue3: 'editor/spaces/blue3.png',
  spaceRed3: 'editor/spaces/red3.png',
  spaceHappening3: 'editor/spaces/happening3.png',
  spaceChance3: 'editor/spaces/chance3.png',
  spaceBowser3: 'editor/spaces/bowser3.png',
  spaceItem3: 'editor/spaces/item3.png',
  spaceBattle3: 'editor/spaces/battle3.png',
  spaceBank3: 'editor/spaces/bank3.png',
  spaceGameGuy3: 'editor/spaces/gameguy.png',

  spaceDuelBasic3: 'editor/spaces/basic3.png',
  spaceDuelPowerup3: 'editor/spaces/powerup3.png',
  spaceDuelReverse3: 'editor/spaces/reverse3.png',
  spaceGameGuyDuel3: 'editor/spaces/gameguyduel.png',
  spaceMiniGameDuel3: 'editor/spaces/minigameduel3.png',
  spaceHappeningDuel3: 'editor/spaces/happeningduel3.png',

  targetImg: 'events/target.png',
};

const images = {};
let loadedPromise = null;

/** Loads every image; resolves when all have loaded (or failed). */
export function preloadImages() {
  if (!loadedPromise) {
    loadedPromise = Promise.all(Object.entries(sources).map(([name, path]) => new Promise(resolve => {
      const img = new Image();
      img.onload = () => resolve();
      img.onerror = () => resolve();
      img.src = `${IMG}/${path}`;
      images[name] = img;
    })));
  }
  return loadedPromise;
}

/** An image by name (images.ts getImage). */
export function getImage(name) {
  return images[name];
}

/** Draws an image if it is loaded (a broken image would throw). */
export function drawImg(ctx, name, x, y) {
  const img = images[name];
  if (img && img.complete && img.naturalWidth) ctx.drawImage(img, x, y);
}
