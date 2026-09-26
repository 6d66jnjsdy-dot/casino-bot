const { EmbedBuilder } = require('discord.js');

function createBlackjackEmbed(status, playerHand, dealerHand, playerScore, dealerScore, betAmount) {
    let embedColor;
    let title;
    let finalPayout = betAmount;

    // קביעת צבע הקו בצד שמאל והכותרת לפי התוצאה
    switch (status.toLowerCase()) {
        case 'win':
            embedColor = 0x2ecc71; // קו ירוק
            title = '🏆 ניצחון! (53% סיכוי)';
            finalPayout = betAmount * 2; // תשלום רגיל פי 2
            break;
            
        case 'blackjack': // מצב של 21 ישר
            embedColor = 0x2ecc71; // קו ירוק
            title = '💥 בלאקג'ק! 21 מושלם';
            // הוספת עוד 30% לרווח (במקום פי 2, מקבלים פי 2.3)
            finalPayout = Math.floor(betAmount * 2.3); 
            break;

        case 'lose':
            embedColor = 0xe74c3c; // קו אדום
            title = '❌ הפסד!';
            finalPayout = 0;
            break;

        case 'tie':
        case 'push':
            embedColor = 0xe67e22; // קו כתום
            title = '🤝 תיקו!';
            finalPayout = betAmount; // הכסף חוזר
            break;

        default:
            embedColor = 0x3498db; // כחול למצב משחק פעיל
            title = '🃏 משחק בלאקג'ק פעיל';
    }

    // יצירת ה-Embed המעוצב בדיוק לפי הבקשה
    const blackjackEmbed = new EmbedBuilder()
        .setColor(embedColor)
        .setTitle(title)
        .setDescription(`תוצאות הסיבוב הנוכחי:`)
        .addFields(
            { name: 'היד שלך', value: `${playerHand.join(', ')} (סה"כ: ${playerScore})`, inline: true },
            { name: 'היד של הדילר', value: `${dealerHand.join(', ')} (סה"כ: ${dealerScore})`, inline: true },
            { name: '💰 הימור מקורי', value: `${betAmount} מטבעות`, inline: false },
            { name: '💵 רווח סופי', value: `${finalPayout} מטבעות`, inline: false }
        )
        .setTimestamp();

    return blackjackEmbed;
}

module.exports = { createBlackjackEmbed };
