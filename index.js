<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>דה קוקי</title>
    <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Rubik:wght@400;600;700;900&display=swap" rel="stylesheet">
    <script src="./js/index.js"></script>
    <script src="./js/dekuki_enhanced.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --yellow: #f5c200;
            --yellow-bright: #ffd700;
            --yellow-dark: #b8860b;
            --yellow-glow: rgba(245,194,0,0.35);
            --black: #0a0a0a;
            --black2: #141414;
            --black3: #1a1a1a;
            --black4: #222;
            --grey: #444;
            --grey2: #666;
            --light: #ddd;
            --white: #f5f5f5;
        }

        body {
            font-family: 'Rubik', sans-serif;
            background: var(--black);
            color: var(--light);
            padding: 0;
            min-height: 100vh;
            overflow-y: auto;
            -webkit-font-smoothing: antialiased;
        }

        /* ===== HEADER ===== */
        .deco-header {
            background: linear-gradient(180deg, #1a1400 0%, #0a0a0a 100%);
            border-bottom: 2px solid var(--yellow-dark);
            padding: 10px 12px 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            position: relative;
            overflow: hidden;
        }

        .deco-header::before {
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: repeating-linear-gradient(
                90deg,
                transparent,
                transparent 40px,
                rgba(180,140,0,0.04) 40px,
                rgba(180,140,0,0.04) 41px
            );
            pointer-events: none;
        }

        .deco-header::after {
            content: "";
            position: absolute;
            bottom: 0;
            left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--yellow), transparent);
        }

        .header-avatar {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            border: 2.5px solid var(--yellow);
            object-fit: cover;
            flex-shrink: 0;
            box-shadow: 0 0 12px var(--yellow-glow), 0 0 30px rgba(200,160,0,0.15);
        }

        .header-text {
            flex: 1;
        }

        .header-title {
            font-family: 'Bebas Neue', sans-serif;
            font-size: 28px;
            letter-spacing: 3px;
            color: var(--white);
            line-height: 1;
            text-shadow: 0 0 20px var(--yellow-glow), 0 2px 4px #000;
        }

        .header-title span {
            color: var(--yellow-bright);
        }

        .header-by {
            font-size: 9px;
            color: var(--grey2);
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-top: 2px;
        }

        .header-by strong {
            color: var(--yellow);
            font-weight: 700;
        }

        .header-badge {
            font-size: 8px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--yellow-bright);
            border: 1px solid var(--yellow-dark);
            background: rgba(140,110,0,0.15);
            padding: 2px 6px;
            border-radius: 3px;
        }

        /* ===== MAIN ===== */
        .main-screen { max-width: 500px; margin: 0 auto; display: flex; flex-direction: column; min-height: 100vh; }
        .content-wrapper { flex: 1; padding: 10px 10px 0; animation: fadeIn .5s ease-out; }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        /* ===== TABS ===== */
        .tab-navigation {
            display: flex;
            gap: 3px;
            margin-bottom: 8px;
            background: var(--black3);
            border: 1px solid rgba(180,140,0,0.25);
            border-radius: 8px;
            padding: 4px;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .tab-btn {
            flex: 1;
            height: 26px;
            background: transparent;
            border: none;
            border-radius: 5px;
            color: var(--grey2);
            font-family: 'Rubik', sans-serif;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            transition: all .25s ease;
            letter-spacing: .5px;
            text-transform: uppercase;
        }

        .tab-btn:hover { color: var(--white); background: rgba(220,176,0,0.1); }

        .tab-btn.active {
            background: linear-gradient(135deg, var(--yellow-dark), var(--yellow));
            color: #fff;
            box-shadow: 0 2px 10px rgba(180,140,0,0.5);
        }

        .tab-content { display: none; animation: fadeIn .3s ease-out; }
        .tab-content.active { display: block; }

        /* ===== TOGGLE ROW ===== */
        .layer-mode-toggle {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 5px 10px;
            background: var(--black3);
            border: 1px solid rgba(180,140,0,0.2);
            border-radius: 8px;
            margin-bottom: 6px;
        }

        .toggle-label { font-size: 10px; font-weight: 700; color: var(--grey2); user-select: none; text-transform: uppercase; letter-spacing: .5px; }

        .toggle-switch { position: relative; width: 40px; height: 20px; cursor: pointer; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }

        .toggle-slider {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(200,160,0,0.15);
            border: 1px solid rgba(200,160,0,0.3);
            border-radius: 24px;
            transition: all .3s ease;
        }

        .toggle-slider:before {
            content: "";
            position: absolute;
            height: 14px; width: 14px;
            left: 2px; bottom: 2px;
            background: linear-gradient(135deg, #ffd700, #c8960b);
            border-radius: 50%;
            transition: all .3s ease;
            box-shadow: 0 0 6px rgba(220,176,0,0.5);
        }

        .toggle-switch input:checked + .toggle-slider { background: rgba(200,160,0,0.25); border-color: var(--yellow-dark); }
        .toggle-switch input:checked + .toggle-slider:before { transform: translate(20px); }

        .toggle-divider { width: 1px; height: 16px; background: rgba(180,140,0,0.3); margin: 0 4px; }

        .precomp-toggle { display: flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; }
        .precomp-toggle input { display: none; }

        .precomp-checkbox {
            width: 14px; height: 14px;
            border: 1.5px solid rgba(200,160,0,0.35);
            border-radius: 3px;
            background: rgba(200,160,0,0.08);
            transition: all .2s ease;
            position: relative; flex-shrink: 0;
        }

        .precomp-toggle input:checked + .precomp-checkbox {
            background: linear-gradient(135deg, #c8960b, var(--yellow-bright));
            border-color: var(--yellow);
        }

        .precomp-toggle input:checked + .precomp-checkbox:after {
            content: "";
            position: absolute;
            left: 3px; top: 0;
            width: 5px; height: 9px;
            border: solid white; border-width: 0 1.5px 1.5px 0;
            transform: rotate(45deg);
        }

        .precomp-label { font-size: 10px; font-weight: 700; color: var(--grey2); transition: color .2s; text-transform: uppercase; letter-spacing: .4px; }
        .precomp-toggle input:checked ~ .precomp-label { color: var(--yellow-bright); }

        /* ===== PICKERS ===== */
        .font-picker {
            background: var(--black3);
            border: 1px solid rgba(180,140,0,0.2);
            border-radius: 8px;
            margin-bottom: 5px;
            overflow: hidden;
            transition: border-color .25s ease;
        }

        .font-picker.is-open { border-color: rgba(220,176,0,0.5); }

        .font-picker-header {
            display: flex; align-items: center; gap: 6px;
            padding: 5px 9px; width: 100%; background: transparent;
            border: none; color: inherit; cursor: pointer;
            font-family: inherit; text-align: left; transition: background .15s;
        }

        .font-picker-header:hover { background: rgba(220,176,0,0.08); }
        .font-picker.is-open .font-picker-header { background: rgba(220,176,0,0.12); border-bottom: 1px solid rgba(255,255,255,.05); }

        .font-picker-icon { color: var(--yellow); opacity: .8; flex-shrink: 0; }
        .font-picker-header-label { font-size: 10px; font-weight: 700; color: rgba(255,255,255,.5); flex-shrink: 0; text-transform: uppercase; letter-spacing: .5px; }
        .font-picker-header-divider { color: rgba(255,255,255,.2); font-size: 10px; flex-shrink: 0; }
        .font-picker-header-preview { font-size: 13px; font-weight: 700; color: #fff; min-width: 22px; text-align: center; flex-shrink: 0; }
        .font-picker-header-preview[hidden] { display: none; }
        .font-picker-header-name { flex: 1; font-size: 11px; color: var(--light); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }

        .font-picker-clear {
            width: 18px; height: 18px; background: rgba(255,255,255,.08);
            border: 1px solid rgba(255,255,255,.1); border-radius: 4px;
            color: rgba(255,255,255,.4); font-size: 12px; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: all .15s; flex-shrink: 0; padding: 0;
        }

        .font-picker-clear[hidden] { display: none; }
        .font-picker-clear:hover { background: rgba(220,176,0,0.2); border-color: rgba(220,176,0,0.5); color: var(--yellow-bright); }

        .font-picker-chevron { color: rgba(255,255,255,.35); flex-shrink: 0; transition: transform .25s ease; }
        .font-picker.is-open .font-picker-chevron { transform: rotate(180deg); color: var(--yellow); }

        .font-picker-body { display: none; animation: fontPickerSlideDown .2s ease; }
        .font-picker.is-open .font-picker-body { display: block; }

        @keyframes fontPickerSlideDown {
            from { opacity: 0; transform: translateY(-4px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .font-picker-search {
            width: 100%; background: rgba(255,255,255,.05); border: none;
            border-bottom: 1px solid rgba(255,255,255,.06); color: #fff;
            font-size: 11px; padding: 7px 10px; outline: none; font-family: inherit;
        }

        .font-picker-search::placeholder { color: rgba(255,255,255,.3); font-style: italic; }
        .font-picker-search:focus { background: rgba(220,176,0,0.06); }

        .font-picker-list { max-height: 180px; overflow-y: auto; padding: 4px; }
        .font-picker-list::-webkit-scrollbar { width: 5px; }
        .font-picker-list::-webkit-scrollbar-track { background: transparent; }
        .font-picker-list::-webkit-scrollbar-thumb { background: rgba(200,160,0,0.3); border-radius: 3px; }
        .font-picker-list::-webkit-scrollbar-thumb:hover { background: var(--yellow-dark); }

        .font-picker-item { display: flex; align-items: center; gap: 10px; padding: 6px 8px; border-radius: 5px; color: var(--light); font-size: 11px; cursor: pointer; transition: background .15s; user-select: none; }
        .font-picker-item[hidden] { display: none; }
        .font-picker-item:hover { background: rgba(200,160,0,0.12); }
        .font-picker-item.selected { background: rgba(200,160,0,0.2); color: #ffdc50; }
        .font-picker-item.is-default { color: var(--grey2); font-style: italic; }
        .font-picker-item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .font-picker-item-sample { flex-shrink: 0; max-width: 45%; font-size: 13px; color: rgba(255,255,255,.7); text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1; }
        .font-picker-item.selected .font-picker-item-sample { color: #ffdc50; }
        .font-picker-item-check { color: transparent; font-size: 12px; flex-shrink: 0; width: 12px; margin-left: 4px; }
        .font-picker-item.selected .font-picker-item-check { color: var(--yellow-bright); }

        .lang-picker { margin-top: 0; }
        .font-picker-item-code { flex-shrink: 0; font-size: 9px; color: rgba(255,255,255,.35); text-transform: uppercase; font-weight: 700; padding-left: 8px; margin-right: 4px; letter-spacing: .5px; }
        .font-picker-item.selected .font-picker-item-code { color: #ffdc50; }

        /* ===== POSITION TOGGLE ===== */
        .position-toggle {
            display: flex; align-items: center; gap: 8px;
            padding: 5px 9px; background: var(--black3);
            border: 1px solid rgba(180,140,0,0.2); border-radius: 8px;
            margin-bottom: 6px;
        }

        .position-toggle-label { display: flex; align-items: center; gap: 6px; font-size: 10px; font-weight: 700; color: rgba(255,255,255,.45); flex-shrink: 0; text-transform: uppercase; letter-spacing: .5px; }
        .position-toggle-label svg { color: var(--yellow); opacity: .7; }

        .position-toggle-buttons { display: flex; flex: 1; gap: 4px; background: rgba(0,0,0,.3); border-radius: 5px; padding: 2px; }

        .position-toggle-btn {
            flex: 1; background: transparent; border: none; color: rgba(255,255,255,.5);
            font-size: 10px; font-weight: 700; padding: 4px 8px; border-radius: 4px;
            cursor: pointer; transition: all .15s; font-family: inherit; text-transform: uppercase; letter-spacing: .4px;
        }

        .position-toggle-btn:hover { color: #fff; background: rgba(200,160,0,0.12); }
        .position-toggle-btn.active { background: rgba(200,160,0,0.25); color: #ffdc50; }

        /* ===== ACTION CARDS ===== */
        .action-cards { display: flex; flex-direction: column; gap: 3px; margin-bottom: 5px; }

        .action-card {
            position: relative;
            background: var(--black3);
            border: 1px solid rgba(180,140,0,0.2);
            border-radius: 8px;
            padding: 6px 10px;
            cursor: pointer;
            transition: all .3s ease;
            overflow: hidden;
            min-height: 40px;
            display: flex; align-items: center; gap: 8px;
        }

        .card-bg-gradient { position: absolute; top: 0; left: 0; right: 0; bottom: 0; opacity: 0; transition: opacity .4s; z-index: 0; }

        .words-gradient       { background: linear-gradient(135deg, rgba(180,140,0,0.3), rgba(100,0,0,0.2)); }
        .wordpairs-gradient   { background: linear-gradient(135deg, rgba(160,120,0,0.3), rgba(80,0,0,0.2)); }
        .sentences-gradient   { background: linear-gradient(135deg, rgba(200,160,0,0.3), rgba(120,0,0,0.2)); }
        .smartextended-gradient { background: linear-gradient(135deg, rgba(170,0,0,0.3), rgba(90,0,0,0.2)); }
        .smartwords-gradient  { background: linear-gradient(135deg, rgba(190,0,0,0.3), rgba(110,0,0,0.2)); }
        .timeline-gradient    { background: linear-gradient(135deg, rgba(150,0,0,0.3), rgba(70,0,0,0.2)); }

        .action-card:hover { transform: translateY(-2px); border-color: rgba(220,176,0,0.5); box-shadow: 0 6px 20px rgba(180,140,0,0.25); }
        .action-card:hover .card-bg-gradient { opacity: 1; }
        .action-card:active { transform: translateY(-1px) scale(1.01); }

        .card-icon-modern {
            flex-shrink: 0; width: 26px; height: 26px;
            background: rgba(200,160,0,0.2); border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            position: relative; z-index: 1; transition: all .3s;
        }

        .card-icon-modern svg { width: 14px; height: 14px; }
        .action-card:hover .card-icon-modern { background: rgba(220,176,0,0.35); transform: scale(1.1) rotate(5deg); }

        .card-content { flex: 1; position: relative; z-index: 1; }
        .card-content h3 { font-size: 11px; font-weight: 800; color: #fff; margin-bottom: 0; letter-spacing: .3px; text-transform: uppercase; }
        .card-content p { font-size: 9px; color: var(--grey2); line-height: 1.3; }
        .card-badge { display: none; }

        .card-progress {
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(10,10,10,0.95); border-radius: 8px;
            display: none; flex-direction: column; align-items: center; justify-content: center;
            gap: 8px; font-size: 11px; font-weight: 700; color: var(--yellow); z-index: 10;
            animation: fadeInProgress .3s ease-out;
        }

        .card-progress:before {
            content: ""; width: 22px; height: 22px;
            border: 2px solid rgba(200,160,0,0.2); border-top-color: var(--yellow);
            border-radius: 50%; animation: spin .7s linear infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeInProgress { from { opacity: 0; transform: scale(.95); } to { opacity: 1; transform: scale(1); } }

        .action-card.processing .card-progress { display: flex; }
        .action-card.processing { pointer-events: none; }
        .action-card.processing .card-icon-modern,
        .action-card.processing .card-content { opacity: .3; }
        .action-card.disabled { opacity: .5; pointer-events: none; }

        /* ===== TOOLS TOOLBAR ===== */
        .tools-toolbar { display: flex; gap: 4px; margin-top: 4px; margin-bottom: 3px; }

        .tool-btn {
            flex: 1; display: flex; align-items: center; justify-content: center; gap: 4px;
            padding: 5px 6px; border-radius: 6px; font-size: 10px; font-weight: 700;
            cursor: pointer; transition: all .2s ease; border: 1px solid;
            font-family: inherit; white-space: nowrap; letter-spacing: .3px; text-transform: uppercase;
        }

        .tool-btn svg { flex-shrink: 0; opacity: .85; }
        .tool-btn:hover { transform: translateY(-1px); }
        .tool-btn:active { transform: translateY(0); }
        .tool-btn:disabled { opacity: .4; cursor: not-allowed; transform: none !important; }

        .tool-select { background: rgba(180,140,0,0.1); border-color: rgba(180,140,0,0.3); color: #ffdc50; }
        .tool-select:hover:not(:disabled) { background: rgba(200,160,0,0.2); border-color: var(--yellow); box-shadow: 0 2px 8px rgba(180,140,0,0.25); }

        .tool-punctuation { background: rgba(180,80,0,0.1); border-color: rgba(180,80,0,0.3); color: #ff9966; }
        .tool-punctuation:hover:not(:disabled) { background: rgba(200,80,0,0.2); border-color: rgba(220,100,0,0.7); }

        .tool-delete { background: rgba(100,0,0,0.1); border-color: rgba(150,0,0,0.3); color: #ff4444; }
        .tool-delete:hover:not(:disabled) { background: rgba(180,140,0,0.25); border-color: var(--yellow-bright); box-shadow: 0 2px 8px rgba(200,160,0,0.3); }

        /* ===== SRT TOOLBAR ===== */
        .srt-toolbar { display: flex; gap: 4px; margin-top: 0; margin-bottom: 5px; }

        .srt-btn {
            flex: 1; display: flex; align-items: center; justify-content: center; gap: 4px;
            padding: 4px 6px; border-radius: 7px; font-size: 10px; font-weight: 700;
            cursor: pointer; transition: all .2s ease; border: 1px solid;
            font-family: inherit; white-space: nowrap; letter-spacing: .3px; text-transform: uppercase;
        }

        .srt-import { background: rgba(150,0,0,0.08); border-color: rgba(180,140,0,0.25); color: #ff7070; }
        .srt-import:hover:not(:disabled) { background: rgba(180,140,0,0.18); border-color: rgba(220,176,0,0.6); }

        .srt-export { background: rgba(100,0,0,0.08); border-color: rgba(150,0,0,0.25); color: #ff5555; }
        .srt-export:hover:not(:disabled) { background: rgba(160,120,0,0.18); border-color: rgba(200,160,0,0.6); }

        /* ===== PROGRESS & STATUS ===== */
        .progress-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
        .progress-row[hidden] { display: none; }

        .progress-wrapper {
            flex: 1; background: rgba(180,140,0,0.1); border: 1px solid rgba(180,140,0,0.2);
            border-radius: 8px; height: 6px; overflow: hidden;
        }

        .progress-bar-modern {
            height: 100%; width: 0%; background: linear-gradient(90deg, #8b0000, var(--yellow-bright));
            transition: width .3s ease; position: relative; overflow: hidden;
        }

        .progress-bar-modern:after {
            content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,.3), transparent);
            animation: shimmer 2s infinite;
        }

        @keyframes shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }

        .cancel-btn {
            width: 22px; height: 22px; background: rgba(200,160,0,0.15);
            border: 1px solid rgba(200,160,0,0.3); border-radius: 6px;
            color: var(--yellow-bright); cursor: pointer; display: flex; align-items: center; justify-content: center;
            padding: 0; flex-shrink: 0; transition: all .15s;
        }

        .cancel-btn:hover { background: rgba(220,176,0,0.3); border-color: var(--yellow-bright); }

        .status-console {
            background: rgba(0,0,0,0.5); border: 1px solid rgba(180,140,0,0.2); border-radius: 6px;
            padding: 5px 10px; font-family: Monaco, monospace; font-size: 9px;
            color: #ffdc50; text-align: center;
        }

        /* ===== CUSTOM EXPANDER ===== */
        .custom-expander {
            display: flex; align-items: center; gap: 6px; padding: 5px 12px; margin-top: 3px;
            background: rgba(180,140,0,0.07); border: 1px dashed rgba(180,140,0,0.25);
            border-radius: 6px; color: rgba(255,220,0,0.7); font-size: 11px; font-weight: 700;
            cursor: pointer; transition: all .2s; user-select: none; text-transform: uppercase; letter-spacing: .4px;
        }

        .custom-expander:hover { background: rgba(200,160,0,0.12); border-color: rgba(220,176,0,0.5); color: #ffdc50; }
        .custom-expander.open { background: rgba(180,140,0,0.12); border-color: rgba(200,160,0,0.45); border-style: solid; border-radius: 8px 8px 0 0; margin-bottom: 0; }
        .custom-expander-hint { font-size: 9px; font-weight: 400; color: rgba(255,255,255,.25); margin-left: auto; text-transform: none; }
        .custom-chevron { transition: transform .2s; flex-shrink: 0; }
        .custom-expander.open .custom-chevron { transform: rotate(180deg); }

        .custom-settings { margin-bottom: 8px; background: rgba(180,140,0,0.05); border: 1px solid rgba(180,140,0,0.2); border-top: none; border-radius: 0 0 8px 8px; overflow: hidden; animation: customSlideDown .2s ease-out; }

        @keyframes customSlideDown { from { opacity: 0; max-height: 0; } to { opacity: 1; max-height: 400px; } }

        .custom-settings-body { padding: 8px 12px 10px; }

        .custom-presets { display: flex; gap: 3px; margin-bottom: 8px; }
        .custom-preset-btn {
            flex: 1; padding: 4px 0; font-size: 8px; font-weight: 700; letter-spacing: .5px; text-transform: uppercase;
            border: 1px solid rgba(255,255,255,.08); border-radius: 4px; background: rgba(255,255,255,.05);
            color: rgba(255,255,255,.4); cursor: pointer; transition: all .15s; text-align: center;
        }

        .custom-preset-btn:hover { background: rgba(180,140,0,0.12); color: rgba(255,255,255,.7); }
        .custom-preset-btn.active { background: rgba(180,140,0,0.25); border-color: rgba(220,176,0,0.5); color: #ffdc50; }

        .custom-row { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
        .custom-row label { font-size: 10px; color: rgba(255,255,255,.5); min-width: 56px; flex-shrink: 0; }

        .custom-slider { flex: 1; -webkit-appearance: none; height: 3px; background: rgba(255,255,255,.1); border-radius: 2px; outline: none; }
        .custom-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%; background: var(--yellow); cursor: pointer; border: 2px solid rgba(0,0,0,.3); box-shadow: 0 0 6px rgba(180,140,0,0.5); }

        .custom-val { font-size: 9px; color: rgba(255,255,255,.4); min-width: 28px; text-align: right; font-family: monospace; }

        .custom-break-btns { display: flex; gap: 3px; flex: 1; }
        .custom-break-btn {
            flex: 1; padding: 3px 0; font-size: 8px; font-weight: 700; text-transform: uppercase;
            border: 1px solid rgba(255,255,255,.08); border-radius: 4px; background: rgba(255,255,255,.05);
            color: rgba(255,255,255,.4); cursor: pointer; transition: all .15s; text-align: center;
        }

        .custom-break-btn:hover { background: rgba(180,140,0,0.12); color: rgba(255,255,255,.7); }
        .custom-break-btn.active { background: rgba(180,140,0,0.2); border-color: rgba(220,176,0,0.5); color: #ffdc50; }

        .custom-check { display: flex; align-items: center; gap: 5px; cursor: pointer; }
        .custom-check input[type=checkbox] { accent-color: var(--yellow); }
        .custom-check span { font-size: 9px; color: rgba(255,255,255,.4); }

        .custom-create-btn {
            width: 100%; margin-top: 8px; padding: 7px 12px; display: flex; align-items: center; justify-content: center; gap: 5px;
            background: linear-gradient(135deg, #8b0000, var(--yellow));
            color: #fff; border: none; border-radius: 6px; font-size: 10px; font-weight: 800;
            cursor: pointer; transition: all .2s; text-transform: uppercase; letter-spacing: .5px;
        }

        .custom-create-btn:hover { filter: brightness(1.2); transform: translateY(-1px); }
        .custom-create-btn:active { transform: translateY(0); }
        .custom-create-btn:disabled { opacity: .5; cursor: not-allowed; transform: none; filter: none; }

        /* ===== STYLES TAB ===== */
        .styles-info {
            display: flex; align-items: center; gap: 6px; padding: 6px 10px;
            background: rgba(180,140,0,0.08); border: 1px solid rgba(200,160,0,0.2);
            border-radius: 8px; margin-bottom: 12px; font-size: 10px; color: var(--grey2);
        }

        .styles-info > span { flex: 1; }
        .styles-info svg { flex-shrink: 0; color: var(--yellow); width: 14px; height: 14px; }
        .styles-info strong { color: #ffdc50; font-weight: 700; }

        .refresh-styles-btn {
            flex-shrink: 0; width: 22px; height: 22px;
            background: rgba(180,140,0,0.12); border: 1px solid rgba(180,140,0,0.3);
            border-radius: 4px; color: var(--yellow); cursor: pointer;
            display: flex; align-items: center; justify-content: center; padding: 0; transition: all .15s;
        }

        .refresh-styles-btn:hover { background: rgba(200,160,0,0.25); transform: rotate(180deg); }
        .refresh-styles-btn.spinning svg { animation: refreshSpin 1s linear infinite; }
        @keyframes refreshSpin { to { transform: rotate(360deg); } }

        .styles-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 16px; }

        .style-card {
            background: var(--black3); border: 1.5px solid rgba(180,140,0,0.2);
            border-radius: 6px; padding: 6px; cursor: pointer;
            transition: all .3s ease; overflow: hidden; aspect-ratio: 1;
            display: flex; flex-direction: column; position: relative;
        }

        .style-card:hover { transform: translateY(-1px); border-color: rgba(220,176,0,0.5); box-shadow: 0 4px 14px rgba(180,140,0,0.3); }
        .style-card.active { border-color: var(--yellow); background: rgba(180,140,0,0.12); }

        .style-preview {
            background: rgba(0,0,0,.6); border-radius: 4px; flex: 1;
            display: flex; align-items: center; justify-content: center; margin-bottom: 6px; overflow: hidden;
        }

        .style-preview svg { width: 32px; height: 32px; }

        .style-info h4 { font-size: 11px; font-weight: 800; color: #fff; margin-bottom: 2px; text-align: center; line-height: 1.2; text-transform: uppercase; letter-spacing: .3px; }
        .style-info p { font-size: 8.5px; color: var(--grey2); text-align: center; line-height: 1.3; }

        .loading-styles { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; grid-column: 1 / -1; }
        .loading-styles p { font-size: 12px; color: var(--grey2); margin-top: 12px; }
        .loading-spinner circle:last-child { stroke: var(--yellow); }

        .reset-style-section { margin-top: 16px; padding: 0; }

        .reset-style-btn {
            width: 100%; display: flex; align-items: center; justify-content: center; gap: 8px;
            padding: 10px 16px; border-radius: 8px; font-size: 12px; font-weight: 800;
            cursor: pointer; transition: all .2s; letter-spacing: .4px; text-transform: uppercase;
            border: 1px solid rgba(200,100,0,0.35); background: rgba(180,60,0,0.12); color: #ff8833;
        }

        .reset-style-btn:hover { background: rgba(200,60,0,0.25); border-color: rgba(220,80,0,0.6); transform: translateY(-1px); }
        .reset-style-btn:disabled { opacity: .5; cursor: not-allowed; transform: none; }

        /* ===== PREVIEW MODAL ===== */
        body.modal-open .tab-content { overflow: hidden; pointer-events: none; }

        .preview-modal-overlay {
            position: fixed; top: 0; right: 0; bottom: 0; left: 0;
            background: rgba(0,0,0,.85); backdrop-filter: blur(8px);
            z-index: 1000; display: flex; align-items: center; justify-content: center;
            padding: 16px; opacity: 0; transition: opacity .2s ease; pointer-events: auto;
        }

        .preview-modal-overlay[hidden] { display: none; }
        .preview-modal-overlay:not([hidden]) { opacity: 1; }

        .preview-modal {
            background: #0f0f0f; border: 1px solid rgba(200,160,0,0.3);
            border-radius: 12px; width: 100%;
            max-width: calc(100vw - 32px); max-height: calc(100vh - 32px);
            display: flex; flex-direction: column;
            box-shadow: 0 20px 60px rgba(180,140,0,0.25);
        }

        .preview-modal-header {
            flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
            padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,.05);
        }

        .preview-modal-title { font-size: 13px; font-weight: 800; color: #fff; letter-spacing: .3px; text-transform: uppercase; }

        .preview-modal-close {
            width: 22px; height: 22px; background: rgba(255,255,255,.07);
            border: 1px solid rgba(255,255,255,.1); border-radius: 4px;
            color: rgba(255,255,255,.6); font-size: 16px; line-height: 1; cursor: pointer;
            display: flex; align-items: center; justify-content: center; padding: 0; transition: all .15s;
        }

        .preview-modal-close:hover { background: rgba(200,160,0,0.2); border-color: rgba(220,176,0,0.5); color: var(--yellow-bright); }

        .preview-modal-info { flex-shrink: 0; padding: 8px 16px; font-size: 10px; color: var(--grey2); background: rgba(180,140,0,0.05); border-bottom: 1px solid rgba(255,255,255,.03); }
        .preview-modal-info #previewModalCount { color: var(--yellow-bright); font-weight: 700; }

        .preview-modal-list { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 12px; }
        .preview-modal-list::-webkit-scrollbar { width: 5px; }
        .preview-modal-list::-webkit-scrollbar-track { background: transparent; }
        .preview-modal-list::-webkit-scrollbar-thumb { background: rgba(180,140,0,0.3); border-radius: 3px; }

        .preview-row { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.03); }
        .preview-row:last-child { border-bottom: none; }
        .preview-time { flex-shrink: 0; font-family: monospace; font-size: 9px; color: var(--grey2); padding-top: 7px; width: 50px; text-align: right; user-select: none; }

        .preview-text {
            flex: 1; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1);
            border-radius: 4px; color: #fff; font-size: 11px; padding: 5px 8px;
            resize: none; overflow-y: auto; min-height: 28px; max-height: 200px;
            font-family: inherit; line-height: 1.4; transition: all .15s; box-sizing: border-box;
        }

        .preview-text:focus { outline: none; border-color: var(--yellow); background: rgba(180,140,0,0.08); }

        .preview-modal-actions { flex-shrink: 0; display: flex; gap: 8px; justify-content: flex-end; padding: 12px 16px; border-top: 1px solid rgba(255,255,255,.05); }

        .preview-modal-btn { padding: 8px 18px; border-radius: 8px; font-size: 12px; font-weight: 800; cursor: pointer; transition: all .15s; border: none; font-family: inherit; letter-spacing: .3px; text-transform: uppercase; }
        .preview-modal-btn:hover { opacity: .92; transform: translateY(-1px); }
        .preview-modal-btn:active { transform: translateY(0); }
        .preview-modal-cancel { background: rgba(255,255,255,.07); color: var(--grey2); border: 1px solid rgba(255,255,255,.1); }
        .preview-modal-cancel:hover { background: rgba(255,255,255,.12); color: #ddd; }
        .preview-modal-approve { background: linear-gradient(135deg, #8b0000, var(--yellow)); color: #fff; box-shadow: 0 2px 8px rgba(180,140,0,0.4); }
        .preview-modal-approve:hover { box-shadow: 0 4px 14px rgba(200,160,0,0.5); }

        /* ===== WHISPER INFO ===== */
        .whisper-info {
            display: flex; align-items: center; gap: 6px; padding: 6px 10px;
            background: rgba(180,140,0,0.07); border: 1px solid rgba(180,140,0,0.18);
            border-radius: 8px; margin-bottom: 8px; font-size: 10px; color: var(--grey2);
        }

        .whisper-info-bottom { margin-top: 8px; margin-bottom: 0; justify-content: center; opacity: .45; border: none; background: transparent; padding: 4px 0; font-size: 9px; }
        .whisper-info-bottom:hover { opacity: .75; }

        /* ===== ANIMATE TAB ===== */
        #animateTab { max-height: calc(100vh - 80px); overflow-y: auto; overflow-x: hidden; padding-right: 2px; }
        #animateTab::-webkit-scrollbar { width: 4px; }
        #animateTab::-webkit-scrollbar-thumb { background: rgba(180,140,0,0.2); border-radius: 2px; }
        #animateTab::-webkit-scrollbar-thumb:hover { background: rgba(200,160,0,0.4); }

        #animateTab .anim-preview-box { position: relative; height: 44px; margin-bottom: 8px; background: rgba(0,0,0,.5); border: 1px solid rgba(255,255,255,.05); border-radius: 6px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
        #animateTab .anim-preview-text { font-size: 14px; font-weight: 700; color: #fff; letter-spacing: .04em; white-space: nowrap; display: inline-flex; }
        #animateTab .anim-preview-label { position: absolute; bottom: 2px; right: 5px; font-size: 7px; color: rgba(255,255,255,.2); text-transform: uppercase; letter-spacing: .08em; }
        #animateTab .anim-preview-char { display: inline-block; animation-fill-mode: both; animation-duration: .5s; animation-timing-function: ease-out; }

        #animateTab .animate-section { margin-bottom: 8px; padding: 8px 10px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.05); border-radius: 6px; transition: border-color .2s, background .2s; }
        #animateTab .animate-section:hover { border-color: rgba(180,140,0,0.2); }
        #animateTab .animate-section.section-active { border-color: rgba(200,160,0,0.35); background: rgba(180,140,0,0.06); }

        #animateTab .animate-section-title { display: flex; align-items: center; gap: 8px; font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: rgba(255,255,255,.4); margin-bottom: 8px; justify-content: center; }
        #animateTab .animate-section-title:before,
        #animateTab .animate-section-title:after { content: ""; flex: 1; height: 1px; background: rgba(255,255,255,.06); }
        #animateTab .animate-section.section-active .animate-section-title { color: rgba(255,220,0,0.8); }
        #animateTab .animate-section.section-active .animate-section-title:before,
        #animateTab .animate-section.section-active .animate-section-title:after { background: rgba(180,140,0,0.25); }

        #animateTab .animate-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 6px; }
        #animateTab .animate-row:last-child { margin-bottom: 0; }
        #animateTab .animate-row label { font-size: 10px; color: rgba(255,255,255,.5); min-width: 58px; flex-shrink: 0; }

        #animateTab .animate-select {
            flex: 1; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.1);
            border-radius: 5px; color: #fff; font-size: 10px; padding: 4px 20px 4px 7px;
            outline: none; cursor: pointer; -webkit-appearance: none; appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%23666' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
            background-repeat: no-repeat; background-position: right 6px center;
        }

        #animateTab .animate-select:focus { border-color: var(--yellow); }
        #animateTab .animate-select option { background: #1a1a1a; color: #fff; }

        #animateTab .animate-slider-wrap { flex: 1; display: flex; align-items: center; gap: 6px; }
        #animateTab .animate-slider { flex: 1; -webkit-appearance: none; height: 3px; background: rgba(255,255,255,.1); border-radius: 2px; outline: none; }
        #animateTab .animate-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%; background: var(--yellow); cursor: pointer; border: 2px solid rgba(0,0,0,.3); }

        #animateTab .animate-val { font-size: 9px; color: rgba(255,255,255,.4); min-width: 32px; text-align: right; font-family: monospace; }

        #animateTab .animate-speed-btns { display: flex; gap: 3px; flex: 1; }
        #animateTab .speed-btn { flex: 1; padding: 3px 0; font-size: 9px; font-weight: 700; text-transform: uppercase; border: 1px solid rgba(255,255,255,.08); border-radius: 4px; background: rgba(255,255,255,.05); color: rgba(255,255,255,.5); cursor: pointer; transition: all .2s; text-align: center; }
        #animateTab .speed-btn:hover { background: rgba(180,140,0,0.12); color: rgba(255,255,255,.8); }
        #animateTab .speed-btn.active { background: rgba(180,140,0,0.22); border-color: rgba(220,176,0,0.5); color: #ffdc50; }

        #animateTab .animate-actions { display: flex; gap: 6px; margin-top: 8px; }

        #animateTab .animate-apply-btn {
            flex: 1; display: flex; align-items: center; justify-content: center; gap: 5px;
            padding: 8px 12px; background: linear-gradient(135deg, #8b0000, var(--yellow));
            color: #fff; border: none; border-radius: 6px; font-size: 11px; font-weight: 800;
            cursor: pointer; transition: all .2s; text-transform: uppercase; letter-spacing: .4px;
        }

        #animateTab .animate-apply-btn:hover { filter: brightness(1.15); transform: translateY(-1px); }
        #animateTab .animate-apply-btn:disabled { opacity: .5; cursor: not-allowed; transform: none; filter: none; }

        #animateTab .animate-clear-btn {
            display: flex; align-items: center; justify-content: center; gap: 4px;
            padding: 8px 10px; background: rgba(255,255,255,.06); color: rgba(255,255,255,.6);
            border: 1px solid rgba(255,255,255,.1); border-radius: 6px; font-size: 10px;
            font-weight: 600; cursor: pointer; transition: all .2s;
        }

        #animateTab .animate-clear-btn:hover { background: rgba(180,140,0,0.12); border-color: rgba(200,160,0,0.4); color: #ffdc50; }

        #animateTab .animate-info { display: flex; align-items: center; gap: 5px; margin: 6px 0; font-size: 9px; color: rgba(255,255,255,.3); }

        #animateTab .ae-color-row { display: flex; align-items: center; gap: 5px; flex: 1; }
        #animateTab .ae-color-swatch { width: 16px; height: 16px; min-width: 16px; border: 1px solid rgba(255,255,255,.25); border-radius: 2px; cursor: pointer; padding: 0; -webkit-appearance: none; appearance: none; background: transparent; }
        #animateTab .ae-color-swatch::-webkit-color-swatch-wrapper { padding: 0; }
        #animateTab .ae-color-swatch::-webkit-color-swatch { border: none; border-radius: 2px; }
        #animateTab .ae-hex-input { width: 56px; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.1); border-radius: 3px; color: #aaa; font-size: 9px; font-family: monospace; padding: 2px 4px; outline: none; text-transform: uppercase; }
        #animateTab .ae-hex-input:focus { border-color: var(--yellow); color: #fff; }
        #animateTab .ae-color-presets { display: flex; gap: 3px; margin-left: 2px; }
        #animateTab .ae-color-dot { width: 10px; height: 10px; border-radius: 2px; border: 1px solid rgba(255,255,255,.12); cursor: pointer; padding: 0; -webkit-appearance: none; transition: border-color .15s, transform .15s; }
        #animateTab .ae-color-dot:hover { border-color: rgba(255,255,255,.5); transform: scale(1.15); }

        #animateTab .ws-color-section { margin-bottom: 6px; }
        #animateTab .ws-color-label { display: flex; align-items: center; gap: 5px; margin-bottom: 4px; font-size: 10px; color: rgba(255,255,255,.5); }
        #animateTab .ae-color-swatch-mini { width: 12px; height: 12px; min-width: 12px; border: 1px solid rgba(255,255,255,.25); border-radius: 2px; cursor: pointer; padding: 0; -webkit-appearance: none; background: transparent; }
        #animateTab .ae-color-swatch-mini::-webkit-color-swatch-wrapper { padding: 0; }
        #animateTab .ae-color-swatch-mini::-webkit-color-swatch { border: none; border-radius: 2px; }
        #animateTab .ae-hex-mini { width: 50px; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.07); border-radius: 3px; color: rgba(255,255,255,.4); font-size: 8px; font-family: monospace; padding: 2px 4px; outline: none; text-transform: uppercase; margin-left: auto; }
        #animateTab .ae-hex-mini:focus { border-color: var(--yellow); color: #fff; }
        #animateTab .ws-color-grid { display: flex; flex-wrap: wrap; gap: 3px; }
        #animateTab .ws-dot { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(255,255,255,.1); cursor: pointer; padding: 0; -webkit-appearance: none; transition: border-color .12s, transform .12s; }
        #animateTab .ws-dot:hover { border-color: rgba(255,255,255,.6); transform: scale(1.15); }
        #animateTab .ws-shape-picker { display: flex; gap: 4px; margin-bottom: 8px; }
        #animateTab .ws-shape-btn { flex: 1; height: 28px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); border-radius: 4px; cursor: pointer; padding: 2px; transition: all .15s; }
        #animateTab .ws-shape-btn svg { width: 100%; height: 100%; }
        #animateTab .ws-shape-btn:hover { background: rgba(180,140,0,0.12); border-color: rgba(200,160,0,0.35); }
        #animateTab .ws-shape-btn.active { background: rgba(180,140,0,0.2); border-color: rgba(220,176,0,0.5); }

        #animateTab .animate-preset-bar { display: flex; gap: 4px; margin-bottom: 4px; align-items: center; }
        #animateTab .preset-btn { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.1); border-radius: 5px; color: rgba(255,255,255,.5); font-size: 11px; cursor: pointer; transition: all .2s; }
        #animateTab .preset-btn:hover { background: rgba(180,140,0,0.15); color: #fff; }

        #animateTab .preset-save-dialog { display: flex; gap: 4px; margin-bottom: 8px; align-items: center; padding: 5px 7px; background: rgba(180,140,0,0.08); border: 1px solid rgba(180,140,0,0.25); border-radius: 6px; }
        #animateTab .preset-name-input { flex: 1; background: rgba(0,0,0,.4); border: 1px solid rgba(255,255,255,.12); border-radius: 4px; color: #fff; font-size: 10px; padding: 4px 7px; outline: none; }
        #animateTab .preset-name-input:focus { border-color: var(--yellow); }
        #animateTab .preset-name-input::placeholder { color: rgba(255,255,255,.25); }
        #animateTab .preset-confirm-btn { padding: 4px 10px; background: rgba(180,140,0,0.22); border: 1px solid rgba(200,160,0,0.35); border-radius: 4px; color: #ffdc50; font-size: 10px; font-weight: 700; cursor: pointer; white-space: nowrap; }
        #animateTab .preset-confirm-btn:hover { background: rgba(200,160,0,0.35); }
        #animateTab .preset-cancel-btn { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); border-radius: 4px; color: rgba(255,255,255,.4); font-size: 11px; cursor: pointer; }
        #animateTab .preset-cancel-btn:hover { background: rgba(180,140,0,0.15); border-color: rgba(200,160,0,0.4); color: #ff4444; }

        #animateTab .char-amounts-group { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,.04); }
        #animateTab .char-amt-row label { color: rgba(255,220,0,0.5); font-size: 9px; }

        html, body { -webkit-user-select: none; -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent; }

        @media (max-width: 450px) { .styles-grid { grid-template-columns: repeat(2, 1fr); } }

        /* ===== ANIM KEYFRAMES ===== */
        @keyframes pc-fi  { 0% { opacity: var(--pc-op, 0); } to { opacity: 1; } }
        @keyframes pc-su  { 0% { opacity: var(--pc-op, 0); transform: translateY(var(--pc-pos, 12px)); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pc-sd  { 0% { opacity: var(--pc-op, 0); transform: translateY(calc(var(--pc-pos, 12px) * -1)); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pc-sl  { 0% { opacity: var(--pc-op, 0); transform: translate(var(--pc-pos, 15px)); } to { opacity: 1; transform: translate(0); } }
        @keyframes pc-sc  { 0% { opacity: var(--pc-op, 0); transform: scale(var(--pc-scale, 0)); } to { opacity: 1; transform: scale(1); } }
        @keyframes pc-ro  { 0% { opacity: var(--pc-op, 0); transform: rotate(var(--pc-rot, 45deg)); } to { opacity: 1; transform: rotate(0); } }
        @keyframes pc-bl  { 0% { opacity: var(--pc-op, 0); filter: blur(var(--pc-blur, 8px)); } to { opacity: 1; filter: blur(0); } }
        @keyframes pc-tr  { 0% { letter-spacing: var(--pc-track, .3em); opacity: .3; } to { letter-spacing: .04em; opacity: 1; } }
        @keyframes pc-dr  { 0% { opacity: var(--pc-op, 0); transform: translateY(calc(var(--pc-pos, 20px) * -1)) scale(var(--pc-scale, 0)); } 60% { opacity: 1; transform: translateY(3px) scale(1.05); } to { opacity: 1; transform: translateY(0) scale(1); } }

        #animateTab .anim-preview-char.pc-typewriter { opacity: var(--pc-op, 0); transition: opacity .01s step-end; animation: none; }
        #animateTab .anim-preview-char.pc-typewriter.pc-visible { opacity: 1; }
        #animateTab .anim-preview-char.pc-fade { opacity: var(--pc-op, 0); animation-name: pc-fi; }
        #animateTab .anim-preview-char.pc-slideUp { opacity: var(--pc-op, 0); animation-name: pc-su; }
        #animateTab .anim-preview-char.pc-slideDown { opacity: var(--pc-op, 0); animation-name: pc-sd; }
        #animateTab .anim-preview-char.pc-slideLeft { opacity: var(--pc-op, 0); animation-name: pc-sl; }
        #animateTab .anim-preview-char.pc-scale { opacity: var(--pc-op, 0); animation-name: pc-sc; }
        #animateTab .anim-preview-char.pc-rotate { opacity: var(--pc-op, 0); animation-name: pc-ro; transform-origin: center bottom; }
        #animateTab .anim-preview-char.pc-blur { opacity: var(--pc-op, 0); animation-name: pc-bl; }
        #animateTab .anim-preview-char.pc-tracking { animation-name: pc-tr; }
        #animateTab .anim-preview-char.pc-drop { opacity: var(--pc-op, 0); animation-name: pc-dr; animation-duration: .6s; }
    </style>
</head>
<body>
    <!-- HEADER -->
    <div class="deco-header">
        <img class="header-avatar" src="data:image/jpeg;base64,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" alt="Zeno Yali">
        <div class="header-text">
            <div class="header-title">דה <span>קוקי</span></div>
            <div class="header-by">by <strong>THE COHEN</strong></div>
        </div>
        <div class="header-badge">v4.1.7</div>
    </div>

    <div id="mainScreen" class="main-screen" style="display: none;">
        <div class="content-wrapper">
            
            <!-- Tab Navigation -->
            <div class="tab-navigation">
                <button class="tab-btn active" data-tab="create">ליצור כתוביות</button>
                <button class="tab-btn" data-tab="styles">סטיילים</button>
                <button class="tab-btn" data-tab="animate">אנימציות</button>
            </div>
            
            <!-- Create Subtitles Tab -->
            <div class="tab-content active" id="createTab">
                <div class="layer-mode-toggle">
                    <span class="toggle-label">רב שכבות</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="layerModeToggle">
                        <span class="toggle-slider"></span>
                    </label>
                    <span class="toggle-label">שכבה אחת</span>
                    <div class="toggle-divider"></div>
                    <label class="precomp-toggle" title="Auto pre-compose after creation for better performance">
                        <input type="checkbox" id="precompToggle">
                        <span class="precomp-checkbox"></span>
                        <span class="precomp-label">Pre-comp</span>
                    </label>
                    <label class="precomp-toggle" title="Review and edit subtitle text before creating layers">
                        <input type="checkbox" id="previewToggle">
                        <span class="precomp-checkbox"></span>
                        <span class="precomp-label">תצוגה מקדימה</span>
                    </label>
                </div>

                <div class="font-picker" id="fontPicker">
                    <div class="font-picker-header" id="fontPickerHeader" role="button" tabindex="0" aria-expanded="false">
                        <svg class="font-picker-icon" width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2v12h2V9h6v5h2V2h-2v5H5V2H3z"/></svg>
                        <span class="font-picker-header-label">פונט</span>
                        <span class="font-picker-header-divider">·</span>
                        <span class="font-picker-header-preview" id="fontPickerHeaderPreview" hidden>Aa</span>
                        <span class="font-picker-header-name" id="fontPickerHeaderName">בְּרִירַת מֶחדָל (Arial / auto-detect)</span>
                        <button type="button" id="fontPickerClear" class="font-picker-clear" title="Reset to default" hidden>&times;</button>
                        <svg class="font-picker-chevron" width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><path d="M2 4l3 3 3-3" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
                    </div>
                    <div class="font-picker-body">
                        <input type="text" class="font-picker-search" id="fontPickerSearch" placeholder="Search fonts (optional)..." autocomplete="off">
                        <div class="font-picker-list" id="fontPickerList" role="listbox"></div>
                    </div>
                </div>

                <div class="font-picker lang-picker" id="langPicker">
                    <div class="font-picker-header" id="langPickerHeader" role="button" tabindex="0" aria-expanded="false">
                        <svg class="font-picker-icon" width="12" height="12" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/><ellipse cx="8" cy="8" rx="3" ry="6.5" stroke="currentColor" stroke-width="1.2"/><line x1="1.5" y1="8" x2="14.5" y2="8" stroke="currentColor" stroke-width="1.2"/></svg>
                        <span class="font-picker-header-label">שָׂפָה</span>
                        <span class="font-picker-header-divider">·</span>
                        <span class="font-picker-header-name" id="langPickerHeaderName">זיהוי אוטומטי</span>
                        <button type="button" id="langPickerClear" class="font-picker-clear" title="Reset to auto-detect" hidden>&times;</button>
                        <svg class="font-picker-chevron" width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 4l3 3 3-3" stroke="currentColor" stroke-width="1.5"/></svg>
                    </div>
                    <div class="font-picker-body">
                        <input type="text" class="font-picker-search" id="langPickerSearch" placeholder="Search languages..." autocomplete="off">
                        <div class="font-picker-list" id="langPickerList" role="listbox"></div>
                    </div>
                </div>

                <div class="position-toggle" id="positionToggle">
                    <span class="position-toggle-label">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><rect x="2" y="2" width="12" height="12" rx="1" stroke="currentColor" stroke-width="1.2" fill="none"/><rect x="3.5" y="9.5" width="9" height="2" fill="currentColor"/></svg>
                        מַצָב
                    </span>
                    <div class="position-toggle-buttons">
                        <button type="button" class="position-toggle-btn" data-position="center">מֶרְכָּז</button>
                        <button type="button" class="position-toggle-btn active" data-position="below">לְהַלָן</button>
                    </div>
                </div>

                <div class="action-cards">
                    <div class="action-card" id="generateBtn" data-mode="words">
                        <div class="card-bg-gradient words-gradient"></div>
                        <div class="card-icon-modern">
                            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="4" y="12" width="6" height="8" rx="1" fill="white" opacity="0.9"/><rect x="13" y="8" width="6" height="12" rx="1" fill="white" opacity="0.9"/><rect x="22" y="10" width="6" height="10" rx="1" fill="white" opacity="0.9"/></svg>
                        </div>
                        <div class="card-content">
                            <h3>מילה אחת</h3>
                            <p>Eכל מילה מופיעה בנפרד עם תזמון</p>
                            <div class="card-badge">מהיר ודינמי</div>
                        </div>
                        <div class="card-progress"></div>
                    </div>
                    
                    <div class="action-card" id="wordPairsBtn" data-mode="wordpairs">
                        <div class="card-bg-gradient wordpairs-gradient"></div>
                        <div class="card-icon-modern">
                            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="6" y="11" width="8" height="10" rx="1" fill="white" opacity="0.9"/><rect x="18" y="11" width="8" height="10" rx="1" fill="white" opacity="0.9"/></svg>
                        </div>
                        <div class="card-content">
                            <h3>שתי מילים</h3>
                            <p>שתי מילים לכל שכבת טקסט עם תזמון מושלם</p>
                            <div class="card-badge">Balanced Flow</div>
                        </div>
                        <div class="card-progress"></div>
                    </div>
                    
                    <div class="action-card" id="smartWordsBtn" data-mode="smartwords">
                        <div class="card-bg-gradient smartwords-gradient"></div>
                        <div class="card-icon-modern">
                            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="4" y="11" width="4" height="10" rx="1" fill="white" opacity="0.9"/><rect x="10" y="11" width="6" height="10" rx="1" fill="white" opacity="0.9"/><rect x="18" y="11" width="4" height="10" rx="1" fill="white" opacity="0.9"/><circle cx="25" cy="16" r="2.5" fill="white" opacity="0.9"/></svg>
                        </div>
                        <div class="card-content">
                            <h3>שלוש מילים</h3>
                            <p>בינה מלאכותית מקבצת לפי משמעות, ביטויים קצרים</p>
                            <div class="card-badge">Smart</div>
                        </div>
                        <div class="card-progress"></div>
                    </div>
                    
                    <div class="action-card" id="smartExtendedBtn" data-mode="smartextended">
                        <div class="card-bg-gradient smartextended-gradient"></div>
                        <div class="card-icon-modern">
                            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="3" y="11" width="5" height="10" rx="1" fill="white" opacity="0.9"/><rect x="10" y="11" width="5" height="10" rx="1" fill="white" opacity="0.9"/><rect x="17" y="11" width="5" height="10" rx="1" fill="white" opacity="0.9"/><rect x="24" y="11" width="5" height="10" rx="1" fill="white" opacity="0.9"/></svg>
                        </div>
                        <div class="card-content">
                            <h3>Smart Long</h3>
                            <p>בינה מלאכותית מקבצת לפי משמעות, ביטויים ארוכים יותר</p>
                            <div class="card-badge">מוּרחָב</div>
                        </div>
                        <div class="card-progress"></div>
                    </div>
                    
                    <div class="action-card" id="sentenceBtn" data-mode="sentences">
                        <div class="card-bg-gradient sentences-gradient"></div>
                        <div class="card-icon-modern">
                            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><rect x="6" y="10" width="20" height="3" rx="1.5" fill="white" opacity="0.9"/><rect x="6" y="15" width="16" height="3" rx="1.5" fill="white" opacity="0.9"/><rect x="6" y="20" width="18" height="3" rx="1.5" fill="white" opacity="0.9"/></svg>
                        </div>
                        <div class="card-content">
                            <h3>Sentences</h3>
                            <p>ביטויים שלמים בבלוקים מרובי שורות</p>
                            <div class="card-badge">קריאה טבעית</div>
                        </div>
                        <div class="card-progress"></div>
                    </div>
                </div>
                
                <!-- Custom Mode Expander -->
                <div class="custom-expander" id="customBtn">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="1" y="4" width="6" height="3" rx="1" fill="currentColor" opacity="0.5"/><rect x="9" y="4" width="6" height="3" rx="1" fill="currentColor" opacity="0.5"/><rect x="3" y="9" width="10" height="3" rx="1" fill="currentColor" opacity="0.3"/><circle cx="13" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>
                    <span>Custom</span>
                    <span class="custom-expander-hint">Configure words, lines & safe zone</span>
                    <svg class="custom-chevron" width="10" height="10" viewBox="0 0 10 10"><path d="M2.5 3.5L5 6.5L7.5 3.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
                </div>
                
                <!-- Custom Mode Settings -->
                <div id="customSettings" class="custom-settings" style="display:none;">
                    <div id="customSettingsBody" class="custom-settings-body">
                        <div class="custom-presets">
                            <button class="custom-preset-btn" data-preset="single" title="1 word per layer">Single</button>
                            <button class="custom-preset-btn active" data-preset="short" title="2–4 words">Short</button>
                            <button class="custom-preset-btn" data-preset="medium" title="3–8 words">Medium</button>
                            <button class="custom-preset-btn" data-preset="long" title="5–15 words, multi-line">Long</button>
                            <button class="custom-preset-btn" data-preset="full" title="All text">Full</button>
                        </div>
                        <div class="custom-row">
                            <label>מילים קטנות</label>
                            <input type="range" id="customMinWords" class="custom-slider" min="1" max="20" value="1" step="1">
                            <span id="customMinWordsVal" class="custom-val">1</span>
                        </div>
                        <div class="custom-row">
                            <label>מקסימום מילים</label>
                            <input type="range" id="customMaxWords" class="custom-slider" min="1" max="50" value="4" step="1">
                            <span id="customMaxWordsVal" class="custom-val">4</span>
                        </div>
                        <div class="custom-row">
                            <label>מקסימום קווים</label>
                            <input type="range" id="customMaxLines" class="custom-slider" min="1" max="5" value="1" step="1">
                            <span id="customMaxLinesVal" class="custom-val">1</span>
                        </div>
                        <div class="custom-row">
                            <label>מקום בטוח</label>
                            <input type="range" id="customSafeZone" class="custom-slider" min="50" max="100" value="80" step="5">
                            <span id="customSafeZoneVal" class="custom-val">80%</span>
                        </div>
                        <div class="custom-row">
                            <label>Break On</label>
                            <div class="custom-break-btns">
                                <button class="custom-break-btn active" data-sensitivity="high" title="Break on any pause">צָמוּד</button>
                                <button class="custom-break-btn" data-sensitivity="medium" title="Natural pauses">טִבעִי</button>
                                <button class="custom-break-btn" data-sensitivity="low" title="Only long pauses">מְשׁוּחרָר</button>
                                <button class="custom-break-btn" data-sensitivity="off" title="No pause detection">כבוי</button>
                            </div>
                        </div>
                        <div class="custom-row">
                            <label></label>
                            <label class="custom-check">
                                <input type="checkbox" id="customSmartBreaks" checked>
                                <span>הימנעו ממילות יחס נגררות</span>
                            </label>
                        </div>
                        <button id="customCreateBtn" class="custom-create-btn">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M10.97 4.97a.75.75 0 011.07 1.05l-3.99 4.99a.75.75 0 01-1.08.02L4.324 8.384a.75.75 0 111.06-1.06l2.094 2.093 3.473-4.425z"/></svg>
                            צור כתוביות מותאמות אישית
                        </button>
                    </div>
                </div>
                
                <div class="tools-toolbar">
                    <button id="selectAllBtn" class="tool-btn tool-select" title="Select All [AC] Layers">
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M2 0a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2V2a2 2 0 00-2-2H2zm10.03 4.97a.75.75 0 010 1.06l-5 5a.75.75 0 01-1.06 0l-2.5-2.5a.75.75 0 111.06-1.06L6.5 9.44l4.47-4.47a.75.75 0 011.06 0z"/></svg>
                        <span>לבחור הכל</span>
                    </button>
                    <button id="removePunctuationBtn" class="tool-btn tool-punctuation" title="Remove Punctuation">
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M2.146 2.854a.5.5 0 11.708-.708L8 7.293l5.146-5.147a.5.5 0 01.708.708L8.707 8l5.147 5.146a.5.5 0 01-.708.708L8 8.707l-5.146 5.147a.5.5 0 01-.708-.708L7.293 8 2.146 2.854z"/></svg>
                        <span>סימני פיסוק</span>
                    </button>
                    <button id="deleteAllBtn" class="tool-btn tool-delete" title="Delete All [AC] Layers">
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M5.5 5.5A.5.5 0 016 6v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm2.5 0a.5.5 0 01.5.5v6a.5.5 0 01-1 0V6a.5.5 0 01.5-.5zm3 .5a.5.5 0 00-1 0v6a.5.5 0 001 0V6z"/><path fill-rule="evenodd" d="M14.5 3a1 1 0 01-1 1H13v9a2 2 0 01-2 2H5a2 2 0 01-2-2V4h-.5a1 1 0 01-1-1V2a1 1 0 011-1H6a1 1 0 011-1h2a1 1 0 011 1h3.5a1 1 0 011 1v1zM4.118 4L4 4.059V13a1 1 0 001 1h6a1 1 0 001-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/></svg>
                        <span>למחוק הכל</span>
                    </button>
                </div>
                
                <div class="srt-toolbar">
                    <button id="importSrtBtn" class="srt-btn srt-import" title="Import SRT file">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M.5 9.9a.5.5 0 01.5.5v2.5a1 1 0 001 1h12a1 1 0 001-1v-2.5a.5.5 0 011 0v2.5a2 2 0 01-2 2H2a2 2 0 01-2-2v-2.5a.5.5 0 01.5-.5z"/><path d="M7.646 1.146a.5.5 0 01.708 0l3 3a.5.5 0 01-.708.708L8.5 2.707V11.5a.5.5 0 01-1 0V2.707L5.354 4.854a.5.5 0 11-.708-.708l3-3z" transform="rotate(180 8 8)"/></svg>
                        <span>Import SRT</span>
                    </button>
                    <button id="exportSrtBtn" class="srt-btn srt-export" title="Export SRT from timeline">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M.5 9.9a.5.5 0 01.5.5v2.5a1 1 0 001 1h12a1 1 0 001-1v-2.5a.5.5 0 011 0v2.5a2 2 0 01-2 2H2a2 2 0 01-2-2v-2.5a.5.5 0 01.5-.5z"/><path d="M7.646 1.146a.5.5 0 01.708 0l3 3a.5.5 0 01-.708.708L8.5 2.707V11.5a.5.5 0 01-1 0V2.707L5.354 4.854a.5.5 0 11-.708-.708l3-3z"/></svg>
                        <span>Export SRT</span>
                    </button>
                </div>
                
                <div class="progress-row" id="progressContainer" hidden>
                    <div class="progress-wrapper">
                        <div class="progress-bar-modern" id="progressBar"></div>
                    </div>
                    <button type="button" id="cancelBtn" class="cancel-btn" title="Cancel transcription">
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 2 L8 8 M8 2 L2 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
                    </button>
                </div>
                
                <div id="status" class="status-console">
                    מוכן • בחר שכבה ומצב
                </div>
                
                <div class="whisper-info whisper-info-bottom">
                    <span>MP3, WAV, M4A, MP4, MOV, AVI, MKV, WEBM</span>
                </div>

                <!-- Subtitle Text Editor Modal -->
                <div class="preview-modal-overlay" id="previewModalOverlay" hidden role="dialog" aria-modal="true" aria-labelledby="previewModalTitle">
                    <div class="preview-modal">
                        <div class="preview-modal-header">
                            <span class="preview-modal-title" id="previewModalTitle">סקירת כתוביות</span>
                            <button class="preview-modal-close" id="previewModalClose" aria-label="Close" type="button">&times;</button>
                        </div>
                        <div class="preview-modal-info">
                            <span id="previewModalCount">0</span> ייווצרו שכבות · ערוך את הטקסט למטה
                        </div>
                        <div class="preview-modal-list" id="previewModalList"></div>
                        <div class="preview-modal-actions">
                            <button class="preview-modal-btn preview-modal-cancel" id="previewModalCancel" type="button">לְבַטֵל</button>
                            <button class="preview-modal-btn preview-modal-approve" id="previewModalApprove" type="button">✓ לִיצוֹר</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Styles Tab -->
            <div class="tab-content" id="stylesTab">
                <div class="styles-info">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zM7 5h2v2H7V5zm0 3h2v5H7V8z"/></svg>
                    <span>סגנונות קיימים רק על <strong>כמה שכבות</strong> מצב</span>
                    <button id="refreshStylesBtn" class="refresh-styles-btn" title="Refresh styles from server">
                        <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3a5 5 0 014.546 2.914.5.5 0 00.908-.418A6 6 0 108 14v-1a5 5 0 110-10z"/><path d="M8 4.466V.534a.25.25 0 01.41-.192L10.77 2.308a.25.25 0 010 .384L8.41 4.658A.25.25 0 018 4.466z"/></svg>
                    </button>
                </div>
                <div class="styles-grid" id="stylesGrid">
                    <div class="loading-styles">
                        <svg class="loading-spinner" width="40" height="40" viewBox="0 0 40 40">
                            <circle cx="20" cy="20" r="18" fill="none" stroke="rgba(180,140,0,0.2)" stroke-width="3"/>
                            <circle cx="20" cy="20" r="18" fill="none" stroke="#c8960b" stroke-width="3" stroke-dasharray="90 90" stroke-linecap="round">
                                <animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="1s" repeatCount="indefinite"/>
                            </circle>
                        </svg>
                        <p>טוען סגנונות מהשרת...</p>
                    </div>
                </div>
                <div class="reset-style-section">
                    <button id="resetStyleBtn" class="reset-style-btn">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3a5 5 0 11-4.546 2.914.5.5 0 00-.908-.418A6 6 0 108 2v1z"/><path d="M8 4.466V.534a.25.25 0 00-.41-.192L5.23 2.308a.25.25 0 000 .384l2.36 1.966A.25.25 0 008 4.466z"/></svg>
                        Reset Style
                    </button>
                </div>
                <div id="styleStatus" class="status-console">בחר סגנון להחלת</div>
            </div>
            
            <!-- Animate Tab -->
            <div class="tab-content" id="animateTab">

  <!-- Preview Box -->
  <div class="anim-preview-box">
    <span class="anim-preview-text" id="animPreviewText">Hello World</span>
    <span class="anim-preview-label" id="animPreviewLabel">PREVIEW</span>
  </div>

  <!-- Entrance Section -->
  <div class="animate-section section-active" id="animEntranceSection">
    <div class="animate-section-title">
      <svg viewBox="0 0 12 12" fill="currentColor"><path d="M2 6h8M6 2l4 4-4 4"/></svg>
      Entrance
    </div>

    <div class="animate-row">
      <label>Type</label>
      <select class="animate-select" id="animEntranceType">
        <option value="none">אַף לֹא אֶחָד</option>
        <option value="fade">Fade In</option>
        <option value="slideUp" selected>Slide Up</option>
        <option value="slideDown">Slide Down</option>
        <option value="slideLeft">Slide from Right</option>
        <option value="scale">Scale In</option>
        <option value="rotate">Rotate In</option>
        <option value="blur">Blur In</option>
        <option value="drop">Drop In</option>
        <option value="typewriter">Typewriter</option>
      </select>
    </div>

    <div class="animate-row">
      <label>Per</label>
      <select class="animate-select" id="animEntrancePer">
        <option value="char">אוֹפִי</option>
        <option value="word">מִלָה</option>
      </select>
    </div>

    <div class="animate-row">
      <label>Duration</label>
      <div class="animate-slider-wrap">
        <input type="range" class="animate-slider" id="animEntranceDuration"
               min="0.1" max="2.0" step="0.05" value="0.5">
        <span class="animate-val" id="animEntranceDurationVal">0.5s</span>
      </div>
    </div>

    <div class="animate-row">
      <label>Delay</label>
      <div class="animate-slider-wrap">
        <input type="range" class="animate-slider" id="animEntranceDelay"
               min="0" max="0.3" step="0.01" value="0.04">
        <span class="animate-val" id="animEntranceDelayVal">0.04s</span>
      </div>
    </div>

    <div class="animate-row">
      <label>Speed</label>
      <div class="animate-speed-btns">
        <button class="speed-btn" data-anim-speed="slow"   data-dur="0.8"  data-delay="0.06">Slow</button>
        <button class="speed-btn active" data-anim-speed="medium" data-dur="0.5"  data-delay="0.04">Med</button>
        <button class="speed-btn" data-anim-speed="fast"   data-dur="0.22" data-delay="0.02">Fast</button>
      </div>
    </div>
  </div>

  <!-- Continuous Section -->
  <div class="animate-section" id="animContinuousSection">
    <div class="animate-section-title">
      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6" cy="6" r="4"/><path d="M6 2 A4 4 0 0 1 10 6"/></svg>
      Continuous
    </div>

    <div class="animate-row">
      <label>Type</label>
      <select class="animate-select" id="animContinuousType">
        <option value="none" selected>אַף לֹא אֶחָד</option>
        <option value="pulse">דוֹפֶק</option>
        <option value="float">לָצוּף</option>
        <option value="wigglePos">לְכַשְׁכֵּשׁ</option>
      </select>
    </div>

    <div class="animate-row">
      <label>מְהִירוּת</label>
      <div class="animate-slider-wrap">
        <input type="range" class="animate-slider" id="animContinuousSpeed"
               min="0.3" max="4.0" step="0.1" value="1.2">
        <span class="animate-val" id="animContinuousSpeedVal">1.2s</span>
      </div>
    </div>
  </div>

  <!-- Colors Section -->
  <div class="animate-section" id="animColorsSection">
    <div class="animate-section-title">
      <svg viewBox="0 0 12 12" fill="currentColor"><circle cx="4" cy="4" r="2"/><circle cx="8" cy="4" r="2"/><circle cx="6" cy="8" r="2"/></svg>
      Colors
    </div>

    <div class="ws-color-section">
      <div class="ws-color-label">מילוי טקסט</div>
      <div class="ae-color-row">
        <input type="color" class="ae-color-swatch" id="animTextColor" value="#ffffff">
        <input type="text"  class="ae-hex-input"    id="animTextColorHex" value="FFFFFF" maxlength="6">
        <div class="ae-color-presets">
          <button class="ae-color-dot" style="background:#ffffff" data-color="#ffffff" title="White"></button>
          <button class="ae-color-dot" style="background:#ffd700" data-color="#ffd700" title="Gold"></button>
          <button class="ae-color-dot" style="background:#f5c200" data-color="#f5c200" title="Yellow"></button>
          <button class="ae-color-dot" style="background:#ffaa00" data-color="#ffaa00" title="Amber"></button>
          <button class="ae-color-dot" style="background:#4bffa5" data-color="#4bffa5" title="Mint"></button>
          <button class="ae-color-dot" style="background:#4bc8ff" data-color="#4bc8ff" title="Sky"></button>
        </div>
      </div>
    </div>

    <div class="ws-color-section">
      <div class="ws-color-label">צל</div>
      <div class="ae-color-row">
        <input type="color" class="ae-color-swatch" id="animStrokeColor" value="#000000">
        <input type="text"  class="ae-hex-input"    id="animStrokeColorHex" value="000000" maxlength="6">
        <div class="ae-color-presets">
          <button class="ae-color-dot" style="background:#000000" data-color="#000000" title="Black"></button>
          <button class="ae-color-dot" style="background:#1a1200" data-color="#1a1200" title="Dark"></button>
          <button class="ae-color-dot" style="background:#3b2700" data-color="#3b2700" title="Brown"></button>
        </div>
      </div>
    </div>
  </div>

  <!-- Actions -->
  <div class="animate-actions">
    <button class="animate-apply-btn" id="animApplyBtn">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 6l3 3 5-5"/></svg>
      Apply to Selected
    </button>
    <button class="animate-clear-btn" id="animClearBtn">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 2l8 8M10 2L2 10"/></svg>
      Clear
    </button>
  </div>
  <div class="animate-info">&#9432; Works on selected text layers in the active composition</div>

</div>
        </div>
    </div>
</body>
</html>