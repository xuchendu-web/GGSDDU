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
    expect(home).toContain('无需输入，也不会采集');
  });
});
