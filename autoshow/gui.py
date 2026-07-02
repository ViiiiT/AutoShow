from __future__ import annotations

import argparse
import array
import json
import math
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg"}
TRACK_NUMBER_PREFIX = re.compile(r"^\d{2}\s+")
EDGE_ANALYSIS_SAMPLE_RATE = 8000
EDGE_ANALYSIS_WINDOW_SECONDS = 0.01
_MEDIA_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], list[dict]]] = {}
_RENDER_TASKS: dict[str, dict] = {}
_RENDER_TASKS_LOCK = threading.Lock()


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AutoShow</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d7dde5;
      --text: #17202e;
      --muted: #667085;
      --accent: #0f766e;
      --accent-soft: #e7f3f1;
      --focus: #134e4a;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .app {
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr);
      min-height: 100vh;
    }

    .sidebar {
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 18px 14px;
    }

    .brand {
      margin: 0 8px 18px;
      font-size: 22px;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .nav {
      display: grid;
      gap: 6px;
    }

    .nav button {
      width: 100%;
      height: 40px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      text-align: left;
      padding: 0 12px;
    }

    .nav button.active {
      background: var(--accent-soft);
      border-color: #a8d8d2;
      color: var(--focus);
    }

    .workspace {
      min-width: 0;
      padding: 30px 28px;
    }

    .sequence-layout {
      display: grid;
      grid-template-columns: minmax(520px, 1.25fr) minmax(420px, .75fr);
      gap: 24px;
      align-items: start;
    }

    .sequence-main {
      min-width: 0;
    }

    .utility-panel {
      min-height: calc(100vh - 68px);
      border-left: 1px solid var(--line);
      padding-left: 22px;
    }

    .utility-title {
      margin: 0 0 12px;
      color: var(--muted);
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0;
    }

    .group-task-list {
      display: grid;
      gap: 12px;
    }

    .group-task-card {
      border: 1px dashed var(--line);
      border-radius: 8px;
      min-height: 120px;
      background: #fbfcfe;
      overflow: hidden;
    }

    .group-task-card.warning {
      background: #fff1f0;
      border-color: #f1b8b3;
    }

    .group-task-head {
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      align-items: end;
      padding: 12px;
      padding-right: 46px;
      border-bottom: 1px dashed var(--line);
      background: #fff;
    }

    .group-task-head select,
    .group-task-head input {
      height: 34px;
      font-size: 14px;
    }

    .group-task-top {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      grid-column: 1 / -1;
    }

    .group-task-trigger,
    .group-task-interrupt {
      min-width: 0;
    }

    .group-task-trigger-index.hidden {
      display: none;
    }

    .group-task-time.hidden {
      display: none;
    }

    .group-task-trigger-index,
    .group-task-time-row {
      grid-column: 1 / -1;
    }

    .group-task-time-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .group-task-time-row.hidden {
      display: none;
    }

    .group-task-max-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      grid-column: 1 / -1;
    }

    .group-task-max-row.hidden {
      display: none;
    }

    .group-task-body {
      display: grid;
      gap: 8px;
      min-height: 72px;
      padding: 12px;
    }

    .group-task-body.hidden {
      display: none;
    }

    .group-task-remove {
      position: absolute;
      top: 12px;
      right: 12px;
    }

    .group-task-item-row {
      position: relative;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      align-items: end;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 10px;
      padding-right: 44px;
      cursor: grab;
    }

    .group-task-item-remove {
      position: absolute;
      top: 10px;
      right: 8px;
    }

    .group-task-item-row.dragging {
      opacity: .55;
      cursor: grabbing;
    }

    .group-task-item-row select,
    .group-task-item-row input {
      height: 34px;
      font-size: 14px;
    }

    .group-task-item-wide {
      grid-column: 1 / -1;
    }

    .group-task-random-quantity {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .group-task-item-hidden {
      display: none;
    }

    .pane {
      display: none;
      width: 100%;
    }

    .pane.active {
      display: block;
    }

    #start {
      max-width: 760px;
    }

    #sequence {
      max-width: 1380px;
    }

    h2 {
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
    }

    .lead {
      margin: 0 0 28px;
      color: var(--muted);
      font-size: 15px;
    }

    .field {
      max-width: 360px;
      margin-bottom: 18px;
    }

    label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-weight: 700;
    }

    input {
      width: 100%;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 12px;
      color: var(--text);
      background: #fff;
      font: inherit;
      font-size: 16px;
    }

    input:focus {
      outline: 2px solid #bfe5df;
      border-color: var(--accent);
    }

    .button-row {
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 18px;
    }

    .button-row.compact {
      margin-top: 0;
    }

    .inline-setting {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-weight: 700;
      white-space: nowrap;
    }

    .inline-setting label {
      margin: 0;
    }

    .inline-setting input {
      width: 72px;
      height: 38px;
      font-size: 14px;
    }

    .config-controls {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px 18px;
      margin: 0 0 16px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .config-controls label {
      margin: 0;
    }

    .config-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      color: var(--text);
      font-weight: 800;
      white-space: nowrap;
    }

    .config-toggle-group {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
    }

    .config-toggle input {
      width: 16px;
      height: 16px;
      padding: 0;
    }

    .config-field {
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .config-field label {
      color: var(--muted);
      font-weight: 800;
      white-space: nowrap;
    }

    .config-field select,
    .config-field input {
      min-width: 0;
      width: 100%;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      font-size: 14px;
      padding: 0 8px;
    }

    .render-panel {
      display: grid;
      gap: 14px;
      max-width: 900px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .progress-track {
      height: 18px;
      border-radius: 999px;
      background: #e5e7eb;
      overflow: hidden;
    }

    .progress-bar {
      width: 0%;
      height: 100%;
      background: var(--accent);
      transition: width .25s ease;
    }

    .render-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .render-stat {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-weight: 700;
    }

    .render-stat strong {
      color: var(--text);
      font-size: 18px;
    }

    .render-output {
      color: var(--muted);
      word-break: break-all;
    }

    .render-schedule {
      display: grid;
      gap: 8px;
    }

    .render-schedule h3 {
      margin: 6px 0 0;
      font-size: 16px;
    }

    .render-schedule-row {
      display: grid;
      grid-template-columns: 52px minmax(180px, 1fr) 120px 100px 120px;
      gap: 10px;
      align-items: center;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      color: var(--muted);
      font-weight: 700;
      background: #f8fafc;
    }

    .render-schedule-row span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .render-schedule-head {
      background: #eef2f7;
      color: var(--text);
    }

    button.primary {
      height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      cursor: pointer;
      font: inherit;
      font-weight: 800;
      padding: 0 16px;
    }

    button.secondary {
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-weight: 800;
      padding: 0 14px;
    }

    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 8px;
    }

    .section-head h2 {
      margin: 0;
    }

    .summary {
      color: var(--muted);
      min-height: 22px;
    }

    .placeholder {
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      color: var(--muted);
      background: rgba(255, 255, 255, .6);
    }

    .sequence-list {
      display: grid;
      gap: 8px;
      min-width: 0;
    }

    .sequence-footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 18px;
    }

    .sequence-row {
      display: grid;
      grid-template-columns: 44px minmax(180px, 1fr) 130px 110px 96px 90px 36px;
      align-items: center;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      padding: 0 12px;
      cursor: grab;
    }

    .sequence-row.dragging {
      opacity: .55;
      cursor: grabbing;
    }

    .sequence-row.finetune-row {
      grid-template-columns: 44px minmax(160px, 1fr) 130px 110px 96px 90px 76px 96px;
      cursor: default;
    }

    .sequence-row.config-row {
      grid-template-columns: 44px minmax(160px, 1fr) 130px 110px minmax(150px, .8fr) 96px 90px;
      border: 0;
      border-radius: 0;
      background: transparent;
      cursor: default;
    }

    .config-group {
      display: grid;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
    }

    .config-group.song {
      background: #eef7ff;
      border-color: #bfdcf4;
    }

    .config-group.asset {
      background: #eefbf3;
      border-color: #bfe7cd;
    }

    .config-group .config-row + .config-row {
      border-top: 1px solid rgba(102, 112, 133, .16);
    }

    .row-actions {
      display: flex;
      justify-content: flex-end;
      gap: 4px;
    }

    .finetune-item {
      display: grid;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      overflow: hidden;
    }

    .finetune-item.song {
      background: #eef7ff;
      border-color: #bfdcf4;
    }

    .finetune-item.asset {
      background: #eefbf3;
      border-color: #bfe7cd;
    }

    .finetune-item .sequence-row {
      border: 0;
      border-radius: 0;
      background: transparent;
    }

    .effect-row {
      display: grid;
      grid-template-columns: repeat(6, minmax(118px, 1fr));
      gap: 8px;
      padding: 10px 12px;
      border-top: 1px solid rgba(102, 112, 133, .18);
      background: rgba(255, 255, 255, .45);
    }

    .effect-control {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      min-width: 0;
    }

    .effect-control label {
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 0;
      color: var(--text);
      white-space: nowrap;
    }

    .effect-control input[type="checkbox"] {
      width: 16px;
      height: 16px;
      padding: 0;
    }

    .effect-fields {
      display: none;
      align-items: center;
      gap: 6px;
    }

    .effect-control.enabled .effect-fields {
      display: flex;
    }

    .effect-fields input {
      height: 30px;
      font-size: 13px;
      padding: 0 8px;
      width: 64px;
    }

    .batch-controls {
      display: grid;
      grid-template-columns: repeat(4, max-content) max-content auto;
      gap: 12px;
      align-items: center;
      margin: 0 0 16px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .batch-controls > div {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .batch-controls > div.batch-hidden {
      display: none;
    }

    .batch-controls label {
      margin: 0;
      white-space: nowrap;
    }

    .batch-controls select,
    .batch-controls input {
      height: 34px;
      font-size: 14px;
    }

    .batch-controls select {
      width: auto;
      min-width: 86px;
    }

    .batch-controls input {
      width: 72px;
    }

    .batch-controls button {
      justify-self: start;
      width: auto;
      height: 34px;
      padding: 0 14px;
    }

    .batch-params {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .batch-params > div {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .batch-params > div.batch-hidden {
      display: none;
    }

    .batch-hidden {
      display: none;
    }

    .sequence-row.song {
      background: #eef7ff;
      border-color: #bfdcf4;
    }

    .sequence-row.asset {
      background: #eefbf3;
      border-color: #bfe7cd;
    }

    .sequence-index {
      color: var(--muted);
      font-weight: 800;
    }

    .sequence-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .sequence-meta {
      color: var(--muted);
      font-weight: 700;
      font-size: 13px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .sequence-meta.warning {
      color: #b42318;
    }

    .sequence-meta.insert-hard {
      color: #b42318;
    }

    .icon-button {
      width: 28px;
      height: 28px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font: inherit;
      font-size: 20px;
      line-height: 1;
    }

    .icon-button:hover {
      border-color: #f1b8b3;
      background: #fff1f0;
      color: #b42318;
    }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
      background: rgba(16, 24, 40, .38);
    }

    .modal-backdrop.open {
      display: flex;
    }

    .modal {
      width: min(720px, 100%);
      max-height: min(760px, calc(100vh - 48px));
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      background: var(--panel);
      border-radius: 8px;
      border: 1px solid var(--line);
      box-shadow: 0 20px 60px rgba(16, 24, 40, .22);
      overflow: hidden;
    }

    .modal-head,
    .modal-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }

    .modal-actions {
      border-top: 1px solid var(--line);
      border-bottom: 0;
      justify-content: flex-end;
    }

    .modal-title {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }

    .modal-body {
      min-height: 0;
      overflow: auto;
      padding: 16px;
    }

    .song-picker-list {
      display: grid;
      gap: 6px;
      margin-top: 12px;
    }

    .song-picker-row {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
    }

    .song-picker-row input {
      width: 16px;
      height: 16px;
      padding: 0;
    }

    .radio-stack {
      display: grid;
      gap: 12px;
    }

    .radio-row {
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-weight: 700;
    }

    .radio-row input {
      width: 16px;
      height: 16px;
      padding: 0;
    }

    @media (max-width: 760px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { border-right: 0; border-bottom: 1px solid var(--line); }
      .sequence-layout { grid-template-columns: 1fr; }
      .utility-panel { min-height: 0; border-left: 0; border-top: 1px solid var(--line); padding: 18px 0 0; }
      .nav { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .nav button { text-align: center; padding: 0 6px; }
      .workspace { padding: 24px 18px; }
      .sequence-row { grid-template-columns: 36px minmax(0, 1fr) 32px; gap: 4px 8px; padding: 8px 10px; }
      .sequence-meta { grid-column: 2; }
      .icon-button { grid-column: 3; grid-row: 1; }
      .effect-row { grid-template-columns: 1fr; }
      .batch-controls { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <h1 class="brand">AutoShow</h1>
      <nav class="nav" aria-label="工作流">
        <button class="active" data-tab="start">开始</button>
        <button data-tab="sequence">粗排</button>
        <button data-tab="finetune">精调</button>
        <button data-tab="config">配置</button>
        <button data-tab="export">导出</button>
      </nav>
    </aside>

    <main class="workspace">
      <section id="start" class="pane active">
        <h2>开始</h2>
        <p class="lead">先决定节目里要包含多少首歌。</p>

        <div class="field">
          <label for="trackCount">歌曲数量</label>
          <input id="trackCount" type="text" inputmode="numeric" value="25">
        </div>

        <div class="button-row">
          <button id="nextFromStart" class="primary">下一步</button>
          <span id="startSummary" class="summary"></span>
        </div>
      </section>

      <section id="sequence" class="pane">
        <div class="sequence-layout">
          <div class="sequence-main">
            <div class="section-head">
              <h2>粗排</h2>
              <div class="button-row compact">
                <button id="addSongBtn" class="secondary">添加歌曲</button>
                <button id="addAssetBtn" class="secondary">添加素材</button>
              </div>
            </div>
            <p id="sequenceSummary" class="lead">预计总时长：--:--</p>
            <div id="sequenceList" class="sequence-list"></div>
            <div class="sequence-footer">
              <button id="nextToFinetune" class="primary">下一步</button>
            </div>
          </div>
          <div class="utility-panel">
            <div class="section-head">
              <h2 class="utility-title">组任务</h2>
              <div class="button-row compact">
                <button id="addGroupTaskBtn" class="secondary">新增任务</button>
                <button id="importGroupTasksBtn" class="secondary">导入</button>
                <button id="exportGroupTasksBtn" class="secondary">导出</button>
                <input id="importGroupTasksFile" type="file" accept="application/json,.json" style="display:none">
              </div>
            </div>
            <div id="groupTaskList" class="group-task-list">
            </div>
          </div>
        </div>
      </section>

      <section id="finetune" class="pane">
        <div class="section-head">
          <h2>精调</h2>
          <div class="button-row compact">
            <button id="importFinetuneBtn" class="secondary">导入</button>
            <button id="exportFinetuneBtn" class="secondary">导出</button>
            <input id="importFinetuneFile" type="file" accept="application/json,.json" style="display:none">
          </div>
        </div>
        <div class="batch-controls">
          <div>
            <label for="batchTarget">将</label>
            <select id="batchTarget">
              <option value="all">所有</option>
              <option value="song">歌曲</option>
              <option value="asset">素材</option>
              <option value="hard">强打断</option>
              <option value="hard_before">强打断前</option>
            </select>
          </div>
          <div id="batchCategoryWrap" class="batch-hidden">
            <label for="batchCategory">素材类别</label>
            <select id="batchCategory"></select>
          </div>
          <div>
            <label for="batchEffect">效果</label>
            <select id="batchEffect">
              <option value="all">全部</option>
              <option value="bed_in">垫入</option>
              <option value="fade_in">淡入</option>
              <option value="fade_out">淡出</option>
              <option value="bed_out">垫出</option>
              <option value="cross_in">交叉叠入</option>
              <option value="cross_out">交叉叠出</option>
            </select>
          </div>
          <div>
            <label for="batchState">设定为</label>
            <select id="batchState">
              <option value="on">开启</option>
              <option value="off">关闭</option>
            </select>
          </div>
          <div id="batchParams" class="batch-params">
            <div id="batchSecondsWrap">
              <label for="batchSeconds">秒</label>
              <input id="batchSeconds" type="text" inputmode="decimal" value="3">
            </div>
            <div id="batchDbWrap">
              <label for="batchDb">分贝</label>
              <input id="batchDb" type="text" inputmode="decimal" value="8">
            </div>
          </div>
          <button id="applyBatchEffects" class="primary">应用</button>
        </div>
        <p id="finetuneSummary" class="lead">预计总时长：--:--</p>
        <div id="finetuneList" class="sequence-list"></div>
        <div class="sequence-footer">
          <button id="nextToConfig" class="primary">下一步</button>
        </div>
      </section>

      <section id="config" class="pane">
        <div class="section-head">
          <h2>配置</h2>
          <div class="button-row compact">
            <button id="startRenderBtn" class="primary">渲染</button>
            <button id="exportRenderPlanBtn" class="secondary">导出渲染计划</button>
          </div>
        </div>
        <p id="configSummary" class="lead">预计总时长：--:--</p>
        <div class="config-controls">
          <div class="config-toggle-group">
            <label class="config-toggle">
              <input id="loudnessNormalize" type="checkbox" checked>
              响度标准化
            </label>
            <label class="config-toggle">
              <input id="removeSilence" type="checkbox" checked>
              去除无声片段
            </label>
          </div>
          <div class="config-field">
            <label for="silenceMinSeconds">无声最短</label>
            <input id="silenceMinSeconds" type="text" inputmode="decimal" value="0.2">
          </div>
          <div class="config-field">
            <label for="silenceThresholdDb">无声最轻</label>
            <input id="silenceThresholdDb" type="text" inputmode="decimal" value="-20">
          </div>
          <div class="config-field">
            <label for="bedTransitionSeconds">垫化过渡</label>
            <input id="bedTransitionSeconds" type="text" inputmode="decimal" value="0.5">
          </div>
          <div class="config-field">
            <label for="exportFormat">导出格式</label>
            <select id="exportFormat">
              <option value="mp3">MP3</option>
              <option value="wav">WAV</option>
              <option value="flac">FLAC</option>
              <option value="aac">AAC</option>
              <option value="ogg">OGG</option>
            </select>
          </div>
          <div class="config-field">
            <label for="sampleRate">采样率</label>
            <select id="sampleRate">
              <option value="44100">44100 Hz</option>
              <option value="48000">48000 Hz</option>
              <option value="96000">96000 Hz</option>
            </select>
          </div>
          <div class="config-field">
            <label for="bitDepth">位深</label>
            <select id="bitDepth">
              <option value="32f">32-bit float</option>
              <option value="24">24-bit</option>
              <option value="16">16-bit</option>
            </select>
          </div>
          <div class="config-field">
            <label for="channelCount">声道数</label>
            <select id="channelCount">
              <option value="2">双声道</option>
              <option value="1">单声道</option>
            </select>
          </div>
        </div>
        <div id="configList" class="sequence-list"></div>
      </section>

      <section id="export" class="pane">
        <div class="section-head">
          <h2>导出</h2>
        </div>
        <p id="exportSummary" class="lead">等待渲染任务。</p>
        <div class="render-panel">
          <div class="progress-track">
            <div id="renderProgressBar" class="progress-bar"></div>
          </div>
          <div class="render-stats">
            <div class="render-stat">
              <span>进度</span>
              <strong id="renderProgressText">0%</strong>
            </div>
            <div class="render-stat">
              <span>已花时长</span>
              <strong id="renderElapsedText">--:--</strong>
            </div>
            <div class="render-stat">
              <span>预计剩余</span>
              <strong id="renderRemainingText">--:--</strong>
            </div>
          </div>
          <div id="renderOutputPath" class="render-output"></div>
          <div id="renderSchedule" class="render-schedule"></div>
        </div>
      </section>

    </main>
  </div>

  <div id="addMediaModal" class="modal-backdrop" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="addMediaTitle">
      <div class="modal-head">
        <h3 id="addMediaTitle" class="modal-title">添加歌曲</h3>
        <button id="closeAddMedia" class="secondary">关闭</button>
      </div>
      <div class="modal-body">
        <div id="mediaSelectStep">
          <label id="mediaSearchLabel" for="mediaSearch">搜索歌曲</label>
          <input id="mediaSearch" type="text" placeholder="输入文件名中的文字">
          <div id="mediaPickerList" class="song-picker-list"></div>
        </div>
        <div id="mediaInsertStep" style="display:none">
          <div class="radio-stack">
            <label class="radio-row"><input type="radio" name="insertMode" value="start" checked>添加至开头</label>
            <label class="radio-row"><input type="radio" name="insertMode" value="end">添加至结尾</label>
            <label class="radio-row"><input type="radio" name="insertMode" value="index">指定序号</label>
          </div>
          <div class="field" style="margin-top:16px">
            <label for="insertIndex">序号</label>
            <input id="insertIndex" type="text" inputmode="numeric" value="1">
          </div>
        </div>
      </div>
      <div class="modal-actions">
        <span id="addMediaSummary" class="summary"></span>
        <button id="backToMediaSelect" class="secondary" style="display:none">上一步</button>
        <button id="nextAddMedia" class="primary">下一步</button>
        <button id="confirmAddMedia" class="primary" style="display:none">添加</button>
      </div>
    </div>
  </div>

  <script>
    const DEFAULT_GROUP_TASKS = [
      {
        "trigger": "single",
        "interrupt_mode": "hard",
        "items": [
          {
            "type": "asset",
            "mode": "specified",
            "path": "media/assets/General/Beep.mp3",
            "title": "General / Beep"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 2,
            "count_max": 4,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "BackNow"
          }
        ],
        "insert_position": 1
      },
      {
        "trigger": "hourly",
        "interrupt_mode": "after_current",
        "items": [
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "RightBack"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 3,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "BackNow"
          }
        ],
        "minute": 15,
        "second": 0
      },
      {
        "trigger": "hourly",
        "interrupt_mode": "after_current",
        "items": [
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "RightBack"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 3,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "BackNow"
          }
        ],
        "minute": 45,
        "second": 0
      },
      {
        "trigger": "hourly",
        "interrupt_mode": "after_current",
        "items": [
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "RightBack"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 2,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "Intro"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 2,
            "count_max": 3,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "BackNow"
          }
        ],
        "minute": 30,
        "second": 0
      },
      {
        "trigger": "hourly",
        "interrupt_mode": "hard",
        "items": [
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "RightBack"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 2,
            "count_max": 4,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "specified",
            "path": "media/assets/TimeCheck/12.mp3",
            "title": "TimeCheck / 12"
          },
          {
            "type": "asset",
            "mode": "specified",
            "path": "media/assets/General/Beep.mp3",
            "title": "General / Beep"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 2,
            "count_max": 4,
            "category": "Jingle"
          },
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "BackNow"
          }
        ],
        "minute": 58,
        "second": 30
      },
      {
        "trigger": "max_songs",
        "interrupt_mode": "after_current",
        "items": [],
        "max_songs": 2,
        "category": "Jingle"
      },
      {
        "trigger": "single",
        "interrupt_mode": "after_current",
        "items": [
          {
            "type": "asset",
            "mode": "random",
            "count_min": 1,
            "count_max": 1,
            "category": "RightBack"
          }
        ],
        "insert_position": 0
      }
    ];

    const EFFECT_KINDS = ["bed_in", "fade_in", "fade_out", "bed_out", "cross_in", "cross_out"];
    const VOLUME_EFFECTS = new Set(["bed_in", "bed_out"]);
    const DEFAULT_EFFECT_SECONDS = "3";
    const DEFAULT_EFFECT_DB = "8";
    const DEFAULT_BED_TRANSITION_SECONDS = "0.5";
    const DEFAULT_SILENCE_MIN_SECONDS = "0.2";
    const DEFAULT_SILENCE_THRESHOLD_DB = "-20";
    const DEFAULT_RENDER_SETTINGS = {
      loudness_normalize: true,
      remove_silence: true,
      export_format: "mp3",
      sample_rate: "44100",
      bit_depth: "32f",
      channels: "2",
      bed_transition_seconds: DEFAULT_BED_TRANSITION_SECONDS,
      silence_min_seconds: DEFAULT_SILENCE_MIN_SECONDS,
      silence_threshold_db: DEFAULT_SILENCE_THRESHOLD_DB
    };
    const state = {
      trackCount: 25,
      sequence: [],
      songs: [],
      assets: [],
      pickerKind: "song",
      selectedMedia: [],
      bedTransitionSeconds: DEFAULT_BED_TRANSITION_SECONDS,
      renderSettings: { ...DEFAULT_RENDER_SETTINGS }
    };
    const renderState = { taskId: "", timer: null };
    const trackCount = document.getElementById("trackCount");
    const startSummary = document.getElementById("startSummary");

    function showTab(tab) {
      if (tab === "config") {
        persistEffectsFromDom();
        persistRenderSettingsFromDom();
        renderConfig();
      }
      document.querySelectorAll(".nav button").forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tab);
      });
      document.querySelectorAll(".pane").forEach((pane) => {
        pane.classList.toggle("active", pane.id === tab);
      });
    }

    document.querySelector(".nav").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-tab]");
      if (button) showTab(button.dataset.tab);
    });

    document.getElementById("sequenceList").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-index]");
      if (!button) return;
      state.sequence.splice(Number(button.dataset.removeIndex), 1);
      renderSequence();
    });

    document.getElementById("finetuneList").addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-finetune-remove]");
      if (removeButton) {
        state.sequence.splice(Number(removeButton.dataset.finetuneRemove), 1);
        renderSequence();
        renderFinetune();
        return;
      }
      const moveButton = event.target.closest("[data-finetune-move]");
      if (!moveButton) return;
      const index = Number(moveButton.dataset.finetuneIndex);
      const direction = moveButton.dataset.finetuneMove;
      const target = direction === "up" ? index - 1 : index + 1;
      if (target < 0 || target >= state.sequence.length) return;
      const [item] = state.sequence.splice(index, 1);
      state.sequence.splice(target, 0, item);
      renderSequence();
      renderFinetune();
    });

    document.getElementById("finetuneList").addEventListener("change", (event) => {
      const checkbox = event.target.closest("[data-effect-toggle]");
      if (!checkbox) return;
      const control = checkbox.closest(".effect-control");
      control.classList.toggle("enabled", checkbox.checked);
      if (checkbox.checked) initializeEffectDefaults(control);
      else clearEffectValues(control);
      syncCrossfadeControls(checkbox);
      persistEffectsFromDom();
    });

    document.getElementById("finetuneList").addEventListener("input", (event) => {
      const input = event.target.closest("[data-effect-seconds], [data-effect-db]");
      if (!input) return;
      if (input.matches("[data-effect-seconds]")) syncCrossfadeSeconds(input);
      persistEffectsFromDom();
    });

    document.getElementById("batchTarget").addEventListener("change", updateBatchControls);
    document.getElementById("batchEffect").addEventListener("change", updateBatchControls);
    document.getElementById("batchState").addEventListener("change", updateBatchControls);
    document.getElementById("applyBatchEffects").addEventListener("click", applyBatchEffects);
    document.getElementById("exportFinetuneBtn").addEventListener("click", exportFinetune);
    document.getElementById("importFinetuneBtn").addEventListener("click", () => {
      document.getElementById("importFinetuneFile").click();
    });
    document.getElementById("importFinetuneFile").addEventListener("change", importFinetune);
    ["loudnessNormalize", "removeSilence", "exportFormat", "sampleRate", "bitDepth", "channelCount", "bedTransitionSeconds", "silenceMinSeconds", "silenceThresholdDb"].forEach((id) => {
      document.getElementById(id).addEventListener("change", persistRenderSettingsFromDom);
    });
    document.getElementById("bedTransitionSeconds").addEventListener("input", persistRenderSettingsFromDom);
    document.getElementById("silenceMinSeconds").addEventListener("input", persistRenderSettingsFromDom);
    document.getElementById("silenceThresholdDb").addEventListener("input", persistRenderSettingsFromDom);
    document.getElementById("nextToConfig").addEventListener("click", () => {
      persistEffectsFromDom();
      persistRenderSettingsFromDom();
      renderConfig();
      showTab("config");
    });
    document.getElementById("exportRenderPlanBtn").addEventListener("click", exportRenderPlan);
    document.getElementById("startRenderBtn").addEventListener("click", startRender);

    document.getElementById("sequenceList").addEventListener("dragstart", (event) => {
      const row = event.target.closest("[data-sequence-index]");
      if (!row || event.target.closest("button")) return;
      row.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.dataset.sequenceIndex);
    });

    document.getElementById("sequenceList").addEventListener("dragend", (event) => {
      const row = event.target.closest("[data-sequence-index]");
      if (row) row.classList.remove("dragging");
    });

    document.getElementById("sequenceList").addEventListener("dragover", (event) => {
      if (event.target.closest("[data-sequence-index]")) event.preventDefault();
    });

    document.getElementById("sequenceList").addEventListener("drop", (event) => {
      const target = event.target.closest("[data-sequence-index]");
      if (!target) return;
      event.preventDefault();
      const from = Number(event.dataTransfer.getData("text/plain"));
      const to = Number(target.dataset.sequenceIndex);
      if (Number.isNaN(from) || Number.isNaN(to) || from === to) return;
      const [item] = state.sequence.splice(from, 1);
      state.sequence.splice(to, 0, item);
      renderSequence();
    });

    document.getElementById("addGroupTaskBtn").addEventListener("click", () => {
      document.getElementById("groupTaskList").appendChild(createGroupTaskCard());
    });

    document.getElementById("nextToFinetune").addEventListener("click", async () => {
      await applyGroupTasks();
      applyDefaultFadeOutBeforeHardBreaks();
      renderSequence();
      renderFinetune();
      showTab("finetune");
    });

    document.getElementById("exportGroupTasksBtn").addEventListener("click", exportGroupTasks);
    document.getElementById("importGroupTasksBtn").addEventListener("click", () => {
      document.getElementById("importGroupTasksFile").click();
    });
    document.getElementById("importGroupTasksFile").addEventListener("change", importGroupTasks);

    document.getElementById("groupTaskList").addEventListener("change", (event) => {
      if (event.target.matches("[data-group-trigger]")) {
        updateGroupTaskTrigger(event.target.closest(".group-task-card"));
        return;
      }
      if (event.target.matches("[data-task-item-type], [data-task-item-mode]")) {
        updateGroupTaskItem(event.target.closest(".group-task-item-row"));
      }
    });

    document.getElementById("groupTaskList").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-group-task]");
      if (button) {
        button.closest(".group-task-card").remove();
        return;
      }
      const addItemButton = event.target.closest("[data-add-group-task-item]");
      if (!addItemButton) {
        const removeItemButton = event.target.closest("[data-remove-group-task-item]");
        if (removeItemButton) removeItemButton.closest(".group-task-item-row").remove();
        return;
      }
      const row = createGroupTaskItemRow();
      addItemButton.before(row);
      updateGroupTaskItem(row);
    });

    document.getElementById("groupTaskList").addEventListener("dragstart", (event) => {
      const row = event.target.closest(".group-task-item-row");
      if (!row || event.target.closest("input, select, button")) return;
      row.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", "group-task-item");
    });

    document.getElementById("groupTaskList").addEventListener("dragend", (event) => {
      const row = event.target.closest(".group-task-item-row");
      if (row) row.classList.remove("dragging");
    });

    document.getElementById("groupTaskList").addEventListener("dragover", (event) => {
      const target = event.target.closest(".group-task-item-row");
      const dragging = document.querySelector(".group-task-item-row.dragging");
      if (!target || !dragging || target.closest(".group-task-card") !== dragging.closest(".group-task-card")) return;
      event.preventDefault();
    });

    document.getElementById("groupTaskList").addEventListener("drop", (event) => {
      const target = event.target.closest(".group-task-item-row");
      const dragging = document.querySelector(".group-task-item-row.dragging");
      if (!target || !dragging || target === dragging || target.closest(".group-task-card") !== dragging.closest(".group-task-card")) return;
      event.preventDefault();
      const body = target.closest(".group-task-body");
      const rows = [...body.querySelectorAll(".group-task-item-row")];
      const from = rows.indexOf(dragging);
      const to = rows.indexOf(target);
      if (from < to) target.after(dragging);
      else target.before(dragging);
    });

    function createGroupTaskCard() {
      const card = document.createElement("div");
      card.className = "group-task-card";
      card.innerHTML = `
        <div class="group-task-head">
          <div class="group-task-top">
            <div class="group-task-trigger">
              <label>触发方式</label>
              <select data-group-trigger>
                <option value="single">单次触发</option>
                <option value="hourly">小时循环</option>
                <option value="max_songs">最大曲目</option>
              </select>
            </div>
            <div class="group-task-interrupt">
              <label>打断模式</label>
              <select data-group-interrupt>
                <option value="hard">强打断</option>
                <option value="after_current">待播放</option>
              </select>
            </div>
          </div>
          <button class="icon-button group-task-remove" data-remove-group-task title="删除组任务">×</button>
          <div class="group-task-trigger-index">
            <label>插入位置</label>
            <input type="text" inputmode="numeric" value="1" data-group-index>
          </div>
          <div class="group-task-time-row hidden">
            <div class="group-task-time">
              <label>分</label>
              <input type="text" inputmode="numeric" value="0" data-group-minute>
            </div>
            <div class="group-task-time">
              <label>秒</label>
              <input type="text" inputmode="numeric" value="0" data-group-second>
            </div>
          </div>
          <div class="group-task-max-row hidden">
            <div>
              <label>最大歌曲数</label>
              <input type="text" inputmode="numeric" value="2" data-group-max-songs>
            </div>
            <div>
              <label>分类</label>
              <select data-group-max-category></select>
            </div>
          </div>
        </div>
        <div class="group-task-body">
          <button class="secondary" data-add-group-task-item>新增项目</button>
        </div>
      `;
      return card;
    }

    function updateGroupTaskTrigger(card) {
      const mode = card.querySelector("[data-group-trigger]").value;
      if (mode === "max_songs" && hasOtherMaxSongTask(card)) {
        card.querySelector("[data-group-trigger]").value = "single";
        flashGroupTaskWarning(card);
        updateGroupTaskTrigger(card);
        return;
      }
      card.querySelector(".group-task-trigger-index").classList.toggle("hidden", mode !== "single");
      card.querySelector(".group-task-time-row").classList.toggle("hidden", mode !== "hourly");
      card.querySelector(".group-task-max-row").classList.toggle("hidden", mode !== "max_songs");
      card.querySelector(".group-task-body").classList.toggle("hidden", mode === "max_songs");
      if (mode === "max_songs") populateGroupMaxCategories(card);
    }

    function hasOtherMaxSongTask(card) {
      return [...document.querySelectorAll(".group-task-card")]
        .some((item) => item !== card && item.querySelector("[data-group-trigger]").value === "max_songs");
    }

    function flashGroupTaskWarning(card) {
      card.classList.add("warning");
      setTimeout(() => card.classList.remove("warning"), 1200);
    }

    async function populateGroupMaxCategories(card) {
      const select = card.querySelector("[data-group-max-category]");
      if (select.options.length) return;
      await populateAssetCategorySelect(select, "random", "随机");
    }

    function collectGroupTasks() {
      return [...document.querySelectorAll(".group-task-card")].map((card) => {
        const trigger = card.querySelector("[data-group-trigger]").value;
        const task = {
          trigger,
          interrupt_mode: card.querySelector("[data-group-interrupt]").value,
          items: trigger === "max_songs" ? [] : [...card.querySelectorAll(".group-task-item-row")].map(collectGroupTaskItem)
        };
        if (trigger === "single") {
          task.insert_position = intValue(card.querySelector("[data-group-index]").value, 0);
        } else if (trigger === "hourly") {
          task.minute = intValue(card.querySelector("[data-group-minute]").value, 0);
          task.second = intValue(card.querySelector("[data-group-second]").value, 0);
        } else if (trigger === "max_songs") {
          task.max_songs = intValue(card.querySelector("[data-group-max-songs]").value, 1);
          task.category = card.querySelector("[data-group-max-category]").value || "random";
        }
        return task;
      });
    }

    function collectGroupTaskItem(row) {
      const type = row.querySelector("[data-task-item-type]").value;
      const mode = row.querySelector("[data-task-item-mode]").value;
      const item = { type, mode };
      if (mode === "specified") {
        const selected = row.querySelector("[data-task-specified]");
        item.path = selected.value;
        item.title = selected.selectedOptions[0]?.textContent || "";
      } else {
        item.count_min = intValue(row.querySelector("[data-task-count-min]").value, 1);
        item.count_max = intValue(row.querySelector("[data-task-count-max]").value, item.count_min);
        if (type === "asset") {
          item.category = row.querySelector("[data-task-category]").value || "random";
        }
      }
      return item;
    }

    function intValue(value, fallback) {
      const number = Number(value);
      return Number.isInteger(number) ? number : fallback;
    }

    function exportGroupTasks() {
      const payload = {
        exported_at: new Date().toISOString(),
        group_tasks: collectGroupTasks()
      };
      downloadJson(payload, "autoshow-group-tasks.json");
    }

    async function applyGroupTasks() {
      restoreManualSequence();
      const tasks = collectGroupTasks();
      await applySingleTasks(tasks.filter((task) => task.trigger === "single"));
      await applyHourlyTasks(tasks.filter((task) => task.trigger === "hourly"));
      await applyMaxSongTasks(tasks.filter((task) => task.trigger === "max_songs"));
    }

    function applyDefaultFadeOutBeforeHardBreaks() {
      state.sequence.forEach((item, index) => {
        if (state.sequence[index + 1]?.insert_interrupt_mode !== "hard") return;
        if (!item.effects) item.effects = {};
        if (item.effects.fade_out && item.effects.fade_out.enabled && !item.effects.fade_out.auto_default) return;
        item.effects.fade_out = {
          ...(item.effects.fade_out || {}),
          enabled: true,
          seconds: item.effects.fade_out?.seconds || DEFAULT_EFFECT_SECONDS,
          db: "",
          auto_default: "hard_break_fade_out"
        };
      });
    }

    function restoreManualSequence() {
      state.sequence = state.sequence
        .filter((item) => !item.auto_generated)
        .map((item) => {
          if (item.original_duration_ms !== undefined) {
            item.duration_ms = item.original_duration_ms;
            delete item.original_duration_ms;
          }
          clearAutoDefaultEffects(item);
          return item;
        });
    }

    function clearAutoDefaultEffects(item) {
      if (!item.effects) return;
      Object.keys(item.effects).forEach((kind) => {
        if (item.effects[kind]?.auto_default) delete item.effects[kind];
      });
      if (!Object.keys(item.effects).length) delete item.effects;
    }

    async function applySingleTasks(tasks) {
      for (const task of tasks) {
        const insertAt = task.insert_position === 0
          ? state.sequence.length
          : Math.min(Math.max(0, (task.insert_position || 1) - 1), state.sequence.length);
        state.sequence.splice(insertAt, 0, ...(await generatedItemsForTask(task, "single")));
      }
    }

    async function applyHourlyTasks(tasks) {
      for (const task of tasks) {
        const horizonMs = totalDuration();
        for (let hour = 0; hour * 3600000 < horizonMs; hour += 1) {
          const targetMs = hour * 3600000 + (task.minute || 0) * 60000 + (task.second || 0) * 1000;
          if (targetMs >= horizonMs) continue;
          const insertAt = findInsertIndexForTime(targetMs, task.interrupt_mode);
          state.sequence.splice(insertAt, 0, ...(await generatedItemsForTask(task, `hourly:${hour}`)));
        }
      }
    }

    function findInsertIndexForTime(targetMs, interruptMode) {
      let cursorMs = 0;
      for (let index = 0; index < state.sequence.length; index += 1) {
        const item = state.sequence[index];
        const durationMs = item.duration_ms || 0;
        const endMs = cursorMs + durationMs;
        if (targetMs <= cursorMs) return index;
        if (targetMs < endMs) {
          if (interruptMode === "hard") {
            if (item.original_duration_ms === undefined) item.original_duration_ms = durationMs;
            item.duration_ms = Math.max(0, targetMs - cursorMs);
          }
          return index + 1;
        }
        cursorMs = endMs;
      }
      return state.sequence.length;
    }

    async function applyMaxSongTasks(tasks) {
      for (const task of tasks) {
        const maxSongs = Math.max(1, task.max_songs || 1);
        let songRun = 0;
        let threshold = randomInt(1, maxSongs);
        for (let index = 0; index < state.sequence.length; index += 1) {
          const item = state.sequence[index];
          if (item.kind !== "song") {
            songRun = 0;
            threshold = randomInt(1, maxSongs);
            continue;
          }
          songRun += 1;
          const next = state.sequence[index + 1];
          if (songRun >= threshold && next && next.kind === "song") {
            const inserted = await generatedItemsForTask(task, `max_songs:${index}`, true);
            state.sequence.splice(index + 1, 0, ...inserted);
            index += inserted.length;
            songRun = 0;
            threshold = randomInt(1, maxSongs);
          }
        }
      }
    }

    async function generatedItemsForTask(task, triggerId, maxSongFallback = false) {
      const sourceItems = task.items.length ? task.items : (maxSongFallback ? [
        { type: "asset", mode: "random", count_min: 1, count_max: 1, category: task.category || "random" }
      ] : []);
      const generated = [];
      for (const item of sourceItems) {
        generated.push(...(await generatedItemsForRuleItem(item)));
      }
      return generated.map((item, index) => ({
        ...item,
        auto_generated: true,
        auto_trigger: triggerId,
        insert_method_label: insertionMethodLabel(task, index),
        insert_interrupt_mode: insertionInterruptMode(task, index)
      }));
    }

    function insertionMethodLabel(task, itemIndex = 0) {
      if (!task || !task.trigger) return "普通插入";
      if (itemIndex > 0) return "组内跟随";
      const triggerLabels = {
        single: "单次触发",
        hourly: "定时任务",
        max_songs: "最大曲目"
      };
      const interruptLabels = {
        hard: "强打断",
        after_current: "待播放"
      };
      if (task.trigger === "max_songs") return "最大曲目插入";
      return `${triggerLabels[task.trigger] || "任务"}${interruptLabels[task.interrupt_mode] || "普通插入"}`;
    }

    function insertionInterruptMode(task, itemIndex = 0) {
      if (itemIndex > 0) return "follow";
      return task.interrupt_mode || "normal";
    }

    async function generatedItemsForRuleItem(ruleItem) {
      if (ruleItem.mode === "specified") {
        const item = await findMediaItem(ruleItem.type, ruleItem.path);
        return item ? [{ ...item }] : [];
      }
      const pool = await randomPool(ruleItem);
      const count = randomInt(
        Math.max(1, ruleItem.count_min || 1),
        Math.max(ruleItem.count_min || 1, ruleItem.count_max || ruleItem.count_min || 1)
      );
      return pickRandomItems(pool, count).map((item) => ({ ...item }));
    }

    async function findMediaItem(type, path) {
      const items = type === "song" ? await loadSongs() : await loadAssets();
      return items.find((item) => item.path === path);
    }

    async function randomPool(ruleItem) {
      if (ruleItem.type === "song") return loadSongs();
      const assets = await loadAssets();
      if (!ruleItem.category || ruleItem.category === "random") return assets;
      return assets.filter((item) => item.category === ruleItem.category);
    }

    function pickRandomItems(items, count) {
      const shuffled = [...items].sort(() => Math.random() - 0.5);
      const selected = shuffled.slice(0, count);
      while (selected.length < count && items.length) {
        selected.push(items[randomInt(0, items.length - 1)]);
      }
      return selected;
    }

    function randomInt(min, max) {
      return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    async function importGroupTasks(event) {
      const file = event.target.files[0];
      if (!file) return;
      try {
        const payload = JSON.parse(await file.text());
        await restoreGroupTasks(payload.group_tasks || []);
      } catch (error) {
        alert(`导入失败：${error.message}`);
      } finally {
        event.target.value = "";
      }
    }

    async function restoreGroupTasks(tasks) {
      const list = document.getElementById("groupTaskList");
      list.innerHTML = "";
      let hasMaxSongTask = false;
      for (const task of tasks) {
        const card = createGroupTaskCard();
        list.appendChild(card);
        let trigger = task.trigger || "single";
        if (trigger === "max_songs") {
          if (hasMaxSongTask) trigger = "single";
          else hasMaxSongTask = true;
        }
        card.querySelector("[data-group-trigger]").value = trigger;
        card.querySelector("[data-group-interrupt]").value = task.interrupt_mode || "hard";
        if (task.insert_position !== undefined) card.querySelector("[data-group-index]").value = task.insert_position;
        if (task.minute !== undefined) card.querySelector("[data-group-minute]").value = task.minute;
        if (task.second !== undefined) card.querySelector("[data-group-second]").value = task.second;
        if (task.max_songs !== undefined) card.querySelector("[data-group-max-songs]").value = task.max_songs;
        updateGroupTaskTrigger(card);
        if (trigger === "max_songs") {
          await populateGroupMaxCategories(card);
          card.querySelector("[data-group-max-category]").value = task.category || "random";
        }
        const addButton = card.querySelector("[data-add-group-task-item]");
        for (const item of (trigger === "max_songs" ? [] : task.items || [])) {
          const row = createGroupTaskItemRow();
          addButton.before(row);
          row.querySelector("[data-task-item-type]").value = item.type || "asset";
          row.querySelector("[data-task-item-mode]").value = item.mode || "random";
          await updateGroupTaskItem(row);
          if ((item.mode || "random") === "specified") {
            row.querySelector("[data-task-specified]").value = item.path || "";
          } else {
            row.querySelector("[data-task-count-min]").value = item.count_min ?? 1;
            row.querySelector("[data-task-count-max]").value = item.count_max ?? 1;
            if ((item.type || "song") === "asset") {
              row.querySelector("[data-task-category]").value = item.category || "random";
            }
          }
        }
      }
    }

    function createGroupTaskItemRow() {
      const row = document.createElement("div");
      row.className = "group-task-item-row";
      row.draggable = true;
      row.innerHTML = `
        <button class="icon-button group-task-item-remove" data-remove-group-task-item title="删除项目">×</button>
        <div>
          <label>类型</label>
          <select data-task-item-type>
            <option value="asset">素材</option>
            <option value="song">歌曲</option>
          </select>
        </div>
        <div>
          <label>内容</label>
          <select data-task-item-mode>
            <option value="random">随机</option>
            <option value="specified">指定</option>
          </select>
        </div>
        <div class="group-task-item-wide" data-task-specified-wrap>
          <label>指定项目</label>
          <select data-task-specified></select>
        </div>
        <div class="group-task-random-quantity group-task-item-wide" data-task-random-wrap>
          <div>
            <label>最小数量</label>
            <input type="text" inputmode="numeric" value="1" data-task-count-min>
          </div>
          <div>
            <label>最大数量</label>
            <input type="text" inputmode="numeric" value="1" data-task-count-max>
          </div>
        </div>
        <div class="group-task-item-wide" data-task-category-wrap>
          <label>分类</label>
          <select data-task-category></select>
        </div>
      `;
      return row;
    }

    async function updateGroupTaskItem(row) {
      const type = row.querySelector("[data-task-item-type]").value;
      const mode = row.querySelector("[data-task-item-mode]").value;
      row.querySelector("[data-task-specified-wrap]").classList.toggle("group-task-item-hidden", mode !== "specified");
      row.querySelector("[data-task-random-wrap]").classList.toggle("group-task-item-hidden", mode !== "random");
      row.querySelector("[data-task-category-wrap]").classList.toggle("group-task-item-hidden", !(type === "asset" && mode === "random"));
      if (mode === "specified") {
        await populateSpecifiedOptions(row, type);
      }
      if (type === "asset" && mode === "random") {
        await populateCategoryOptions(row);
      }
    }

    async function populateSpecifiedOptions(row, type) {
      const items = type === "song" ? await loadSongs() : await loadAssets();
      const select = row.querySelector("[data-task-specified]");
      select.innerHTML = items.map((item) => `<option value="${escapeHtml(item.path)}">${escapeHtml(mediaPickerTitle(item))}</option>`).join("");
    }

    async function populateCategoryOptions(row) {
      const select = row.querySelector("[data-task-category]");
      await populateAssetCategorySelect(select, "random", "随机");
    }

    function renderSequence() {
      renderSequenceView("sequenceList", "sequenceSummary", true);
    }

    function renderFinetune() {
      renderSequenceView("finetuneList", "finetuneSummary", false, true);
    }

    function renderConfig() {
      const list = document.getElementById("configList");
      if (!list) return;
      if (!state.sequence.length) {
        document.getElementById("configSummary").textContent = "预计总时长：--:--";
        list.innerHTML = '<div class="placeholder">还没有可配置的节目单。</div>';
        return;
      }
      const schedule = adjustedSchedule();
      document.getElementById("configSummary").textContent = `预计总时长：${formatDuration(schedule.totalMs)}`;
      list.innerHTML = groupSequenceByKind().map((group) => `
        <div class="config-group ${escapeHtml(group.kind || "")}">
          ${group.items.map(({ item, index }) => configRow(item, index, schedule.items[index])).join("")}
        </div>
      `).join("");
    }

    function groupSequenceByKind() {
      const groups = [];
      state.sequence.forEach((item, index) => {
        const previous = groups[groups.length - 1];
        if (!previous || previous.kind !== item.kind) {
          groups.push({ kind: item.kind, items: [] });
        }
        groups[groups.length - 1].items.push({ item, index });
      });
      return groups;
    }

    function configRow(item, index, timing) {
      return `
        <div class="sequence-row config-row">
          <span class="sequence-index">${index + 1}</span>
          <span class="sequence-title">${escapeHtml(item.title)}</span>
          <span class="sequence-meta ${insertionModeClass(item)}">${escapeHtml(insertionModeLabel(item))}</span>
          ${categoryMeta(item)}
          <span class="sequence-meta">${escapeHtml(effectSummary(item))}</span>
          <span class="sequence-meta">开始-${formatDuration(timing.start_ms)}</span>
          <span class="sequence-meta">时长-${formatDuration(item.duration_ms)}</span>
        </div>
      `;
    }

    function adjustedSchedule() {
      const items = [];
      let cursorMs = 0;
      state.sequence.forEach((item, index) => {
        const overlapMs = index === 0 ? 0 : overlapBeforeMs(index);
        const startMs = Math.max(0, cursorMs - overlapMs);
        const endMs = startMs + (item.duration_ms || 0);
        items.push({ start_ms: startMs, end_ms: endMs });
        cursorMs = Math.max(cursorMs, endMs);
      });
      return { items, totalMs: cursorMs };
    }

    function overlapBeforeMs(index) {
      const current = state.sequence[index];
      const previous = state.sequence[index - 1];
      return Math.max(
        effectSeconds(current, "bed_in"),
        effectSeconds(current, "cross_in"),
        effectSeconds(previous, "bed_out"),
        effectSeconds(previous, "cross_out")
      ) * 1000;
    }

    function effectSeconds(item, kind) {
      const effect = item?.effects?.[kind];
      if (!effect || !effect.enabled) return 0;
      const value = Number(effect.seconds);
      return Number.isFinite(value) && value > 0 ? value : 0;
    }

    function renderSequenceView(listId, summaryId, interactive, finetune = false) {
      const list = document.getElementById(listId);
      if (!list) return;
      document.getElementById(summaryId).textContent = `预计总时长：${formatDuration(totalDuration())}`;
      if (!state.sequence.length) {
        list.innerHTML = '<div class="placeholder">还没有生成节目单。</div>';
        return;
      }
      let cursorMs = 0;
      const counts = state.sequence.reduce((acc, item) => {
        acc[item.path] = (acc[item.path] || 0) + 1;
        return acc;
      }, {});
      list.innerHTML = state.sequence.map((item, index) => {
        const startMs = cursorMs;
        cursorMs += item.duration_ms || 0;
        const row = `
          <div class="sequence-row ${escapeHtml(item.kind || "")} ${finetune ? "finetune-row" : ""}" ${interactive ? 'draggable="true"' : ""} data-sequence-index="${index}">
            <span class="sequence-index">${index + 1}</span>
            <span class="sequence-title">${escapeHtml(item.title)}</span>
            <span class="sequence-meta ${insertionModeClass(item)}">${escapeHtml(insertionModeLabel(item))}</span>
            ${finetune ? categoryMeta(item) : ""}
            <span class="sequence-meta">开始-${formatDuration(startMs)}</span>
            <span class="sequence-meta">时长-${formatDuration(item.duration_ms)}</span>
            <span class="sequence-meta ${isRepeated(item, index, counts) ? "warning" : ""}">重复-${isRepeated(item, index, counts) ? "是" : "否"}</span>
            ${finetune ? `<span class="row-actions">
              <button class="icon-button" data-finetune-move="up" data-finetune-index="${index}" title="上移">↑</button>
              <button class="icon-button" data-finetune-move="down" data-finetune-index="${index}" title="下移">↓</button>
              <button class="icon-button" data-finetune-remove="${index}" title="删除">×</button>
            </span>` : ""}
            ${interactive ? `<button class="icon-button" data-remove-index="${index}" title="删除">×</button>` : ""}
          </div>
        `;
        if (!finetune) return row;
        return `<div class="finetune-item ${escapeHtml(item.kind || "")}" data-finetune-item="${index}">${row}${effectRow(index, item)}</div>`;
      }).join("");
    }

    function categoryMeta(item) {
      const label = item.kind === "asset" && item.category ? `类别-${item.category}` : "";
      return `<span class="sequence-meta">${escapeHtml(label)}</span>`;
    }

    function effectRow(index, item) {
      return `
        <div class="effect-row">
          ${effectControl("bed_in", index, "垫入", true, item)}
          ${effectControl("fade_in", index, "淡入", false, item)}
          ${effectControl("fade_out", index, "淡出", false, item)}
          ${effectControl("bed_out", index, "垫出", true, item)}
          ${effectControl("cross_in", index, "交叉叠入", false, item)}
          ${effectControl("cross_out", index, "交叉叠出", false, item)}
        </div>
      `;
    }

    function insertionModeLabel(item) {
      return item.insert_method_label || "普通插入";
    }

    function insertionModeClass(item) {
      return item.insert_interrupt_mode === "hard" ? "insert-hard" : "";
    }

    function effectSummary(item) {
      const labels = {
        bed_in: "垫入",
        fade_in: "淡入",
        fade_out: "淡出",
        bed_out: "垫出",
        cross_in: "交叉叠入",
        cross_out: "交叉叠出"
      };
      const enabled = EFFECT_KINDS
        .map((kind) => {
          const effect = item.effects?.[kind];
          if (!effect || !effect.enabled) return "";
          const parts = [];
          if (effect.seconds) parts.push(`${effect.seconds}s`);
          if (VOLUME_EFFECTS.has(kind) && effect.db) parts.push(`${effect.db}dB`);
          return `${labels[kind]}${parts.length ? parts.join("/") : ""}`;
        })
        .filter(Boolean);
      return enabled.length ? enabled.join("、") : "无效果";
    }

    function effectControl(kind, index, label, hasVolume, item) {
      const effect = (item.effects && item.effects[kind]) || {};
      const enabled = Boolean(effect.enabled);
      return `
        <div class="effect-control ${enabled ? "enabled" : ""}" data-effect-control="${kind}" data-effect-index="${index}">
          <label><input type="checkbox" data-effect-toggle="${kind}" data-effect-index="${index}" ${enabled ? "checked" : ""}>${label}</label>
          <div class="effect-fields">
            <input type="text" inputmode="decimal" placeholder="秒" value="${escapeHtml(effect.seconds || "")}" data-effect-seconds="${kind}">
            ${hasVolume ? '<input type="text" inputmode="decimal" placeholder="dB" value="' + escapeHtml(effect.db || "") + '" data-effect-db="' + kind + '">' : ""}
          </div>
        </div>
      `;
    }

    function syncCrossfadeControls(checkbox) {
      const kind = checkbox.dataset.effectToggle;
      if (kind !== "cross_in" && kind !== "cross_out") return;
      const index = Number(checkbox.dataset.effectIndex);
      const targetIndex = kind === "cross_in" ? index - 1 : index + 1;
      const targetKind = kind === "cross_in" ? "cross_out" : "cross_in";
      const target = document.querySelector(`[data-effect-toggle="${targetKind}"][data-effect-index="${targetIndex}"]`);
      if (!target) return;
      target.checked = checkbox.checked;
      target.closest(".effect-control").classList.toggle("enabled", checkbox.checked);
      const sourceSeconds = checkbox.closest(".effect-control").querySelector("[data-effect-seconds]");
      const targetSeconds = target.closest(".effect-control").querySelector("[data-effect-seconds]");
      targetSeconds.value = sourceSeconds.value;
    }

    function initializeEffectDefaults(control) {
      const secondsInput = control.querySelector("[data-effect-seconds]");
      if (secondsInput && !secondsInput.value) secondsInput.value = DEFAULT_EFFECT_SECONDS;
      const dbInput = control.querySelector("[data-effect-db]");
      if (dbInput && !dbInput.value) dbInput.value = DEFAULT_EFFECT_DB;
    }

    function clearEffectValues(control) {
      control.querySelectorAll("[data-effect-seconds], [data-effect-db]").forEach((input) => {
        input.value = "";
      });
    }

    function syncCrossfadeSeconds(input) {
      const kind = input.dataset.effectSeconds;
      if (kind !== "cross_in" && kind !== "cross_out") return;
      const control = input.closest(".effect-control");
      const checkbox = control.querySelector("[data-effect-toggle]");
      if (!checkbox.checked) return;
      const index = Number(checkbox.dataset.effectIndex);
      const targetIndex = kind === "cross_in" ? index - 1 : index + 1;
      const targetKind = kind === "cross_in" ? "cross_out" : "cross_in";
      const target = document.querySelector(`[data-effect-toggle="${targetKind}"][data-effect-index="${targetIndex}"]`);
      if (!target || !target.checked) return;
      target.closest(".effect-control").querySelector("[data-effect-seconds]").value = input.value;
    }

    async function updateBatchControls() {
      const target = document.getElementById("batchTarget").value;
      const effect = document.getElementById("batchEffect").value;
      const stateValue = document.getElementById("batchState").value;
      document.getElementById("batchCategoryWrap").classList.toggle("batch-hidden", target !== "asset");
      if (target === "asset") await populateBatchCategories();

      const showParams = stateValue === "on" && effect !== "all";
      const hasVolume = VOLUME_EFFECTS.has(effect);
      document.getElementById("batchParams").classList.toggle("batch-hidden", !showParams);
      document.getElementById("batchSecondsWrap").classList.toggle("batch-hidden", !showParams);
      document.getElementById("batchDbWrap").classList.toggle("batch-hidden", !(showParams && hasVolume));
    }

    async function populateBatchCategories() {
      const select = document.getElementById("batchCategory");
      const previous = select.value || "all";
      await populateAssetCategorySelect(select, "all", "全部素材");
      select.value = [...select.options].some((option) => option.value === previous) ? previous : "all";
    }

    async function populateAssetCategorySelect(select, firstValue, firstLabel) {
      const categories = await assetCategories();
      select.innerHTML = `<option value="${escapeHtml(firstValue)}">${escapeHtml(firstLabel)}</option>` +
        categories.map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`).join("");
    }

    async function assetCategories() {
      const assets = await loadAssets();
      return [...new Set(assets.map((item) => item.category).filter(Boolean))].sort();
    }

    function applyBatchEffects() {
      const target = document.getElementById("batchTarget").value;
      const category = document.getElementById("batchCategory").value || "all";
      const effect = document.getElementById("batchEffect").value;
      const enabled = document.getElementById("batchState").value === "on";
      const seconds = document.getElementById("batchSeconds").value.trim();
      const db = document.getElementById("batchDb").value.trim();
      const effects = effect === "all" ? EFFECT_KINDS : [effect];

      document.querySelectorAll(".finetune-item").forEach((element) => {
        const index = Number(element.dataset.finetuneItem);
        const item = state.sequence[index];
        if (!batchTargetMatches(item, index, target, category)) return;
        effects.forEach((kind) => setEffectState(element, kind, enabled, effect === "all" ? "" : seconds, effect === "all" ? "" : db, true));
      });
      persistEffectsFromDom();
    }

    function batchTargetMatches(item, index, target, category) {
      if (!item) return false;
      if (target === "all") return true;
      if (target === "song") return item.kind === "song";
      if (target === "asset") return item.kind === "asset" && (category === "all" || item.category === category);
      if (target === "hard") return item.insert_interrupt_mode === "hard";
      if (target === "hard_before") return state.sequence[index + 1]?.insert_interrupt_mode === "hard";
      return false;
    }

    function setEffectState(element, kind, enabled, seconds, db, syncPair = false) {
      const control = element.querySelector(`[data-effect-control="${kind}"]`);
      if (!control) return;
      const checkbox = control.querySelector("[data-effect-toggle]");
      checkbox.checked = enabled;
      control.classList.toggle("enabled", enabled);
      if (!enabled) {
        clearEffectValues(control);
        if (syncPair) syncPairedCrossfadeState(element, kind, enabled, "");
        return;
      }
      initializeEffectDefaults(control);

      if (seconds) {
        const secondsInput = control.querySelector("[data-effect-seconds]");
        if (secondsInput) secondsInput.value = seconds;
      }
      if (db && VOLUME_EFFECTS.has(kind)) {
        const dbInput = control.querySelector("[data-effect-db]");
        if (dbInput) dbInput.value = db;
      }
      if (syncPair) {
        const secondsInput = control.querySelector("[data-effect-seconds]");
        syncPairedCrossfadeState(element, kind, enabled, secondsInput ? secondsInput.value : "");
      }
    }

    function syncPairedCrossfadeState(element, kind, enabled, seconds) {
      if (kind !== "cross_in" && kind !== "cross_out") return;
      const index = Number(element.dataset.finetuneItem);
      const targetIndex = kind === "cross_in" ? index - 1 : index + 1;
      const targetKind = kind === "cross_in" ? "cross_out" : "cross_in";
      const targetElement = document.querySelector(`.finetune-item[data-finetune-item="${targetIndex}"]`);
      if (!targetElement) return;
      setEffectState(targetElement, targetKind, enabled, seconds, "", false);
    }

    function persistEffectsFromDom() {
      document.querySelectorAll(".finetune-item").forEach((element) => {
        const index = Number(element.dataset.finetuneItem);
        const item = state.sequence[index];
        if (!item) return;
        const effects = {};
        element.querySelectorAll(".effect-control").forEach((control) => {
          const kind = control.dataset.effectControl;
          const checkbox = control.querySelector("[data-effect-toggle]");
          const secondsInput = control.querySelector("[data-effect-seconds]");
          const dbInput = control.querySelector("[data-effect-db]");
          effects[kind] = {
            enabled: Boolean(checkbox && checkbox.checked),
            seconds: secondsInput ? secondsInput.value : "",
            db: dbInput ? dbInput.value : ""
          };
        });
        item.effects = effects;
      });
    }

    function persistRenderSettingsFromDom() {
      state.bedTransitionSeconds = document.getElementById("bedTransitionSeconds").value || DEFAULT_BED_TRANSITION_SECONDS;
      state.renderSettings = {
        loudness_normalize: document.getElementById("loudnessNormalize").checked,
        remove_silence: document.getElementById("removeSilence").checked,
        export_format: document.getElementById("exportFormat").value,
        sample_rate: document.getElementById("sampleRate").value,
        bit_depth: document.getElementById("bitDepth").value,
        channels: document.getElementById("channelCount").value,
        bed_transition_seconds: state.bedTransitionSeconds,
        silence_min_seconds: document.getElementById("silenceMinSeconds").value || DEFAULT_SILENCE_MIN_SECONDS,
        silence_threshold_db: document.getElementById("silenceThresholdDb").value || DEFAULT_SILENCE_THRESHOLD_DB
      };
    }

    function collectRenderPlan() {
      persistEffectsFromDom();
      persistRenderSettingsFromDom();
      const schedule = adjustedSchedule();
      return {
        kind: "autoshow-render-plan",
        version: 1,
        exported_at: new Date().toISOString(),
        settings: { ...state.renderSettings },
        sequence: state.sequence.map((item, index) => ({
          ...item,
          scheduled_start_ms: schedule.items[index]?.start_ms || 0,
          scheduled_end_ms: schedule.items[index]?.end_ms || (item.duration_ms || 0)
        })),
        total_duration_ms: schedule.totalMs
      };
    }

    function exportRenderPlan() {
      const payload = collectRenderPlan();
      downloadJson(payload, "autoshow-render-plan.json");
    }

    async function startRender() {
      const button = document.getElementById("startRenderBtn");
      button.disabled = true;
      button.textContent = "渲染中";
      showTab("export");
      updateRenderDisplay({
        status: "queued",
        progress: 0,
        elapsed_seconds: 0,
        estimated_remaining_seconds: null,
        output_path: "",
        error: ""
      });
      try {
        const response = await fetch("/api/render", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectRenderPlan())
        });
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.error || "启动渲染失败");
        renderState.taskId = payload.task.id;
        updateRenderDisplay(payload.task);
        startRenderPolling();
      } catch (error) {
        button.disabled = false;
        button.textContent = "渲染";
        document.getElementById("exportSummary").textContent = `渲染启动失败：${error.message}`;
      }
    }

    function startRenderPolling() {
      if (renderState.timer) clearInterval(renderState.timer);
      renderState.timer = setInterval(pollRenderStatus, 500);
      pollRenderStatus();
    }

    async function pollRenderStatus() {
      if (!renderState.taskId) return;
      try {
        const response = await fetch(`/api/render/status?id=${encodeURIComponent(renderState.taskId)}`);
        const payload = await response.json();
        if (!response.ok || payload.ok === false) throw new Error(payload.error || "读取渲染状态失败");
        updateRenderDisplay(payload.task);
        if (payload.task.status === "done" || payload.task.status === "error") {
          clearInterval(renderState.timer);
          renderState.timer = null;
          const button = document.getElementById("startRenderBtn");
          button.disabled = false;
          button.textContent = "渲染";
        }
      } catch (error) {
        clearInterval(renderState.timer);
        renderState.timer = null;
        document.getElementById("exportSummary").textContent = `渲染状态读取失败：${error.message}`;
      }
    }

    function updateRenderDisplay(task) {
      const progress = Math.max(0, Math.min(1, Number(task.progress) || 0));
      const percent = Math.round(progress * 100);
      document.getElementById("renderProgressBar").style.width = `${percent}%`;
      document.getElementById("renderProgressText").textContent = `${percent}%`;
      document.getElementById("renderElapsedText").textContent = formatDuration((Number(task.elapsed_seconds) || 0) * 1000);
      const remaining = task.estimated_remaining_seconds;
      document.getElementById("renderRemainingText").textContent =
        remaining === null || remaining === undefined ? "--:--" : formatDuration(Number(remaining) * 1000);
      document.getElementById("renderOutputPath").textContent = task.output_path ? `输出文件：${task.output_path}` : "";
      document.getElementById("renderSchedule").innerHTML = renderScheduleTable(task.render_schedule || []);
      const statusText = {
        queued: "渲染任务已排队。",
        running: task.stage || "正在渲染音频。",
        done: "渲染完成，已尝试打开文件和文件夹。",
        error: `渲染失败：${task.error || "未知错误"}`
      };
      document.getElementById("exportSummary").textContent = statusText[task.status] || "等待渲染任务。";
    }

    function renderScheduleTable(schedule) {
      if (!schedule.length) return "";
      return `
        <h3>最终节目时间表</h3>
        <div class="render-schedule-row render-schedule-head">
          <span>序号</span>
          <span>标题</span>
          <span>开始</span>
          <span>时长</span>
          <span>类别</span>
        </div>
        ${schedule.map((item) => `
          <div class="render-schedule-row">
            <span>${item.index}</span>
            <span>${escapeHtml(item.title || "")}</span>
            <span>${formatDuration(item.start_ms)}</span>
            <span>${formatDuration(item.duration_ms)}</span>
            <span>${escapeHtml(item.category || "")}</span>
          </div>
        `).join("")}
      `;
    }

    function applyRenderSettingsToDom(settings = {}) {
      const merged = { ...DEFAULT_RENDER_SETTINGS, ...settings };
      state.renderSettings = merged;
      state.bedTransitionSeconds = String(merged.bed_transition_seconds || DEFAULT_BED_TRANSITION_SECONDS);
      document.getElementById("loudnessNormalize").checked = Boolean(merged.loudness_normalize);
      document.getElementById("removeSilence").checked = Boolean(merged.remove_silence);
      setSelectValue("exportFormat", merged.export_format);
      setSelectValue("sampleRate", merged.sample_rate);
      setSelectValue("bitDepth", merged.bit_depth);
      setSelectValue("channelCount", merged.channels);
      document.getElementById("bedTransitionSeconds").value = state.bedTransitionSeconds;
      document.getElementById("silenceMinSeconds").value = String(merged.silence_min_seconds || DEFAULT_SILENCE_MIN_SECONDS);
      document.getElementById("silenceThresholdDb").value = String(merged.silence_threshold_db || DEFAULT_SILENCE_THRESHOLD_DB);
    }

    function setSelectValue(id, value) {
      const select = document.getElementById(id);
      select.value = [...select.options].some((option) => option.value === String(value)) ? String(value) : select.options[0].value;
    }

    function exportFinetune() {
      persistEffectsFromDom();
      const payload = {
        exported_at: new Date().toISOString(),
        kind: "autoshow-finetune-sequence",
        version: 1,
        sequence: state.sequence
      };
      downloadJson(payload, "autoshow-finetune-sequence.json");
    }

    function downloadJson(payload, filename) {
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    async function importFinetune(event) {
      const file = event.target.files[0];
      if (!file) return;
      try {
        const payload = JSON.parse(await file.text());
        const sequence = payload.sequence || payload.items;
        if (!Array.isArray(sequence)) throw new Error("文件中没有可导入的节目表。");
        state.sequence = sequence.map((item) => ({ ...item }));
        renderSequence();
        renderFinetune();
        showTab("finetune");
      } catch (error) {
        alert(`导入失败：${error.message}`);
      } finally {
        event.target.value = "";
      }
    }

    function totalDuration() {
      return state.sequence.reduce((total, item) => total + (item.duration_ms || 0), 0);
    }

    function isRepeated(item, index, counts) {
      if (item.kind === "asset") {
        const previous = state.sequence[index - 1];
        const next = state.sequence[index + 1];
        return Boolean((previous && previous.kind === "asset" && previous.path === item.path) ||
          (next && next.kind === "asset" && next.path === item.path));
      }
      return counts[item.path] > 1;
    }

    function formatDuration(ms) {
      if (!Number.isFinite(ms) || ms <= 0) return "--:--";
      const totalSeconds = Math.round(ms / 1000);
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = String(totalSeconds % 60).padStart(2, "0");
      if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${seconds}`;
      return `${minutes}:${seconds}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    async function loadSongs() {
      if (state.songs.length) return state.songs;
      const response = await fetch("/api/songs");
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "读取歌曲库失败");
      }
      state.songs = payload.songs;
      return state.songs;
    }

    async function loadAssets() {
      if (state.assets.length) return state.assets;
      const response = await fetch("/api/assets");
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "读取素材库失败");
      }
      state.assets = payload.assets;
      return state.assets;
    }

    function currentMediaItems() {
      return state.pickerKind === "song" ? state.songs : state.assets;
    }

    async function createInitialSequence(count) {
      const response = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_count: count })
      });
      const payload = await response.json();
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "生成节目单失败");
      }
      return payload.sequence;
    }

    function openAddMediaModal(kind) {
      state.pickerKind = kind;
      state.selectedMedia = [];
      const label = kind === "song" ? "歌曲" : "素材";
      document.getElementById("addMediaTitle").textContent = `添加${label}`;
      document.getElementById("mediaSearchLabel").textContent = `搜索${label}`;
      document.getElementById("addMediaModal").classList.add("open");
      document.getElementById("addMediaModal").setAttribute("aria-hidden", "false");
      document.getElementById("mediaSearch").value = "";
      document.getElementById("addMediaSummary").textContent = "";
      showMediaSelectStep();
      const loader = kind === "song" ? loadSongs : loadAssets;
      loader()
        .then(renderMediaPicker)
        .catch((error) => document.getElementById("addMediaSummary").textContent = error.message);
    }

    function closeAddMediaModal() {
      document.getElementById("addMediaModal").classList.remove("open");
      document.getElementById("addMediaModal").setAttribute("aria-hidden", "true");
    }

    function renderMediaPicker() {
      const query = document.getElementById("mediaSearch").value.trim().toLowerCase();
      const list = document.getElementById("mediaPickerList");
      const selectedPaths = new Set(state.selectedMedia.map((item) => item.path));
      const filtered = currentMediaItems().filter((item) => mediaSearchText(item).includes(query));
      if (!filtered.length) {
        list.innerHTML = '<div class="placeholder">没有匹配的项目。</div>';
        return;
      }
      list.innerHTML = filtered.map((item) => `
        <label class="song-picker-row">
          <input type="checkbox" data-media-path="${escapeHtml(item.path)}" ${selectedPaths.has(item.path) ? "checked" : ""}>
          <span>${escapeHtml(mediaPickerTitle(item))}</span>
        </label>
      `).join("");
    }

    function mediaPickerTitle(item) {
      return item.category ? `${item.category} / ${item.title}` : item.title;
    }

    function mediaSearchText(item) {
      return mediaPickerTitle(item).toLowerCase();
    }

    function syncSelectedMedia() {
      const checkedPaths = new Set(
        [...document.querySelectorAll('#mediaPickerList input[type="checkbox"]:checked')]
          .map((input) => input.dataset.mediaPath)
      );
      const previousHidden = state.selectedMedia.filter((item) => !document.querySelector(`[data-media-path="${cssEscape(item.path)}"]`));
      const visibleSelected = currentMediaItems().filter((item) => checkedPaths.has(item.path));
      state.selectedMedia = [...previousHidden, ...visibleSelected];
    }

    function cssEscape(value) {
      if (window.CSS && CSS.escape) return CSS.escape(value);
      return String(value).replace(/["\\]/g, "\\$&");
    }

    function showMediaSelectStep() {
      document.getElementById("mediaSelectStep").style.display = "";
      document.getElementById("mediaInsertStep").style.display = "none";
      document.getElementById("backToMediaSelect").style.display = "none";
      document.getElementById("nextAddMedia").style.display = "";
      document.getElementById("confirmAddMedia").style.display = "none";
    }

    function showMediaInsertStep() {
      document.getElementById("mediaSelectStep").style.display = "none";
      document.getElementById("mediaInsertStep").style.display = "";
      document.getElementById("backToMediaSelect").style.display = "";
      document.getElementById("nextAddMedia").style.display = "none";
      document.getElementById("confirmAddMedia").style.display = "";
    }

    function selectedInsertMode() {
      return document.querySelector('input[name="insertMode"]:checked').value;
    }

    function addSelectedMedia() {
      const items = state.selectedMedia.map((item) => ({ ...item }));
      const mode = selectedInsertMode();
      if (mode === "start") {
        state.sequence.unshift(...items);
      } else if (mode === "end") {
        state.sequence.push(...items);
      } else {
        const value = Number(document.getElementById("insertIndex").value);
        if (!Number.isInteger(value) || value < 1) {
          document.getElementById("addMediaSummary").textContent = "请输入有效的序号。";
          return;
        }
        const insertAt = Math.min(value - 1, state.sequence.length);
        state.sequence.splice(insertAt, 0, ...items);
      }
      state.selectedMedia = [];
      renderSequence();
      closeAddMediaModal();
    }

    document.getElementById("nextFromStart").addEventListener("click", async () => {
      const value = Number(trackCount.value);
      if (!Number.isInteger(value) || value < 1) {
        startSummary.textContent = "请输入有效的歌曲数量。";
        return;
      }
      startSummary.textContent = "";
      try {
        state.trackCount = value;
        state.sequence = await createInitialSequence(value);
        renderSequence();
        showTab("sequence");
      } catch (error) {
        startSummary.textContent = error.message;
      }
    });

    document.getElementById("addSongBtn").addEventListener("click", () => openAddMediaModal("song"));
    document.getElementById("addAssetBtn").addEventListener("click", () => openAddMediaModal("asset"));
    document.getElementById("closeAddMedia").addEventListener("click", closeAddMediaModal);
    document.getElementById("mediaSearch").addEventListener("input", () => {
      syncSelectedMedia();
      renderMediaPicker();
    });
    document.getElementById("mediaPickerList").addEventListener("change", syncSelectedMedia);
    document.getElementById("nextAddMedia").addEventListener("click", () => {
      syncSelectedMedia();
      if (!state.selectedMedia.length) {
        document.getElementById("addMediaSummary").textContent = "请至少选择一个项目。";
        return;
      }
      document.getElementById("addMediaSummary").textContent = `已选择 ${state.selectedMedia.length} 个。`;
      showMediaInsertStep();
    });
    document.getElementById("backToMediaSelect").addEventListener("click", showMediaSelectStep);
    document.getElementById("confirmAddMedia").addEventListener("click", addSelectedMedia);

    async function initialize() {
      await restoreGroupTasks(DEFAULT_GROUP_TASKS);
      await updateBatchControls();
      applyRenderSettingsToDom(DEFAULT_RENDER_SETTINGS);
      renderSequence();
      renderFinetune();
    }

    initialize();
  </script>
</body>
</html>
"""


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AutoShow GUI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2025)
    parser.add_argument("--no-open", action="store_true", help="Do not open the GUI in a browser automatically.")
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    browser_host = "127.0.0.1" if args.host in {"", "0.0.0.0"} else args.host
    url = f"http://{browser_host}:{args.port}"
    print(f"AutoShow GUI: {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/songs":
            self._send_json({"ok": True, "songs": _music_items()})
            return
        if parsed.path == "/api/assets":
            self._send_json({"ok": True, "assets": _asset_items()})
            return
        if parsed.path == "/api/render/status":
            task_id = parse_qs(parsed.query).get("id", [""])[0]
            task = _render_task_status(task_id)
            if not task:
                self._send_json({"ok": False, "error": "render task not found"}, status=404)
                return
            self._send_json({"ok": True, "task": task})
            return
        if parsed.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/render":
            try:
                plan = self._read_json()
                task = _start_render_task(plan)
                self._send_json({"ok": True, "task": task})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=400)
            return
        if parsed.path != "/api/plan":
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            track_count = int(payload.get("track_count", 0))
            if track_count < 1:
                raise ValueError("track_count must be greater than 0")
            sequence = _random_music_sequence(track_count)
            self._send_json({"ok": True, "sequence": sequence})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def _random_music_sequence(track_count: int) -> list[dict]:
    songs = _music_items()
    if len(songs) < track_count:
        raise ValueError(f"音乐数量不足：需要 {track_count} 首，当前只有 {len(songs)} 首")
    random.shuffle(songs)
    return songs[:track_count]


def _start_render_task(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("render plan must be an object")
    task_id = uuid.uuid4().hex[:12]
    export_format = str(plan.get("settings", {}).get("export_format", "mp3")).lower()
    if export_format not in {"mp3", "wav", "flac", "aac", "ogg"}:
        export_format = "mp3"
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"autoshow-render-{time.strftime('%Y%m%d-%H%M%S')}-{task_id}.{export_format}"
    task = {
        "id": task_id,
        "status": "queued",
        "progress": 0,
        "started_at": time.time(),
        "elapsed_seconds": 0,
        "estimated_remaining_seconds": None,
        "output_path": str(output_path),
        "output_dir": str(output_dir),
        "error": "",
    }
    with _RENDER_TASKS_LOCK:
        _RENDER_TASKS[task_id] = task
    thread = threading.Thread(target=_run_render_task, args=(task_id, plan, output_path), daemon=True)
    thread.start()
    return dict(task)


def _render_task_status(task_id: str) -> Optional[dict]:
    with _RENDER_TASKS_LOCK:
        task = _RENDER_TASKS.get(task_id)
        return dict(task) if task else None


def _update_render_task(task_id: str, **updates: object) -> None:
    with _RENDER_TASKS_LOCK:
        task = _RENDER_TASKS.get(task_id)
        if not task:
            return
        task.update(updates)
        elapsed = time.time() - float(task["started_at"])
        task["elapsed_seconds"] = elapsed
        progress = float(task.get("progress") or 0)
        if 0 < progress < 1:
            task["estimated_remaining_seconds"] = max(0, elapsed * (1 - progress) / progress)
        elif progress >= 1:
            task["estimated_remaining_seconds"] = 0


def _run_render_task(task_id: str, plan: dict, output_path: Path) -> None:
    try:
        _require_ffmpeg()
        _update_render_task(task_id, status="running", progress=0.01, stage="准备渲染")
        settings = _normalized_render_settings(plan.get("settings", {}))
        items = _render_items_from_plan(plan)
        with tempfile.TemporaryDirectory(prefix="autoshow-render-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            processed_items = _preprocess_render_items(task_id, items, settings, temp_dir)
            scheduled_items, total_duration_ms = _schedule_render_items(processed_items)
            _update_render_task(task_id, render_schedule=_render_schedule_payload(scheduled_items))
            _mix_render_items(task_id, scheduled_items, total_duration_ms, settings, output_path)
        _update_render_task(task_id, status="done", progress=1, completed_at=time.time())
        _open_render_outputs(output_path)
    except Exception as exc:
        _update_render_task(task_id, status="error", error=str(exc))


def _require_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("找不到 ffmpeg/ffprobe，请先安装 ffmpeg。") from exc


def _normalized_render_settings(raw: object) -> dict:
    settings = raw if isinstance(raw, dict) else {}
    export_format = str(settings.get("export_format", "mp3")).lower()
    if export_format not in {"mp3", "wav", "flac", "aac", "ogg"}:
        export_format = "mp3"
    sample_rate = _allowed_int(settings.get("sample_rate"), 44100, {44100, 48000, 96000})
    channels = _allowed_int(settings.get("channels"), 2, {1, 2})
    bit_depth = str(settings.get("bit_depth", "32f"))
    if bit_depth not in {"32f", "24", "16"}:
        bit_depth = "32f"
    silence_threshold_db = _float_value(settings.get("silence_threshold_db"), -20)
    if silence_threshold_db > 0:
        silence_threshold_db = -silence_threshold_db
    silence_threshold_db = max(-100, min(0, silence_threshold_db))
    return {
        "loudness_normalize": bool(settings.get("loudness_normalize", True)),
        "remove_silence": bool(settings.get("remove_silence", True)),
        "export_format": export_format,
        "sample_rate": sample_rate,
        "channels": channels,
        "bit_depth": bit_depth,
        "bed_transition_seconds": max(0, _float_value(settings.get("bed_transition_seconds"), 0.5)),
        "silence_min_seconds": max(0.01, _float_value(settings.get("silence_min_seconds"), 0.2)),
        "silence_threshold_db": silence_threshold_db,
    }


def _render_items_from_plan(plan: dict) -> list[dict]:
    sequence = plan.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        raise ValueError("节目单为空，无法渲染。")
    items = []
    for index, raw_item in enumerate(sequence):
        if not isinstance(raw_item, dict):
            raise ValueError(f"节目单第 {index + 1} 项无效。")
        relative_path = str(raw_item.get("path") or "")
        input_path = (ROOT / relative_path).resolve()
        try:
            input_path.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError(f"节目单第 {index + 1} 项路径不在项目目录内。") from exc
        if not input_path.is_file():
            raise FileNotFoundError(f"找不到音频文件：{relative_path}")
        duration_ms = _int_value(raw_item.get("duration_ms"), _duration_ms(input_path))
        if duration_ms <= 0:
            duration_ms = _duration_ms(input_path)
        items.append(
            {
                "index": index,
                "title": str(raw_item.get("title") or input_path.stem),
                "kind": str(raw_item.get("kind") or ""),
                "category": str(raw_item.get("category") or ""),
                "path": relative_path,
                "input_path": input_path,
                "duration_ms": max(1, duration_ms),
                "effects": raw_item.get("effects") if isinstance(raw_item.get("effects"), dict) else {},
            }
        )
    return items


def _preprocess_render_items(task_id: str, items: list[dict], settings: dict, temp_dir: Path) -> list[dict]:
    processed = []
    total = len(items)
    for index, item in enumerate(items):
        progress = 0.02 + (index / max(1, total)) * 0.62
        _update_render_task(
            task_id,
            progress=progress,
            stage=f"预处理 {index + 1}/{total}",
        )
        output_path = temp_dir / f"clip-{index:04d}.wav"
        _preprocess_one_item(item, output_path, settings)
        actual_duration_ms = _duration_ms(output_path)
        if actual_duration_ms <= 0 and settings["remove_silence"]:
            fallback_settings = {**settings, "remove_silence": False}
            _preprocess_one_item(item, output_path, fallback_settings)
            actual_duration_ms = _duration_ms(output_path)
        if actual_duration_ms <= 0:
            raise RuntimeError(f"预处理后音频为空：{item['title']}")
        processed.append(
            {
                **item,
                "processed_path": output_path,
                "duration_ms": actual_duration_ms,
            }
        )
    _update_render_task(task_id, progress=0.66, stage="预处理完成")
    return processed


def _preprocess_one_item(item: dict, output_path: Path, settings: dict) -> None:
    base_filters = _preprocess_base_filters(
        item,
        settings["remove_silence"],
        settings["silence_min_seconds"],
        settings["silence_threshold_db"],
    )
    filters = list(base_filters)
    if settings["loudness_normalize"]:
        measured = _measure_loudness(item["input_path"], base_filters)
        filters.append(_loudnorm_filter(measured))
    filters.extend(
        [
            f"aresample={settings['sample_rate']}",
            f"aformat=channel_layouts={_channel_layout(settings['channels'])}",
        ]
    )
    args = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(item["input_path"]),
        "-vn",
        "-af",
        ",".join(filters),
        "-ar",
        str(settings["sample_rate"]),
        "-ac",
        str(settings["channels"]),
        "-c:a",
        _wav_codec(settings["bit_depth"]),
        str(output_path),
    ]
    _run_checked(args, f"预处理失败：{item['title']}")


def _preprocess_base_filters(
    item: dict,
    remove_silence: bool,
    silence_min_seconds: float,
    silence_threshold_db: float,
) -> list[str]:
    duration_seconds = max(0.001, item["duration_ms"] / 1000)
    trim_start, trim_end = (0.0, duration_seconds)
    if remove_silence:
        trim_start, trim_end = _edge_trim_bounds(
            item["input_path"],
            duration_seconds,
            silence_min_seconds,
            silence_threshold_db,
        )
    filters = [
        f"atrim=start={_fmt(trim_start)}:end={_fmt(trim_end)}",
        "asetpts=PTS-STARTPTS",
    ]
    return filters


def _edge_trim_bounds(
    input_path: Path,
    duration_seconds: float,
    silence_min_seconds: float,
    silence_threshold_db: float,
) -> tuple[float, float]:
    samples = _edge_analysis_samples(input_path, duration_seconds)
    if not samples:
        return 0.0, duration_seconds
    threshold = math.pow(10, silence_threshold_db / 20)
    window_size = max(1, int(EDGE_ANALYSIS_SAMPLE_RATE * EDGE_ANALYSIS_WINDOW_SECONDS))
    first_sound: Optional[int] = None
    last_sound: Optional[int] = None
    for start in range(0, len(samples), window_size):
        window = samples[start : start + window_size]
        if any(abs(sample) > threshold for sample in window):
            if first_sound is None:
                first_sound = start
            last_sound = min(len(samples), start + len(window))
    if first_sound is None or last_sound is None:
        return 0.0, duration_seconds
    detected_start = first_sound / EDGE_ANALYSIS_SAMPLE_RATE
    detected_end = min(duration_seconds, last_sound / EDGE_ANALYSIS_SAMPLE_RATE)
    trim_start = detected_start if detected_start >= silence_min_seconds else 0.0
    trim_end = detected_end if duration_seconds - detected_end >= silence_min_seconds else duration_seconds
    if trim_end - trim_start < 0.001:
        return 0.0, duration_seconds
    return trim_start, trim_end


def _edge_analysis_samples(input_path: Path, duration_seconds: float) -> array.array:
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vn",
        "-t",
        _fmt(duration_seconds),
        "-ac",
        "1",
        "-ar",
        str(EDGE_ANALYSIS_SAMPLE_RATE),
        "-f",
        "f32le",
        "-",
    ]
    try:
        result = subprocess.run(args, capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return array.array("f")
    samples = array.array("f")
    samples.frombytes(result.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _measure_loudness(input_path: Path, base_filters: list[str]) -> Optional[dict]:
    args = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        ",".join([*base_filters, "loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json"]),
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(args, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError:
        return None
    return _extract_loudnorm_json(result.stderr)


def _extract_loudnorm_json(stderr: str) -> Optional[dict]:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None
    required = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    if not required.issubset(payload):
        return None
    for key in required:
        if not math.isfinite(_float_value(payload.get(key), math.nan)):
            return None
    return payload


def _loudnorm_filter(measured: Optional[dict]) -> str:
    if not measured:
        return "loudnorm=I=-16:LRA=11:TP=-1.5"
    return (
        "loudnorm=I=-16:LRA=11:TP=-1.5:"
        f"measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:"
        "linear=true:print_format=summary"
    )


def _schedule_render_items(items: list[dict]) -> tuple[list[dict], int]:
    scheduled = []
    cursor_ms = 0
    for index, item in enumerate(items):
        overlap_ms = 0 if index == 0 else _overlap_before_ms(items[index - 1], item)
        overlap_ms = min(overlap_ms, cursor_ms, item["duration_ms"])
        start_ms = max(0, cursor_ms - overlap_ms)
        end_ms = start_ms + item["duration_ms"]
        scheduled.append({**item, "scheduled_start_ms": start_ms, "scheduled_end_ms": end_ms})
        cursor_ms = max(cursor_ms, end_ms)
    return scheduled, cursor_ms


def _render_schedule_payload(items: list[dict]) -> list[dict]:
    return [
        {
            "index": index + 1,
            "title": item.get("title") or item.get("path") or "",
            "start_ms": item["scheduled_start_ms"],
            "duration_ms": item["duration_ms"],
            "category": (item.get("category") or "General") if item.get("kind") == "asset" else "歌曲",
        }
        for index, item in enumerate(items)
    ]


def _overlap_before_ms(previous: dict, current: dict) -> int:
    seconds = max(
        _effect_seconds(current, "bed_in"),
        _effect_seconds(current, "cross_in"),
        _effect_seconds(previous, "bed_out"),
        _effect_seconds(previous, "cross_out"),
    )
    return int(round(seconds * 1000))


def _mix_render_items(
    task_id: str,
    items: list[dict],
    total_duration_ms: int,
    settings: dict,
    output_path: Path,
) -> None:
    _update_render_task(task_id, progress=0.68, stage="拼接节目")
    filter_complex = _mix_filter_complex(items, total_duration_ms, settings)
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1"]
    for item in items:
        args.extend(["-i", str(item["processed_path"])])
    args.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-ar",
            str(settings["sample_rate"]),
            "-ac",
            str(settings["channels"]),
            *_output_format_args(settings),
            str(output_path),
        ]
    )
    _run_ffmpeg_with_progress(task_id, args, total_duration_ms)
    _update_render_task(task_id, progress=0.99, stage="整理输出")


def _mix_filter_complex(items: list[dict], total_duration_ms: int, settings: dict) -> str:
    chains = []
    labels = []
    for input_index, item in enumerate(items):
        label = f"a{input_index}"
        labels.append(f"[{label}]")
        filters = [
            "asetpts=PTS-STARTPTS",
            f"atrim=start=0:end={_fmt(item['duration_ms'] / 1000)}",
            f"aformat=channel_layouts={_channel_layout(settings['channels'])}",
        ]
        volume_expression = _volume_expression(item, settings["bed_transition_seconds"])
        if volume_expression != "1":
            filters.append(f"volume=eval=frame:volume='{volume_expression}'")
        if item["scheduled_start_ms"] > 0:
            filters.append(f"adelay={item['scheduled_start_ms']}:all=1")
        chains.append(f"[{input_index}:a]{','.join(filters)}[{label}]")
    total_seconds = max(0.001, total_duration_ms / 1000)
    if len(items) == 1:
        chains.append(f"{labels[0]}atrim=start=0:end={_fmt(total_seconds)},asetpts=PTS-STARTPTS[out]")
    else:
        chains.append(
            "".join(labels)
            + f"amix=inputs={len(items)}:duration=longest:dropout_transition=0:normalize=0,"
            + f"atrim=start=0:end={_fmt(total_seconds)},asetpts=PTS-STARTPTS[out]"
        )
    return ";".join(chains)


def _volume_expression(item: dict, bed_transition_seconds: float) -> str:
    duration_seconds = max(0.001, item["duration_ms"] / 1000)
    expressions = []
    for kind in ("fade_in", "cross_in"):
        seconds = min(_effect_seconds(item, kind), duration_seconds)
        if seconds > 0:
            expressions.append(f"if(lt(t,{_fmt(seconds)}),t/{_fmt(seconds)},1)")
    for kind in ("fade_out", "cross_out"):
        seconds = min(_effect_seconds(item, kind), duration_seconds)
        if seconds > 0:
            start = max(0, duration_seconds - seconds)
            expressions.append(
                f"if(lt(t,{_fmt(start)}),1,if(lt(t,{_fmt(duration_seconds)}),"
                f"({_fmt(duration_seconds)}-t)/{_fmt(seconds)},0))"
            )
    bed_in_seconds = min(_effect_seconds(item, "bed_in"), duration_seconds)
    if bed_in_seconds > 0:
        expressions.append(
            _bed_in_expression(
                bed_in_seconds,
                _effect_gain(item, "bed_in"),
                bed_transition_seconds,
            )
        )
    bed_out_seconds = min(_effect_seconds(item, "bed_out"), duration_seconds)
    if bed_out_seconds > 0:
        expressions.append(
            _bed_out_expression(
                duration_seconds,
                bed_out_seconds,
                _effect_gain(item, "bed_out"),
                bed_transition_seconds,
            )
        )
    if not expressions:
        return "1"
    return "*".join(f"({expression})" for expression in expressions)


def _bed_in_expression(seconds: float, gain: float, transition_seconds: float) -> str:
    transition = min(max(0, transition_seconds), seconds / 2)
    if transition <= 0:
        return f"if(lt(t,{_fmt(seconds)}),{_fmt(gain)},1)"
    hold_until = max(transition, seconds - transition)
    return (
        f"if(lt(t,{_fmt(transition)}),{_fmt(gain)}*(t/{_fmt(transition)}),"
        f"if(lt(t,{_fmt(hold_until)}),{_fmt(gain)},"
        f"if(lt(t,{_fmt(seconds)}),"
        f"{_fmt(gain)}+(1-{_fmt(gain)})*((t-{_fmt(hold_until)})/{_fmt(transition)}),1)))"
    )


def _bed_out_expression(duration_seconds: float, seconds: float, gain: float, transition_seconds: float) -> str:
    start = max(0, duration_seconds - seconds)
    transition = min(max(0, transition_seconds), seconds)
    if transition <= 0:
        return f"if(lt(t,{_fmt(start)}),1,{_fmt(gain)})"
    down_end = min(duration_seconds, start + transition)
    return (
        f"if(lt(t,{_fmt(start)}),1,"
        f"if(lt(t,{_fmt(down_end)}),"
        f"1+({_fmt(gain)}-1)*((t-{_fmt(start)})/{_fmt(transition)}),"
        f"{_fmt(gain)}))"
    )


def _effect_seconds(item: dict, kind: str) -> float:
    effect = item.get("effects", {}).get(kind)
    if not isinstance(effect, dict) or not effect.get("enabled"):
        return 0
    return max(0, _float_value(effect.get("seconds"), 3))


def _effect_gain(item: dict, kind: str) -> float:
    effect = item.get("effects", {}).get(kind)
    db = abs(_float_value(effect.get("db") if isinstance(effect, dict) else None, 8))
    return max(0, min(1, math.pow(10, -db / 20)))


def _output_format_args(settings: dict) -> list[str]:
    export_format = settings["export_format"]
    if export_format == "wav":
        return ["-c:a", _wav_codec(settings["bit_depth"])]
    if export_format == "flac":
        return ["-c:a", "flac"]
    if export_format == "aac":
        return ["-c:a", "aac", "-b:a", "256k"]
    if export_format == "ogg":
        return ["-c:a", "vorbis", "-q:a", "6", "-strict", "-2"]
    return ["-c:a", "libmp3lame", "-b:a", "320k"]


def _run_checked(args: list[str], message: str) -> None:
    try:
        subprocess.run(args, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if len(detail) > 1200:
            detail = detail[-1200:]
        raise RuntimeError(f"{message}\n{detail}") from exc


def _run_ffmpeg_with_progress(task_id: str, args: list[str], total_duration_ms: int) -> None:
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    total_us = max(1, total_duration_ms * 1000)
    assert process.stdout is not None
    for line in process.stdout:
        key, _, value = line.strip().partition("=")
        if key != "out_time_ms":
            continue
        out_time_us = _int_value(value, 0)
        mix_progress = max(0, min(1, out_time_us / total_us))
        _update_render_task(task_id, progress=0.70 + mix_progress * 0.27, stage="导出音频")
    stderr = process.stderr.read() if process.stderr else ""
    return_code = process.wait()
    if return_code != 0:
        detail = stderr.strip()
        if len(detail) > 1600:
            detail = detail[-1600:]
        raise RuntimeError(f"音频拼接失败。\n{detail}")


def _allowed_int(value: object, fallback: int, allowed: set[int]) -> int:
    number = _int_value(value, fallback)
    return number if number in allowed else fallback


def _int_value(value: object, fallback: int) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return fallback


def _float_value(value: object, fallback: float) -> float:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _channel_layout(channels: int) -> str:
    return "mono" if channels == 1 else "stereo"


def _wav_codec(bit_depth: str) -> str:
    if bit_depth == "16":
        return "pcm_s16le"
    if bit_depth == "24":
        return "pcm_s24le"
    return "pcm_f32le"


def _open_render_outputs(output_path: Path) -> None:
    try:
        subprocess.Popen(["open", str(output_path)])
        subprocess.Popen(["open", str(output_path.parent)])
    except OSError:
        pass


def _music_items() -> list[dict]:
    music_dir = ROOT / "media" / "music"
    return _cached_media_items(
        "music",
        music_dir,
        lambda path: _song_item(path),
    )


def _asset_items() -> list[dict]:
    assets_dir = ROOT / "media" / "assets"
    return _cached_media_items(
        "assets",
        assets_dir,
        lambda path: _asset_item(path, assets_dir),
    )


def _cached_media_items(cache_key: str, directory: Path, build_item) -> list[dict]:
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    signature = tuple(
        (str(path.relative_to(ROOT)), path.stat().st_mtime_ns, path.stat().st_size)
        for path in files
    )
    cached = _MEDIA_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return [dict(item) for item in cached[1]]
    items = [build_item(path) for path in files]
    _MEDIA_CACHE[cache_key] = (signature, items)
    return [dict(item) for item in items]


def _song_item(path: Path) -> dict:
    return {
        "kind": "song",
        "title": _display_title(path),
        "filename": path.name,
        "path": str(path.relative_to(ROOT)),
        "duration_ms": _duration_ms(path),
    }


def _asset_item(path: Path, assets_dir: Path) -> dict:
    relative = path.relative_to(assets_dir)
    category = relative.parts[0] if len(relative.parts) > 1 else "General"
    return {
        "kind": "asset",
        "title": path.stem,
        "filename": path.name,
        "category": category,
        "path": str(path.relative_to(ROOT)),
        "duration_ms": _duration_ms(path),
    }


def _display_title(path: Path) -> str:
    return TRACK_NUMBER_PREFIX.sub("", path.stem)


def _duration_ms(path: Path) -> int:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        return int(float(result.stdout.strip()) * 1000)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0
