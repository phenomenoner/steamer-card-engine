#!/usr/bin/env node
import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
function arg(name, fallback=null){const p=`--${name}=`; const h=process.argv.find(x=>x.startsWith(p)); if(h) return h.slice(p.length); const i=process.argv.indexOf(`--${name}`); return i>=0&&process.argv[i+1]?process.argv[i+1]:fallback;}
const url=arg('url','http://43.212.33.0/');
const out=resolve(arg('out','.state/screenshots/state.png'));
const metaOut=resolve(arg('meta',`${out}.json`));
const symbol=arg('symbol',null);
mkdirSync(dirname(out),{recursive:true}); mkdirSync(dirname(metaOut),{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1200},deviceScaleFactor:1});
const errors=[]; page.on('pageerror',e=>errors.push(String(e))); page.on('console',m=>{if(['error','warning'].includes(m.type())) errors.push(`${m.type()}: ${m.text()}`)});
const response=await page.goto(url,{waitUntil:'networkidle',timeout:45000});
if(symbol){ await page.locator('#observer-symbol-select').selectOption(symbol); await page.waitForTimeout(1200); }
await page.screenshot({path:out,fullPage:true});
const visibleText=await page.locator('body').innerText({timeout:5000}).catch(()=>'');
const selectedSymbol=await page.locator('#observer-symbol-select').inputValue().catch(()=>null);
const selectedDate=await page.locator('#observer-date-select').inputValue().catch(()=>null);
const selectedCard=await page.locator('#observer-strategy-select').inputValue().catch(()=>null);
const meta={url,out,captured_at:new Date().toISOString(),status:response?.status()??null,title:await page.title(),requested_symbol:symbol,selectedDate,selectedCard,selectedSymbol,visible_text_head:visibleText.slice(0,2500),console_errors:errors.slice(0,50)};
writeFileSync(metaOut,JSON.stringify(meta,null,2));
await browser.close();
console.log(JSON.stringify(meta,null,2));
