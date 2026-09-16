import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { CARDS } from '../miniprogram/data/cards';

const target = resolve(import.meta.dirname, '../cloudfunctions/draw/cards.generated.json');
writeFileSync(target, `${JSON.stringify(CARDS, null, 2)}\n`, 'utf8');
console.log(`已同步 ${CARDS.length} 条内容到 ${target}`);
