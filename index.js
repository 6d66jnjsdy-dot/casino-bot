const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const GAMES_FILE = path.join(__dirname, "games.json");

app.use(express.json());
app.use(express.static(__dirname));

function readGames() {
  try {
    if (!fs.existsSync(GAMES_FILE)) {
      fs.writeFileSync(GAMES_FILE, "{}");
    }

    return JSON.parse(fs.readFileSync(GAMES_FILE, "utf8"));
  } catch {
    return {};
  }
}

function saveGames(games) {
  fs.writeFileSync(
    GAMES_FILE,
    JSON.stringify(games, null, 2),
    "utf8"
  );
}

app.get("/api/games", (req, res) => {
  res.json(readGames());
});

app.post("/api/games", (req, res) => {
  const {
    messageId,
    guildId,
    channelId,
    bombs
  } = req.body;

  if (!messageId || !Array.isArray(bombs)) {
    return res.status(400).json({
      error: "messageId and bombs are required"
    });
  }

  const games = readGames();

  games[String(messageId)] = {
    messageId: String(messageId),
    guildId: guildId ? String(guildId) : null,
    channelId: channelId ? String(channelId) : null,
    bombs: bombs.map(Number),
    debug: true,
    createdAt: new Date().toISOString()
  };

  saveGames(games);

  res.json({
    success: true,
    game: games[String(messageId)]
  });
});

app.get("*splat", (req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Mines Predict running on port ${PORT}`);
});