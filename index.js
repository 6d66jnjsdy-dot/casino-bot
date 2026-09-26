<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Casino Bot Dashboard</title>

  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: Arial, sans-serif;
    }

    body {
      min-height: 100vh;
      background:
        radial-gradient(circle at top, #292929 0%, #111 45%, #080808 100%);
      color: #fff;
    }

    header {
      padding: 25px;
      text-align: center;
      border-bottom: 1px solid #333;
      background: rgba(10, 10, 10, .85);
    }

    header h1 {
      font-size: 32px;
      margin-bottom: 8px;
    }

    header p {
      color: #aaa;
    }

    .container {
      width: min(1100px, 92%);
      margin: 30px auto;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
      margin-bottom: 25px;
    }

    .stat {
      background: #171717;
      border: 1px solid #333;
      border-radius: 15px;
      padding: 22px;
      text-align: center;
    }

    .stat h2 {
      color: #f39c12;
      font-size: 28px;
      margin-bottom: 6px;
    }

    .stat p {
      color: #999;
    }

    .section {
      background: #151515;
      border: 1px solid #303030;
      border-radius: 18px;
      padding: 25px;
      margin-bottom: 20px;
    }

    .section h2 {
      margin-bottom: 18px;
      color: #f39c12;
    }

    .commands {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }

    .command {
      background: #202020;
      border: 1px solid #383838;
      border-radius: 12px;
      padding: 15px;
      transition: .2s;
    }

    .command:hover {
      transform: translateY(-2px);
      border-color: #f39c12;
    }

    .command code {
      color: #2ecc71;
      font-size: 17px;
      font-weight: bold;
    }

    .command p {
      color: #aaa;
      margin-top: 7px;
      font-size: 14px;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: #2ecc71;
      font-weight: bold;
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: #2ecc71;
      box-shadow: 0 0 10px #2ecc71;
    }

    .rules {
      line-height: 1.9;
      color: #ccc;
    }

    .rules strong {
      color: #fff;
    }

    footer {
      text-align: center;
      padding: 25px;
      color: #666;
    }

    @media (max-width: 600px) {
      header h1 {
        font-size: 25px;
      }

      .container {
        width: 94%;
      }

      .section {
        padding: 18px;
      }
    }
  </style>
</head>

<body>

<header>
  <h1>🎰 Casino Bot</h1>
  <p>Casino & Economy Discord Bot</p>
</header>

<div class="container">

  <div class="stats">
    <div class="stat">
      <h2>🎮</h2>
      <p>Casino Games</p>
    </div>

    <div class="stat">
      <h2>💰</h2>
      <p>Economy System</p>
    </div>

    <div class="stat">
      <h2>💾</h2>
      <p>Persistent Data</p>
    </div>

    <div class="stat">
      <h2>
        <span class="status">
          <span class="dot"></span>
          Online
        </span>
      </h2>
      <p>Bot Status</p>
    </div>
  </div>

  <div class="section">
    <h2>🎮 משחקים</h2>

    <div class="commands">

      <div class="command">
        <code>$bj</code>
        <p>Blackjack</p>
      </div>

      <div class="command">
        <code>$ht</code>
        <p>Coin Flip</p>
      </div>

      <div class="command">
        <code>$hl</code>
        <p>Higher / Lower</p>
      </div>

      <div class="command">
        <code>$cf</code>
        <p>Cockfight — 50/50</p>
      </div>

      <div class="command">
        <code>$mines</code>
        <p>Mines</p>
      </div>

      <div class="command">
        <code>$gm</code>
        <p>Gold Mine</p>
      </div>

      <div class="command">
        <code>$slots</code>
        <p>Slots</p>
      </div>

      <div class="command">
        <code>$roulette</code>
        <p>Roulette</p>
      </div>

      <div class="command">
        <code>$wheel</code>
        <p>Wheel</p>
      </div>

      <div class="command">
        <code>$crash</code>
        <p>Crash</p>
      </div>

    </div>
  </div>

  <div class="section">
    <h2>💰 כלכלה</h2>

    <div class="commands">

      <div class="command">
        <code>$balance</code>
        <p>בדיקת היתרה</p>
      </div>

      <div class="command">
        <code>$daily</code>
        <p>Daily reward — פעם ב־24 שעות</p>
      </div>

      <div class="command">
        <code>$work</code>
        <p>עבודה וקבלת כסף</p>
      </div>

      <div class="command">
        <code>$crime</code>
        <p>Crime עם סיכוי להיתפס</p>
      </div>

      <div class="command">
        <code>$rob @user</code>
        <p>ניסיון שוד של משתמש אחר</p>
      </div>

      <div class="command">
        <code>$top</code>
        <p>טבלת המובילים</p>
      </div>

    </div>
  </div>

  <div class="section">
    <h2>⚙️ הגדרות המשחקים</h2>

    <div class="rules">

      <p>🟢 <strong>ניצחון:</strong> הודעה בצבע ירוק.</p>

      <p>🔴 <strong>הפסד:</strong> הודעה בצבע אדום.</p>

      <p>🟠 <strong>משחק פעיל:</strong> הודעה בצבע כתום.</p>

      <p>🐔 <strong>Cockfight:</strong> סיכוי קבוע של 50%.</p>

      <p>🚔 <strong>Crime:</strong> 12% סיכוי להיתפס, ללא קנס במקרה של תפיסה.</p>

      <p>🕵️ <strong>Rob:</strong> 20% סיכוי להיתפס כאשר למטרה יש כסף,
      ו־12% כאשר אין לה כסף.</p>

      <p>💣 <strong>Mines:</strong> השהיה של 550ms בין לחיצות.</p>

      <p>🎡 <strong>Roulette:</strong> ספירה לאחור של 10 שניות.</p>

      <p>🎰 <strong>Slots:</strong> סיכוי הזכייה מופחת ב־4%.</p>

      <p>⬆️⬇️ <strong>Higher / Lower:</strong> סיכוי הזכייה מופחת ב־2%.</p>

      <p>🚀 <strong>Crash:</strong> מכפיל מתעדכן עם אנימציה.</p>

      <p>🃏 <strong>Blackjack:</strong> קלפים מוצגים בצורה של קלפים אמיתיים.</p>

      <p>❌ <strong>Random:</strong> המשחק הוסר מהבוט.</p>

      <p>☀️ <strong>Daily:</strong> הפקודה הישנה <code>$summer</code>
      הוחלפה ב־<code>$daily</code>.</p>

    </div>
  </div>

  <div class="section">
    <h2>💾 שמירת נתונים</h2>

    <div class="rules">
      <p>היתרות והנתונים נשמרים בקובץ <strong>data.json</strong>.</p>
      <p>קיימת שמירת גיבוי כדי לצמצם אובדן נתונים במקרה של תקלה.</p>
      <p>הנתונים נשמרים גם לפני כיבוי התהליך.</p>
      <p>הבוט יכול להמשיך עם אותם balances גם לאחר Restart.</p>
    </div>
  </div>

  <div class="section">
    <h2>🛠️ טכנולוגיה</h2>

    <div class="rules">
      <p><strong>Node.js</strong></p>
      <p><strong>discord.js v14</strong></p>
      <p><strong>Express</strong> — Keep Alive</p>
      <p><strong>JSON Database</strong> — שמירת נתונים</p>
    </div>
  </div>

  <div class="section">
    <h2>🔒 אבטחה</h2>

    <div class="rules">
      <p>הרשאות Admin צריכות להיבדק בצד השרת.</p>
      <p>אין לשים Bot Token בתוך קובץ HTML.</p>
      <p>את ה־Token יש לשמור כ־Environment Variable.</p>
    </div>
  </div>

</div>

<footer>
  Casino Bot Dashboard
</footer>

</body>
</html>