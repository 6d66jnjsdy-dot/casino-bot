const { getUser, saveData } = require("../database");
const { money, validBet } = require("../helpers");

// מפה לשמירת משחקים פעילים למניעת ספאם (נשמר לפי יוניק ID של המשתמש)
const activeGames = new Set();

async function cockfight(message, args, user) {
  const userId = message.author.id;

  // הגנה מפני הרצת פקודות במקביל
  if (activeGames.has(userId)) {
    return message.reply("❌ יש לך כבר קרב תרנגולים פעיל ברגע זה.");
  }

  // בדיקת תקינות ההימור (תומך גם ב-all, half וכו' דרך validBet)
  const bet = validBet(message, args);
  if (!bet) return;

  if (bet > user.cash) {
    return message.reply("❌ אין לך מספיק כסף בחשבון להימור זה.");
  }

  // הוספת המשתמש למשחקים פעילים
  activeGames.add(userId);

  try {
    // 1. הגרלת אחוז החוזק של התרנגול שלך (בין 50 ל-83)
    const strength = Math.floor(Math.random() * (83 - 50 + 1)) + 50;
    
    // 2. המרה של האחוז לערך עשרוני לצורך בדיקת זכייה
    const winChance = strength / 100;
    const won = Math.random() < winChance;

    // 3. עדכון היתרה בבסיס הנתונים
    if (won) {
      user.cash += bet; // המשתמש מקבל בחזרה את ההימור + סכום הזכייה (רווח נקי של גובה ההימור)
    } else {
      user.cash -= bet; // המשתמש מפסיד את גובה ההימור
    }

    // שמירת הנתונים החדשים
    saveData();

    // 4. בניית הודעת הפלט בהתאם לתוצאה בדיוק כמו בצילום המסך שלך
    if (won) {
      await message.reply(
        `Your chicken won the fight, you won ${bet} 💸🐔!\n\n` +
        `Your chicken's strength (chance of winning): ${strength}%\n` +
        `You now have ${user.cash} 💸`
      );
    } else {
      await message.reply(
        `Your chicken lost the fight... You lost ${bet} 💸🐔.`
      );
    }

  } catch (error) {
    console.error("Cockfight Error:", error);
    await message.reply("❌ התרחשה שגיאה במהלך הקרב.");
  } finally {
    // הסרת המשתמש מרשימת המשחקים הפעילים בסיום הקרב
    activeGames.delete(userId);
  }
}

// ייצוא הפונקציה (הסרנו את פונקציית הכפתורים הישנה שאין בה צורך יותר)
module.exports = {
  cockfight
};
