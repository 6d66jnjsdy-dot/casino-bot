const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(__dirname));
app.use(express.json());

app.get("/api/games", (req, res) => {
  const file = path.join(__dirname, "games.json");

  try {
    const data = fs.readFileSync(file, "utf8");
    res.type("json").send(data);
  } catch {
    res.json({});
  }
});

app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});