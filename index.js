const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { COLORS } = require('../config'); 

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

// פונקציה שמפרמטת את תצוגת הקלפים
function formatHand(hand, hideSecond = false) {
    if (hideSecond) {
        return `\` ${hand[0]} \`, \` 🟥 \``; 
    }
    return hand.map(c => `\` ${c} \``).join(', ');
}

async function blackjack(message, args, user) {
    let betAmount;
    const raw = String(args[0] || "").toLowerCase();
    
    // בדיקת סוג ההימור והפיכתו למספרים מתאימים
    if (raw === "all") betAmount = user.cash;
    else if (raw === "half") betAmount = Math.floor(user.cash / 2);
    else betAmount = Math.floor(Number(raw));

    // הגנה בסיסית מפני הימורים לא תקינים או חריגה מהתקציב
    if (!betAmount || isNaN(betAmount) || betAmount <= 0 || betAmount > user.cash) {
        return message.reply("❌ סכום ההימור אינו תקין או שאין לך מספיק כסף.");
    }

    // הורדת כסף על ההימור הראשוני
    user.cash -= betAmount;

    // חוק 53% סיכוי שהבית/דילר ינצח
    const isRiggedLoss = Math.random() < 0.53;

    let playerHand = [drawCard(), drawCard()];
    let dealerHand = [drawCard(), drawCard()];

    let playerValue = calculateHandValue(playerHand);

    // בניית ה-Embed (תיקון ה-Template Literals עם גרש נטוי ` `)
    const buildEmbed = (status = 'active') => {
        let embedColor = 0xFEE75C; 
        let winBonusText = '';

        if (status === 'win') {
            embedColor = 0x57F287; 
        } else if (status === 'win_21') {
            embedColor = 0x57F287; 
            winBonusText = ' (💥 +30% Multiplier Bonus!)';
        } else if (status === 'lose') {
            embedColor = 0xED4245; 
        } else if (status === 'tie') {
            embedColor = 0xE67E22; 
        }

        return new EmbedBuilder()
            .setAuthor({ name: `\${message.author.username}'s Game`, iconURL: message.author.displayAvatarURL() })
            .setTitle(`🃏 Blackjack\${winBonusText}`)
            .setColor(embedColor)
            .addFields(
                { name: 'Your Hand', value: formatHand(playerHand), inline: false },
                { name: 'Value: ' + playerValue, value: '\u200b', inline: false },
                { name: 'Dealer', value: formatHand(dealerHand, status === 'active'), inline: false },
                { name: 'Value: ' + (status === 'active' ? calculateHandValue([dealerHand[0]]) : calculateHandValue(dealerHand)), value: '\u200b', inline: false }
            );
    };

    // תיקון קריטי: הכנסת המשתנים userId ו-betAmount בצורה דינמית לתוך ה-CustomId של הכפתורים
    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`bj:hit:message.author.id:{betAmount}`).setLabel('Hit').setStyle(ButtonStyle.Primary),       
        new ButtonBuilder().setCustomId(`bj:stand:message.author.id:{betAmount}`).setLabel('Stand').setStyle(ButtonStyle.Success),   
        new ButtonBuilder().setCustomId(`bj:double:message.author.id:{betAmount}`).setLabel('Double').setStyle(ButtonStyle.Danger),  
        new ButtonBuilder().setCustomId(`bj:split:message.author.id:{betAmount}`).setLabel('Split').setStyle(ButtonStyle.Secondary).setDisabled(true) 
    );

    // שליחת הודעת המשחק
    const gameMessage = await message.reply({
        embeds: [buildEmbed('active')],
        components: [row]
    });

    // שמירת המצב הזמני על גבי ההודעה
    gameMessage.gameState = {
        playerHand,
        dealerHand,
        isRiggedLoss,
        user
    };
}

async function handleBlackjackButton(interaction) {
    const [prefix, action, userId, betRaw] = interaction.customId.split(':');
    let betAmount = parseInt(betRaw);

    // וידוא שהמשתמש שלחץ הוא בעל המשחק
    if (interaction.user.id !== userId) {
        return interaction.reply({ content: '❌ זה לא המשחק שלך!', ephemeral: true });
    }

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
        else if (status === 'win_21') payout = Math.floor(betAmount * 2.3); 
        else if (status === 'tie') payout = betAmount;

        user.cash += payout; 

        // יצירת ה-Embed הסופי והסרת הכפתורים
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
        
        delete message.gameState; 
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
        betAmount = betAmount * 2; 

        playerHand.push(drawCard());
        playerValue = calculateHandValue(playerHand);

        if (playerValue > 21 || isRiggedLoss) {
            return finishGame('lose');
        }
        
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

    // עדכון תצוגה זמנית במהלך המשחק
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
