function predict(input) {
  const text = input.trim();

  const match = text.match(
    /^https?:\/\/discord\.com\/channels\/(\d+)\/(\d+)\/(\d+)$/
  );

  if (!match) {
    return {
      success: false,
      error: "קישור Discord לא תקין"
    };
  }

  return {
    success: true,
    guildId: match[1],
    channelId: match[2],
    messageId: match[3]
  };
}

function runPredict() {
  const input = document.getElementById("predictInput").value;
  const result = predict(input);

  const output = document.getElementById("output");

  if (!result.success) {
    output.textContent = `❌ ${result.error}`;
    return;
  }

  output.innerHTML = `
    ✅ קישור זוהה<br><br>
    🏠 Server ID: ${result.guildId}<br>
    💬 Channel ID: ${result.channelId}<br>
    📨 Message ID: ${result.messageId}
  `;
}