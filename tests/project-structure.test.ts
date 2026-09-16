import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = resolve(import.meta.dirname, '..');

describe('微信原生工程结构', () => {
  it('declares pages whose TypeScript, WXML and WXSS files all exist', () => {
    const app = JSON.parse(readFileSync(resolve(root, 'miniprogram/app.json'), 'utf8'));
    for (const page of app.pages) {
      for (const extension of ['ts', 'wxml', 'wxss', 'json']) {
        expect(existsSync(resolve(root, `miniprogram/${page}.${extension}`)), `${page}.${extension}`).toBe(true);
      }
    }
  });

  it('uses TypeScript compiler plugin and cloud roots', () => {
    const config = JSON.parse(readFileSync(resolve(root, 'project.config.json'), 'utf8'));
    expect(config.miniprogramRoot).toBe('miniprogram/');
    expect(config.cloudfunctionRoot).toBe('cloudfunctions/');
    expect(config.setting.useCompilerPlugins).toContain('typescript');
  });

  it('does not expose an input for a user question', () => {
    const home = readFileSync(resolve(root, 'miniprogram/pages/index/index.wxml'), 'utf8');
    expect(home).not.toMatch(/<input|<textarea/);
    expect(home).toContain('放心，不用告诉我');
  });

  it('uses the playful share copy without old instructional branding', () => {
    const resultTs = readFileSync(resolve(root, 'miniprogram/pages/result/result.ts'), 'utf8');
    const resultWxml = readFileSync(resolve(root, 'miniprogram/pages/result/result.wxml'), 'utf8');
    expect(resultTs).toContain('没别的意思，这页有点像你');
    expect(resultTs).toContain('随手翻到这句，你看看');
    expect(resultWxml).toContain('发给那个懂的人');
    expect(`${resultTs}${resultWxml}`).not.toContain('投资反思卡');
  });
});
