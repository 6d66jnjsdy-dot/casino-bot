const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { COLORS } = require('../config'); // מייבא את מערך הצבעים של הבוט שלך

// פונקציית עזר להגרלת קלף
function drawCard() {
    const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    return values[Math.floor(Math.random() * values.length)];
}

// פונקציה לחישוב ערך היד (מתחשב ב-A כ-1 או 11)
function calculateHandValue(hand) {
    let value = 0;
    let aces = 0;
    for (const card of hand) {
        if (['J', 'Q', 'K'].includes(card)) value += 10;
        else if (card === 'A') { aces += 1; value += 11; }
        else value += parseInt(card);
    }
    while (value > 21 && aces > 0) { value -= 10; aces -= 1; }
    return value;
}

// פונקציה שמפרמטת את תצוגת הקלפים לפי התמונה ששלחת
function formatHand(hand, hideSecond = false) {
    if (hideSecond) {
        return `\` ${hand[0]} \`, \` 🟥 \``; // הקלף השני חסוי עם ריבוע אדום
    }
    return hand.map(c => `\` ${c} \``).join(', ');
}

async function blackjack(message, args, user) {
    // שליפת סכום ההימור מהפונקציה הגלובלית שנמצאת ב-index.js
    // (הפונקציה getBet מחזירה null אם ההימור לא תקין ומטפלת בזה בעצמה)
    const getBet = message.client.listeners('messageCreate')[0].toString().includes('getBet') 
        ? global.getBet 
        : null; 
    
    // בגלל ששאר הפקודות באינדקס משתמשות במבנה הזה, נשלוף את ה-args בצורה פשוטה
    let betAmount;
    const raw = String(args[0] || "").toLowerCase();
    if (raw === "all") betAmount = user.cash;
    else if (raw === "half") betAmount = Math.floor(user.cash / 2);
    else betAmount = Math.floor(Number(raw));

    if (!betAmount || isNaN(betAmount) || betAmount > user.cash) return; // הגנה בסיסית

    // הורדת כסף על ההימור הראשוני
    user.cash -= betAmount;

    // חוק 53% סיכוי שהבית/דילר ינצח
    const isRiggedLoss = Math.random() < 0.53;

    let playerHand = [drawCard(), drawCard()];
    let dealerHand = [drawCard(), drawCard()];

    let playerValue = calculateHandValue(playerHand);
    let dealerValue = calculateHandValue(dealerHand);

    // בניית ה-Embed אחד לאחד לפי צילום המסך (במצב פעיל הקו צהוב/זהב)
    const buildEmbed = (status = 'active') => {
        let embedColor = 0xFEE75C; // ברירת מחדל צהוב במהלך משחק
        let winBonusText = '';

        if (status === 'win') {
            embedColor = 0x57F287; // קו ירוק בווין
        } else if (status === 'win_21') {
            embedColor = 0x57F287; // קו ירוק ב-21
            winBonusText = ' (💥 +30% Multiplier Bonus!)';
        } else if (status === 'lose') {
            embedColor = 0xED4245; // קו אדום בהפסד
        } else if (status === 'tie') {
            embedColor = 0xE67E22; // קו כתום בתיקו
        }

        return new EmbedBuilder()
            .setAuthor({ name: `\${message.author.username}'s Game`, iconURL: message.author.displayAvatarURL() })
            .setTitle(`🃏 Blackjack\${winBonusText}`)
            .setColor(embedColor)
            .addFields(
                { name: 'Your Hand', value: formatHand(playerHand), inline: false },
                { name: 'Value: ' + playerValue, value: '\u200b', inline: false },
                { name: 'Dealer', value: formatHand(dealerHand, status === 'active'), inline: false },
                { name: 'Value: ' + (status === 'active' ? calculateHandValue([dealerHand[0]]) : dealerValue), value: '\u200b', inline: false }
            );
    };

    // יצירת שורת הכפתורים המעוצבת אחד לאחד לפי התמונה
    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`bj:hit:message.author.id:{betAmount}`).setLabel('Hit').setStyle(ButtonStyle.Primary),       // כחול
        new ButtonBuilder().setCustomId(`bj:stand:message.author.id:{betAmount}`).setLabel('Stand').setStyle(ButtonStyle.Success),   // ירוק
        new ButtonBuilder().setCustomId(`bj:double:message.author.id:{betAmount}`).setLabel('Double').setStyle(ButtonStyle.Danger),  // אדום
        new ButtonBuilder().setCustomId(`bj:split:message.author.id:{betAmount}`).setLabel('Split').setStyle(ButtonStyle.Secondary).setDisabled(true) // אפור מושבת
    );

    // שליחת המשחק
    const gameMessage = await message.reply({
        embeds: [buildEmbed('active')],
        components: [row]
    });

    // שמירת נתוני המשחק הזמניים על ההודעה כדי שהמנגנון ב-Interaction יוכל לקרוא אותם
    gameMessage.gameState = {
        playerHand,
        dealerHand,
        isRiggedLoss,
        user
    };
}

// פונקציית הטיפול בלחיצות על הכפתורים (שמופעלת מה-InteractionCreate באינדקס)
async function handleBlackjackButton(interaction) {
    const [prefix, action, userId, betRaw] = interaction.customId.split(':');
    let betAmount = parseInt(betRaw);

    // בדיקה שהמשתמש שלחץ הוא הבעלים של המשחק
    if (interaction.user.id !== userId) {
        return interaction.reply({ content: '❌ זה לא המשחק שלך!', ephemeral: true });
    }

    // שחזור המצב מתוך ההודעה
    const message = interaction.message;
    if (!message.gameState) {
        return interaction.reply({ content: '❌ משחק זה פג תוקף.', ephemeral: true });
    }

    let { playerHand, dealerHand, isRiggedLoss, user } = message.gameState;
    await interaction.deferUpdate();

    let playerValue = calculateHandValue(playerHand);
    let dealerValue = calculateHandValue(dealerHand);

    const finishGame = async (status) => {
        let payout = 0;
        if (status === 'win') payout = betAmount * 2;
        else if (status === 'win_21') payout = Math.floor(betAmount * 2.3); // תוספת 30% לרווח ב-21 מושלם (2.3 במקום 2)
        else if (status === 'tie') payout = betAmount;

        user.cash += payout; // עדכון ה-Database המקומי שלך

        // בניית ה-Embed הסופי (הצבעים ישתנו אוטומטית בפנים) והסרת הכפתורים
        const endEmbed = new EmbedBuilder()
            .setAuthor({ name: `\${interaction.user.username}'s Game`, iconURL: interaction.user.displayAvatarURL() })
            .setTitle(`🃏 Blackjack \${status === 'win_21' ? '(💥 21 מושלם!)' : ''}`)
            .setColor(status === 'lose' ? 0xED4245 : (status === 'tie' ? 0xE67E22 : 0x57F287))
            .addFields(
                { name: 'Your Hand', value: playerHand.map(c => `\` ${c} \``).join(', '), inline: false },
                { name: 'Value: ' + calculateHandValue(playerHand), value: '\u200b', inline: false },
                { name: 'Dealer', value: dealerHand.map(c => `\` ${c} \``).join(', '), inline: false },
                { name: 'Value: ' + calculateHandValue(dealerHand), value: '\u200b', inline: false }
            );

        await interaction.editReply({
            embeds: [endEmbed],
            components: []
        });
        
        delete message.gameState; // ניקוי הזיכרון
    };

    // --- כפתור HIT ---
    if (action === 'hit') {
        playerHand.push(drawCard());
        playerValue = calculateHandValue(playerHand);

        if (playerValue > 21 || isRiggedLoss) {
            return finishGame('lose');
        } else if (playerValue === 21) {
            return finishGame('win_21');
        }
    }

    // --- כפתור DOUBLE ---
    if (action === 'double') {
        if (user.cash < betAmount) {
            return interaction.followUp({ content: '❌ אין לך מספיק כסף בקופה כדי לבצע Double!', ephemeral: true });
        }
        user.cash -= betAmount;
        betAmount = betAmount * 2; // הכפלת סכום ההימור

        playerHand.push(drawCard());
        playerValue = calculateHandValue(playerHand);

        if (playerValue > 21 || isRiggedLoss) {
            return finishGame('lose');
        }
        
        // בבלאקג'ק, אחרי דאבל מקבלים קלף אחד והתור עובר ישר לדילר:
        while (dealerValue < 17) {
            dealerHand.push(drawCard());
            dealerValue = calculateHandValue(dealerHand);
        }
        if (dealerValue > 21 || playerValue > dealerValue) return finishGame(playerValue === 21 ? 'win_21' : 'win');
        else if (playerValue < dealerValue) return finishGame('lose');
        else return finishGame('tie');
    }

    // --- כפתור STAND ---
    if (action === 'stand') {
        while (dealerValue < 17) {
            dealerHand.push(drawCard());
            dealerValue = calculateHandValue(dealerHand);
        }

        if (isRiggedLoss) {
            return finishGame('lose');
        } else if (dealerValue > 21 || playerValue > dealerValue) {
            return finishGame(playerValue === 21 ? 'win_21' : 'win');
        } else if (playerValue < dealerValue) {
            return finishGame('lose');
        } else {
            return finishGame('tie');
        }
    }

    // עדכון המשחק הנוכחי על המסך במידה והמשחק עדיין פעיל (אחרי Hit רגיל)
    const updateEmbed = new EmbedBuilder()
        .setAuthor({ name: `\${interaction.user.username}'s Game`, iconURL: interaction.user.displayAvatarURL() })
        .setTitle(`🃏 Blackjack`)
        .setColor(0xFEE75C)
        .addFields(
            { name: 'Your Hand', value: playerHand.map(c => `\` ${c} \``).join(', '), inline: false },
            { name: 'Value: ' + playerValue, value: '\u200b', inline: false },
            { name: 'Dealer', value: formatHand(dealerHand, true), inline: false },
            { name: 'Value: ' + calculateHandValue([dealerHand[0]]), value: '\u200b', inline: false }
        );

    await interaction.editReply({
        embeds: [updateEmbed]
    });
}

module.exports = {
    blackjack,
    handleBlackjackButton
};
