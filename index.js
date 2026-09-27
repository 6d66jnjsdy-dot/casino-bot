const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(__dirname));

app.get("/api/games", (req, res) => {
  const file = path.join(__dirname, "games.json");

  try {
    const data = fs.readFileSync(file, "utf8");
    res.type("json").send(data);
  } catch (error) {
    res.json({});
  }
});

app.use((req, res) => {
  res.sendFile(path.join(__dirname, "index.html"));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Mines Predict running on port ${PORT}`);
});