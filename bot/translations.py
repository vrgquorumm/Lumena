"""Explicit display labels for AURELIA navigation."""
import re

LABELS = {
    "ru": {
        "Home": "Главная", "Profile": "Профиль", "Wallet": "Кошелёк",
        "Rewards": "Награды", "Daily": "Ежедневная награда", "Daily reward": "Ежедневная награда",
        "Quests": "Задания", "Streak": "Серия", "Achievements": "Достижения",
        "Social": "Соцсети", "Social Profile": "Социальный профиль",
        "Community": "Сообщество", "Links": "Ссылки", "Events": "События",
        "News": "Новости", "Settings": "Настройки", "Notifications": "Уведомления",
        "Language": "Язык", "Privacy": "Конфиденциальность", "Delete account": "Удалить профиль",
        "Confirm deletion": "Подтвердить удаление", "Cancel": "Отмена",
        "Claim reward": "Получить награду", "Claim quest completion": "Получить награду за задания",
        "Send": "Перевести", "Confirm send": "Подтвердить перевод",
        "History": "История", "Store": "Магазин", "Invite friends": "Пригласить друзей",
        "Invite friend": "Пригласить друга", "Referral Hub": "Центр приглашений",
        "Add LMN": "Заработать LMN", "Notify me": "Уведомить меня",
        "Remove me": "Не уведомлять", "Back": "Назад", "Copy link": "Скопировать ссылку",
        "Share": "Поделиться", "Open App": "Открыть приложение",
        "Your balance": "Ваш баланс", "day streak": "дней подряд",
        "Coming soon. AI is currently unavailable.": "Скоро. ИИ пока недоступен.",
        "Official links have not been configured.": "Официальные ссылки пока не настроены.",
        "No verified project feed is connected yet.": "Подтверждённый источник новостей ещё не подключён.",
        "Mini App is not configured yet.": "Мини-приложение ещё не настроено.",
        "Nothing here yet. Older legacy transactions are not itemized.": "Здесь пока пусто. Старые операции не детализированы.",
    },
    "sl": {
        "Home": "Domov", "Profile": "Profil", "Wallet": "Denarnica",
        "Rewards": "Nagrade", "Daily": "Dnevna nagrada", "Daily reward": "Dnevna nagrada",
        "Quests": "Naloge", "Streak": "Niz", "Achievements": "Dosežki",
        "Social": "Družabna omrežja", "Social Profile": "Družabni profil",
        "Community": "Skupnost", "Links": "Povezave", "Events": "Dogodki",
        "News": "Novice", "Settings": "Nastavitve", "Notifications": "Obvestila",
        "Language": "Jezik", "Privacy": "Zasebnost", "Delete account": "Izbriši profil",
        "Confirm deletion": "Potrdi izbris", "Cancel": "Prekliči",
        "Claim reward": "Prevzemi nagrado", "Claim quest completion": "Prevzemi nagrado za naloge",
        "Send": "Pošlji", "Confirm send": "Potrdi nakazilo",
        "History": "Zgodovina", "Store": "Trgovina", "Invite friends": "Povabi prijatelje",
        "Invite friend": "Povabi prijatelja", "Referral Hub": "Središče povabil",
        "Add LMN": "Zasluži LMN", "Notify me": "Obvesti me",
        "Remove me": "Odjavi me", "Back": "Nazaj", "Copy link": "Kopiraj povezavo",
        "Share": "Deli", "Open App": "Odpri aplikacijo",
        "Your balance": "Vaše stanje", "day streak": "dni zapored",
        "Coming soon. AI is currently unavailable.": "Kmalu. AI trenutno ni na voljo.",
        "Official links have not been configured.": "Uradne povezave še niso nastavljene.",
        "No verified project feed is connected yet.": "Preverjen vir novic še ni povezan.",
        "Mini App is not configured yet.": "Mini aplikacija še ni nastavljena.",
        "Nothing here yet. Older legacy transactions are not itemized.": "Tu še ni zapisov. Stare transakcije niso razčlenjene.",
    }
}

LABELS["ru"].update({
    "Help": "Помощь",
    "Welcome back": "С возвращением", "Welcome": "Добро пожаловать",
    "Level": "Уровень", "Daily reward claimed": "Ежедневная награда получена",
    "Daily reward available": "Ежедневная награда доступна",
    "Referrals": "Приглашения", "Earn LMN from rewards. Transfers require confirmation.":
        "Зарабатывайте LMN с помощью наград. Переводы требуют подтверждения.",
    "Protected bank": "Защищённый банк", "Term deposit": "Срочный вклад",
    "SEND LMN": "ПЕРЕВОД LMN",
    "Use /send [known Telegram ID or @username] [positive whole amount].":
        "Используйте /send [известный Telegram ID или @username] [целая положительная сумма].",
    "Confirm": "Подтвердите", "expires in 5 minutes": "действует 5 минут",
    "to #": "получателю #", "Status": "Статус", "Claimed today": "Получено сегодня",
    "Available": "Доступно", "days": "дней", "DAILY REWARD": "ЕЖЕДНЕВНАЯ НАГРАДА",
    "REWARDS": "НАГРАДЫ", "YOUR STREAK": "ВАША СЕРИЯ",
    "Return tomorrow": "Возвращайтесь завтра",
    "subject to account cap": "с учётом лимита счёта",
    "Current": "Текущая серия", "Best": "Рекорд",
    "Recorded daily rewards": "Учтённые ежедневные награды",
    "Claim on consecutive Kyiv calendar days to build your streak.":
        "Получайте награды несколько дней подряд по киевскому времени для увеличения серии.",
    "QUEST CENTER": "ЦЕНТР ЗАДАНИЙ", "Community messages": "Сообщений в сообществе",
    "3-day daily streak": "Трёхдневная серия наград",
    "Complete all three for 1,000 LMN + 75 XP.":
        "Выполните все три задания для получения 1 000 LMN и 75 XP.",
    "ACHIEVEMENTS": "ДОСТИЖЕНИЯ", "Unlocked": "Открыто",
    "Nothing here yet. Earn XP and claim daily rewards.":
        "Здесь пока пусто. Зарабатывайте XP и получайте ежедневные награды.",
    "A verified social profile integration is not connected yet.":
        "Интеграция социального профиля ещё не подключена.",
    "Official channel": "Официальный канал", "Website": "Сайт",
    "AI": "ИИ", "Other categories await verified event sources.":
        "Остальные категории ожидают подключённых источников событий.",
    "Daily and referral notices are delivered to users who started a private chat.":
        "Ежедневные уведомления и приглашения отправляются тем, кто начал личный чат.",
    "ON": "ВКЛ", "OFF": "ВЫКЛ", "SETTINGS": "НАСТРОЙКИ",
    "Selected": "Выбрано", "Deleting a profile does not erase LMN, XP, financial history or referral attribution.":
        "Удаление профиля не стирает LMN, XP, финансовую историю и данные приглашений.",
    "Delete AURELIA profile?": "Удалить профиль AURELIA?",
    "Your public profile and preferences will be removed. Financial history and attribution remain.":
        "Публичный профиль и настройки будут удалены. Финансовая история и приглашения сохранятся.",
    "YOUR REFERRALS": "ВАШИ ПРИГЛАШЕНИЯ", "Invited": "Приглашено",
    "Historical earnings are not itemized.": "Ранние начисления не детализированы.",
    "Invite link": "Ссылка для приглашения",
    "Bot username is not configured for invites.": "Имя бота для приглашений пока не настроено.",
    "Nothing here yet. Older legacy transactions are not itemized.":
        "Здесь пока пусто. Старые операции не детализированы.",
    "Purchases": "Покупки", "Purchases are currently unavailable. Your LMN is unchanged.":
        "Покупки пока недоступны. Ваши LMN сохранены.",
    "Open": "Открыть", "Share AURELIA": "Поделиться AURELIA",
    "Invite friends using your personal link.": "Приглашайте друзей по личной ссылке.",
    "A community and identity experience with rewards. AI is coming soon.":
        "Сообщество, профиль и награды. ИИ скоро появится.",
    "Community, identity and rewards. AI coming soon.":
        "Сообщество, профиль и награды. ИИ скоро появится.",
    "Core": "Главное", "Account": "Аккаунт", "Future": "Скоро",
    "Verify your account to continue.": "Подтвердите аккаунт, чтобы продолжить.",
    "Solve": "Решите", "Too many attempts. Try again in one minute.":
        "Слишком много попыток. Повторите через минуту.",
    "Open /start in a private chat with the bot to verify.":
        "Откройте /start в личном чате с ботом для подтверждения.",
    "Wrong answer. Open /start to try again.":
        "Неверный ответ. Откройте /start и повторите попытку.",
    "Verification expired. Open /start to try again.":
        "Время проверки истекло. Откройте /start и повторите попытку.",
    "Verify with /start in a private chat first.":
        "Сначала пройдите проверку через /start в личном чате.",
    "This screen belongs to another user or is invalid.":
        "Этот экран принадлежит другому пользователю или недействителен.",
    "This screen is no longer available.": "Этот экран уже недоступен.",
    "Invalid action": "Неверное действие",
    "Already claimed today.": "Сегодня награда уже получена.",
    "Transfer expired, invalid or already confirmed.":
        "Перевод истёк, недействителен или уже подтверждён.",
    "Complete all quests first or already claimed today.":
        "Сначала выполните все задания или вернитесь завтра.",
    "This action is unavailable.": "Это действие недоступно.",
    "Account storage is unavailable. No changes were applied.":
        "Хранилище аккаунта недоступно. Изменения не сохранены.",
    "Transfer rejected. Check recipient, balance, amount and account cap.":
        "Перевод отклонён. Проверьте получателя, баланс, сумму и лимит счёта.",
    "New referral joined AURELIA.": "Новый приглашённый присоединился к AURELIA.",
    "Daily reward claimed": "Ежедневная награда получена",
    "Your daily reward is available. Open /daily to claim.":
        "Ежедневная награда доступна. Откройте /daily, чтобы получить её.",
    "Telegram": "Telegram", "Instagram": "Instagram", "Threads": "Threads",
    "TikTok": "TikTok", "English": "English", "Slovenščina": "Slovenščina",
})

LABELS["sl"].update({
    "Help": "Pomoč",
    "Welcome back": "Dobrodošli nazaj", "Welcome": "Dobrodošli",
    "Level": "Raven", "Daily reward claimed": "Dnevna nagrada je prevzeta",
    "Daily reward available": "Dnevna nagrada je na voljo",
    "Referrals": "Povabila", "Earn LMN from rewards. Transfers require confirmation.":
        "LMN zaslužite z nagradami. Nakazila zahtevajo potrditev.",
    "Protected bank": "Zaščitena banka", "Term deposit": "Vezani depozit",
    "SEND LMN": "POŠLJI LMN",
    "Use /send [known Telegram ID or @username] [positive whole amount].":
        "Uporabite /send [znani Telegram ID ali @username] [pozitiven cel znesek].",
    "Confirm": "Potrdite", "expires in 5 minutes": "poteče čez 5 minut",
    "to #": "prejemniku #", "Status": "Stanje", "Claimed today": "Danes prevzeto",
    "Available": "Na voljo", "days": "dni", "DAILY REWARD": "DNEVNA NAGRADA",
    "REWARDS": "NAGRADE", "YOUR STREAK": "VAŠ NIZ",
    "Return tomorrow": "Vrnite se jutri",
    "subject to account cap": "ob upoštevanju omejitve računa",
    "Current": "Trenutni niz", "Best": "Najdaljši niz",
    "Recorded daily rewards": "Zabeležene dnevne nagrade",
    "Claim on consecutive Kyiv calendar days to build your streak.":
        "Nagrado prevzemajte zaporedne dni po kijevskem času, da podaljšate niz.",
    "QUEST CENTER": "SREDIŠČE NALOG", "Community messages": "Sporočila v skupnosti",
    "3-day daily streak": "Tridnevni niz dnevnih nagrad",
    "Complete all three for 1,000 LMN + 75 XP.":
        "Opravite vse tri naloge za 1.000 LMN in 75 XP.",
    "ACHIEVEMENTS": "DOSEŽKI", "Unlocked": "Odklenjeno",
    "Nothing here yet. Earn XP and claim daily rewards.":
        "Tu še ni dosežkov. Zaslužite XP in prevzemajte dnevne nagrade.",
    "A verified social profile integration is not connected yet.":
        "Integracija družabnega profila še ni povezana.",
    "Official channel": "Uradni kanal", "Website": "Spletno mesto",
    "AI": "UI", "Other categories await verified event sources.":
        "Druge kategorije čakajo na potrjene vire dogodkov.",
    "Daily and referral notices are delivered to users who started a private chat.":
        "Dnevna obvestila in povabila prejmejo uporabniki, ki so začeli zasebni klepet.",
    "ON": "VKLOP", "OFF": "IZKLOP", "SETTINGS": "NASTAVITVE",
    "Selected": "Izbrano", "Deleting a profile does not erase LMN, XP, financial history or referral attribution.":
        "Izbris profila ne izbriše LMN, XP, finančne zgodovine ali podatkov o povabilih.",
    "Delete AURELIA profile?": "Izbrisati profil AURELIA?",
    "Your public profile and preferences will be removed. Financial history and attribution remain.":
        "Javni profil in nastavitve bodo odstranjeni. Finančna zgodovina in povabila ostanejo.",
    "YOUR REFERRALS": "VAŠA POVABILA", "Invited": "Povabljeni",
    "Historical earnings are not itemized.": "Pretekli zaslužki niso razčlenjeni.",
    "Invite link": "Povezava za povabilo",
    "Bot username is not configured for invites.": "Ime bota za povabila še ni nastavljeno.",
    "Nothing here yet. Older legacy transactions are not itemized.":
        "Tu še ni zapisov. Stare transakcije niso razčlenjene.",
    "Purchases": "Nakupi", "Purchases are currently unavailable. Your LMN is unchanged.":
        "Nakupi trenutno niso na voljo. Vaš LMN je nespremenjen.",
    "Open": "Odpri", "Share AURELIA": "Deli AURELIA",
    "Invite friends using your personal link.": "Povabite prijatelje z osebno povezavo.",
    "A community and identity experience with rewards. AI is coming soon.":
        "Skupnost, identiteta in nagrade. UI prihaja kmalu.",
    "Community, identity and rewards. AI coming soon.":
        "Skupnost, identiteta in nagrade. UI prihaja kmalu.",
    "Core": "Osnovno", "Account": "Račun", "Future": "Prihodnost",
    "Verify your account to continue.": "Za nadaljevanje potrdite svoj račun.",
    "Solve": "Rešite", "Too many attempts. Try again in one minute.":
        "Preveč poskusov. Poskusite znova čez minuto.",
    "Open /start in a private chat with the bot to verify.":
        "Za preverjanje odprite /start v zasebnem klepetu z botom.",
    "Wrong answer. Open /start to try again.":
        "Napačen odgovor. Odprite /start in poskusite znova.",
    "Verification expired. Open /start to try again.":
        "Preverjanje je poteklo. Odprite /start in poskusite znova.",
    "Verify with /start in a private chat first.":
        "Najprej se preverite z /start v zasebnem klepetu.",
    "This screen belongs to another user or is invalid.":
        "Ta zaslon pripada drugemu uporabniku ali ni veljaven.",
    "This screen is no longer available.": "Ta zaslon ni več na voljo.",
    "Invalid action": "Neveljavno dejanje",
    "Already claimed today.": "Danes je nagrada že prevzeta.",
    "Transfer expired, invalid or already confirmed.":
        "Nakazilo je poteklo, ni veljavno ali je že potrjeno.",
    "Complete all quests first or already claimed today.":
        "Najprej opravite vse naloge ali se vrnite jutri.",
    "This action is unavailable.": "To dejanje ni na voljo.",
    "Account storage is unavailable. No changes were applied.":
        "Shramba računa ni na voljo. Spremembe niso bile shranjene.",
    "Transfer rejected. Check recipient, balance, amount and account cap.":
        "Nakazilo zavrnjeno. Preverite prejemnika, stanje, znesek in omejitev računa.",
    "New referral joined AURELIA.": "Nov povabljeni se je pridružil AURELIA.",
    "Daily reward claimed": "Dnevna nagrada je prevzeta",
    "Your daily reward is available. Open /daily to claim.":
        "Vaša dnevna nagrada je na voljo. Za prevzem odprite /daily.",
    "Telegram": "Telegram", "Instagram": "Instagram", "Threads": "Threads",
    "TikTok": "TikTok", "English": "English", "Slovenščina": "Slovenščina",
})

LABELS["ru"].update({
    "App": "Приложение", "SOCIAL": "СОЦСЕТИ", "LINKS": "ССЫЛКИ",
    "COMMUNITY": "СООБЩЕСТВО", "EVENTS": "СОБЫТИЯ", "NEWS": "НОВОСТИ",
    "HISTORY_REWARDS": "ИСТОРИЯ НАГРАД", "HISTORY_REFERRALS": "ИСТОРИЯ ПРИГЛАШЕНИЙ",
    "HISTORY_QUESTS": "ИСТОРИЯ ЗАДАНИЙ", "HISTORY_PURCHASES": "ИСТОРИЯ ПОКУПОК",
    "HISTORY_ACHIEVEMENTS": "ИСТОРИЯ ДОСТИЖЕНИЙ",
    "HISTORY": "ИСТОРИЯ", "LEDGER": "ОПЕРАЦИИ", "STORE": "МАГАЗИН",
    "Ai": "ИИ", "Send to #": "Отправлено получателю #",
    "Received from #": "Получено от #", "Quest completion": "Выполнение заданий",
    "Referral": "Реферальная награда", "first_message": "Первое слово",
    "first_100xp": "Искра", "xp_1500": "Опытный участник",
    "legend": "Легенда", "streak_7": "Неделя подряд",
    "streak_30": "Месяц подряд", "rich_1m": "Миллионер",
    "rich_1b": "Миллиардер", "married": "Историческая свадьба",
    "gambler": "Исторический игрок", "winner": "Исторический победитель",
})
LABELS["sl"].update({
    "App": "Aplikacija", "SOCIAL": "DRUŽABNA OMREŽJA", "LINKS": "POVEZAVE",
    "COMMUNITY": "SKUPNOST", "EVENTS": "DOGODKI", "NEWS": "NOVICE",
    "HISTORY_REWARDS": "ZGODOVINA NAGRAD", "HISTORY_REFERRALS": "ZGODOVINA POVABIL",
    "HISTORY_QUESTS": "ZGODOVINA NALOG", "HISTORY_PURCHASES": "ZGODOVINA NAKUPOV",
    "HISTORY_ACHIEVEMENTS": "ZGODOVINA DOSEŽKOV",
    "HISTORY": "ZGODOVINA", "LEDGER": "TRANSAKCIJE", "STORE": "TRGOVINA",
    "Ai": "UI", "Send to #": "Poslano prejemniku #",
    "Received from #": "Prejeto od #", "Quest completion": "Opravljene naloge",
    "Referral": "Nagrada za povabilo", "first_message": "Prva beseda",
    "first_100xp": "Iskra", "xp_1500": "Izkušen uporabnik",
    "legend": "Legenda", "streak_7": "Teden zapored",
    "streak_30": "Mesec zapored", "rich_1m": "Milijonar",
    "rich_1b": "Milijarder", "married": "Pretekla poroka",
    "gambler": "Pretekli igralec", "winner": "Pretekli zmagovalec",
})

LANGUAGES = {
    "en": ("🇬🇧", "English"), "ru": ("🇷🇺", "Русский"),
    "uk": ("🇺🇦", "Українська"), "be": ("🇧🇾", "Беларуская"),
    "kk": ("🇰🇿", "Қазақша"), "hy": ("🇦🇲", "Հայերեն"),
    "az": ("🇦🇿", "Azərbaycanca"), "ky": ("🇰🇬", "Кыргызча"),
    "tg": ("🇹🇯", "Тоҷикӣ"), "tk": ("🇹🇲", "Türkmençe"),
    "uz": ("🇺🇿", "O‘zbekcha"), "ro": ("🇲🇩", "Română (Moldova)"),
    "ka": ("🇬🇪", "ქართული"), "sl": ("🇸🇮", "Slovenščina"),
}

# Core navigation, language selection, and account-safety messages for the
# national languages of CIS states (including associated Turkmenistan and
# Moldova), together with Ukrainian. Unlisted long-form copy remains in English.
_CORE = {
    "uk": {
        "Home": "Головна", "Profile": "Профіль", "Wallet": "Гаманець",
        "Rewards": "Нагороди", "Daily": "Щоденна нагорода", "Quests": "Завдання",
        "Social": "Соцмережі", "Community": "Спільнота", "Events": "Події",
        "News": "Новини", "Settings": "Налаштування", "Language": "Мова",
        "Notifications": "Сповіщення", "Back": "Назад", "Cancel": "Скасувати",
        "Help": "Допомога", "Select your preferred language.": "Виберіть бажану мову.",
        "Selected": "Вибрано", "Open": "Відкрити", "Share": "Поділитися",
        "Solve": "Розв’яжіть", "Already claimed today.": "Сьогодні нагороду вже отримано.",
        "Verify your account to continue.": "Підтвердьте обліковий запис, щоб продовжити.",
        "Account storage is unavailable. No changes were applied.":
            "Сховище облікового запису недоступне. Зміни не збережено.",
    },
    "be": {
        "Home": "Галоўная", "Profile": "Профіль", "Wallet": "Кашалёк",
        "Rewards": "Узнагароды", "Daily": "Штодзённая ўзнагарода", "Quests": "Заданні",
        "Social": "Сацыяльныя сеткі", "Community": "Супольнасць", "Events": "Падзеі",
        "News": "Навіны", "Settings": "Налады", "Language": "Мова",
        "Notifications": "Апавяшчэнні", "Back": "Назад", "Cancel": "Скасаваць",
        "Help": "Дапамога", "Select your preferred language.": "Выберыце пажаданую мову.",
        "Selected": "Выбрана", "Open": "Адкрыць", "Share": "Падзяліцца",
        "Solve": "Рашыце", "Already claimed today.": "Сёння ўзнагарода ўжо атрымана.",
        "Verify your account to continue.": "Пацвердзіце ўліковы запіс, каб працягнуць.",
    },
    "kk": {
        "Home": "Басты бет", "Profile": "Профиль", "Wallet": "Әмиян",
        "Rewards": "Сыйақылар", "Daily": "Күнделікті сыйақы", "Quests": "Тапсырмалар",
        "Social": "Әлеуметтік желілер", "Community": "Қауымдастық", "Events": "Оқиғалар",
        "News": "Жаңалықтар", "Settings": "Баптаулар", "Language": "Тіл",
        "Notifications": "Хабарландырулар", "Back": "Артқа", "Cancel": "Болдырмау",
        "Help": "Көмек", "Select your preferred language.": "Қалаған тіліңізді таңдаңыз.",
        "Selected": "Таңдалды", "Open": "Ашу", "Share": "Бөлісу",
        "Solve": "Шешіңіз", "Already claimed today.": "Бүгінгі сыйақы алынды.",
        "Verify your account to continue.": "Жалғастыру үшін тіркелгіңізді растаңыз.",
    },
    "hy": {
        "Home": "Գլխավոր", "Profile": "Պրոֆիլ", "Wallet": "Դրամապանակ",
        "Rewards": "Պարգևներ", "Daily": "Օրական պարգև", "Quests": "Առաջադրանքներ",
        "Social": "Սոցիալական ցանցեր", "Community": "Համայնք",
        "Events": "Իրադարձություններ", "News": "Նորություններ",
        "Settings": "Կարգավորումներ", "Language": "Լեզու", "Notifications": "Ծանուցումներ",
        "Back": "Հետ", "Cancel": "Չեղարկել", "Help": "Օգնություն",
        "Select your preferred language.": "Ընտրեք նախընտրելի լեզուն։",
        "Selected": "Ընտրված է", "Open": "Բացել", "Share": "Կիսվել",
        "Solve": "Լուծեք", "Already claimed today.": "Այսօրվա պարգևն արդեն ստացվել է։",
        "Verify your account to continue.": "Շարունակելու համար հաստատեք ձեր հաշիվը։",
    },
    "az": {
        "Home": "Ana səhifə", "Profile": "Profil", "Wallet": "Pulqabı",
        "Rewards": "Mükafatlar", "Daily": "Gündəlik mükafat", "Quests": "Tapşırıqlar",
        "Social": "Sosial şəbəkələr", "Community": "İcma", "Events": "Tədbirlər",
        "News": "Xəbərlər", "Settings": "Parametrlər", "Language": "Dil",
        "Notifications": "Bildirişlər", "Back": "Geri", "Cancel": "Ləğv et",
        "Help": "Kömək", "Select your preferred language.": "İstədiyiniz dili seçin.",
        "Selected": "Seçildi", "Open": "Aç", "Share": "Paylaş",
        "Solve": "Həll edin", "Already claimed today.": "Bugünkü mükafat artıq alınıb.",
        "Verify your account to continue.": "Davam etmək üçün hesabınızı təsdiqləyin.",
    },
    "ky": {
        "Home": "Башкы бет", "Profile": "Профиль", "Wallet": "Капчык",
        "Rewards": "Сыйлыктар", "Daily": "Күнүмдүк сыйлык", "Quests": "Тапшырмалар",
        "Social": "Социалдык тармактар", "Community": "Коомчулук",
        "Events": "Окуялар", "News": "Жаңылыктар", "Settings": "Жөндөөлөр",
        "Language": "Тил", "Notifications": "Билдирмелер", "Back": "Артка",
        "Cancel": "Жокко чыгаруу", "Help": "Жардам",
        "Select your preferred language.": "Каалаган тилиңизди тандаңыз.",
        "Selected": "Тандалды", "Open": "Ачуу", "Share": "Бөлүшүү",
        "Solve": "Чечиңиз", "Already claimed today.": "Бүгүнкү сыйлык мурунтан алынган.",
        "Verify your account to continue.": "Улантуу үчүн аккаунтуңузду ырастаңыз.",
    },
    "tg": {
        "Home": "Саҳифаи асосӣ", "Profile": "Профил", "Wallet": "Ҳамён",
        "Rewards": "Мукофотҳо", "Daily": "Мукофоти ҳаррӯза", "Quests": "Вазифаҳо",
        "Social": "Шабакаҳои иҷтимоӣ", "Community": "Ҷомеа", "Events": "Рӯйдодҳо",
        "News": "Хабарҳо", "Settings": "Танзимот", "Language": "Забон",
        "Notifications": "Огоҳиномаҳо", "Back": "Бозгашт",
        "Cancel": "Бекор кардан", "Help": "Кӯмак",
        "Select your preferred language.": "Забони дилхоҳатонро интихоб кунед.",
        "Selected": "Интихоб шуд", "Open": "Кушодан", "Share": "Мубодила кардан",
        "Solve": "Ҳал кунед", "Already claimed today.": "Мукофоти имрӯз аллакай гирифта шудааст.",
        "Verify your account to continue.": "Барои идома ҳисобатонро тасдиқ кунед.",
    },
    "tk": {
        "Home": "Baş sahypa", "Profile": "Profil", "Wallet": "Gapjyk",
        "Rewards": "Baýraklar", "Daily": "Gündelik baýrak", "Quests": "Tabşyryklar",
        "Social": "Sosial ulgamlar", "Community": "Jemgyýet", "Events": "Wakalar",
        "News": "Täzelikler", "Settings": "Sazlamalar", "Language": "Dil",
        "Notifications": "Bildirişler", "Back": "Yza", "Cancel": "Ýatyr",
        "Help": "Kömek", "Select your preferred language.": "Isleýän diliňizi saýlaň.",
        "Selected": "Saýlandy", "Open": "Aç", "Share": "Paýlaş",
        "Solve": "Çözüň", "Already claimed today.": "Şu günki baýrak eýýäm alyndy.",
        "Verify your account to continue.": "Dowam etmek üçin hasabyňyzy tassyklaň.",
    },
    "uz": {
        "Home": "Bosh sahifa", "Profile": "Profil", "Wallet": "Hamyon",
        "Rewards": "Mukofotlar", "Daily": "Kunlik mukofot", "Quests": "Vazifalar",
        "Social": "Ijtimoiy tarmoqlar", "Community": "Hamjamiyat", "Events": "Tadbirlar",
        "News": "Yangiliklar", "Settings": "Sozlamalar", "Language": "Til",
        "Notifications": "Bildirishnomalar", "Back": "Orqaga", "Cancel": "Bekor qilish",
        "Help": "Yordam", "Select your preferred language.": "Oʻzingizga qulay tilni tanlang.",
        "Selected": "Tanlandi", "Open": "Ochish", "Share": "Ulashish",
        "Solve": "Yeching", "Already claimed today.": "Bugungi mukofot allaqachon olingan.",
        "Verify your account to continue.": "Davom etish uchun hisobingizni tasdiqlang.",
    },
    "ro": {
        "Home": "Acasă", "Profile": "Profil", "Wallet": "Portofel",
        "Rewards": "Recompense", "Daily": "Recompensă zilnică", "Quests": "Misiuni",
        "Social": "Rețele sociale", "Community": "Comunitate", "Events": "Evenimente",
        "News": "Noutăți", "Settings": "Setări", "Language": "Limbă",
        "Notifications": "Notificări", "Back": "Înapoi", "Cancel": "Anulează",
        "Help": "Ajutor", "Select your preferred language.": "Alegeți limba preferată.",
        "Selected": "Selectat", "Open": "Deschide", "Share": "Distribuie",
        "Solve": "Rezolvați", "Already claimed today.": "Recompensa de astăzi a fost deja revendicată.",
        "Verify your account to continue.": "Verificați-vă contul pentru a continua.",
    },
    "ka": {
        "Home": "მთავარი", "Profile": "პროფილი", "Wallet": "საფულე",
        "Rewards": "ჯილდოები", "Daily": "დღიური ჯილდო", "Quests": "დავალებები",
        "Social": "სოციალური ქსელები", "Community": "საზოგადოება",
        "Events": "ღონისძიებები", "News": "სიახლეები", "Settings": "პარამეტრები",
        "Language": "ენა", "Notifications": "შეტყობინებები", "Back": "უკან",
        "Cancel": "გაუქმება", "Help": "დახმარება",
        "Select your preferred language.": "აირჩიეთ სასურველი ენა.",
        "Selected": "არჩეულია", "Open": "გახსნა", "Share": "გაზიარება",
        "Solve": "ამოხსენით", "Already claimed today.": "დღევანდელი ჯილდო უკვე მიღებულია.",
        "Verify your account to continue.": "გასაგრძელებლად დაადასტურეთ თქვენი ანგარიში.",
    },
}
for _code, _words in _CORE.items():
    LABELS.setdefault(_code, {}).update(_words)


def translate(text, language):
    """Translate labels while preserving URLs; IDs and callback data are never touched."""
    words = LABELS.get(language, {})
    if not words:
        return text
    urls = []
    def protect(match):
        urls.append(match.group())
        return f"\x00URL{len(urls) - 1}\x00"
    text = re.sub(r"https://[^\s<>]+", protect, text)
    for english, localized in sorted(words.items(), key=lambda item: -len(item[0])):
        text = re.sub(r"(?<![A-Za-z/@])" + re.escape(english) + r"(?![A-Za-z_])",
                      lambda _: localized, text)
    for index, url in enumerate(urls):
        text = text.replace(f"\x00URL{index}\x00", url)
    return text