#!/usr/bin/env node
/**
 * collab_memory_bridge.mjs
 * Sync events.jsonl → agentmemory. Reads new events since last cursor and saves as memories.
 * Usage: node collab_memory_bridge.mjs [base_dir]
 */
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, join } from 'path';

const AM_PKG = '/home/caohui/.local/share/mise/installs/node/latest/lib/node_modules/@agentmemory/agentmemory/dist/standalone.mjs';
const PROJECT = 'claude-codex-gemini-collab';

const baseDir = resolve(process.argv[2] || '.');
const collabDir = join(baseDir, '.collab');
const eventsFile = join(collabDir, 'events.jsonl');
const cursorFile = join(collabDir, 'memory_bridge_cursor');

if (!existsSync(eventsFile)) {
  console.error('No events.jsonl found at', eventsFile);
  process.exit(1);
}

const lastSynced = existsSync(cursorFile) ? parseInt(readFileSync(cursorFile, 'utf8').trim()) : 0;
const lines = readFileSync(eventsFile, 'utf8').trim().split('\n').filter(Boolean);
const newEvents = [];

for (const line of lines) {
  try {
    const ev = JSON.parse(line);
    if (typeof ev === 'object' && ev.id > lastSynced) newEvents.push(ev);
  } catch { /* skip malformed */ }
}

if (newEvents.length === 0) {
  console.log('No new events to sync.');
  process.exit(0);
}

const { handleToolCall } = await import(AM_PKG);
let maxId = lastSynced;

for (const ev of newEvents) {
  const content = `[${ev.type}] agent=${ev.agent} task=${ev.task_id || 'none'} summary="${ev.summary || ''}"`;
  const concepts = [ev.type, ev.agent, ev.task_id, ev.status].filter(Boolean).join(',');
  try {
    await handleToolCall('memory_save', { content, concepts, project: PROJECT, type: 'workflow' });
    if (ev.id > maxId) maxId = ev.id;
    console.log(`✓ Synced event #${ev.id}: ${ev.type}`);
  } catch (e) {
    console.error(`✗ Failed event #${ev.id}:`, e.message);
  }
}

writeFileSync(cursorFile, String(maxId));
console.log(`Done. Synced ${newEvents.length} events, cursor → ${maxId}`);
