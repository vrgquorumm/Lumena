import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion';
import { useRef, useState } from 'react';
import { 
  Coins, 
  Heart, 
  ShieldAlert, 
  Link as LinkIcon, 
  Gamepad2, 
  UserCircle, 
  CheckCircle2, 
  Wand2,
  ChevronDown,
  Terminal,
  MessageSquareText,
  BookOpen,
  Hash,
  Users,
  Radio,
  ChevronRight,
  ExternalLink,
  Globe,
  Send,
  ScrollText,
  ListChecks
} from 'lucide-react';
import { FloatingButton } from '@/components/FloatingButton';

const CHAT_URL    = "https://t.me/+_K2SJRYIhq9hYjFi";
const CHANNEL_URL = "https://t.me/lmnfff";
const BOT_URL     = "https://t.me/LumenarAi_Bot";

const COMMAND_CATEGORIES = [
  {
    label: "💰 Економіка",
    color: "text-yellow-400",
    commands: [
      { cmd: "/balance",  desc: "Переглянути баланс LMN" },
      { cmd: "/work",     desc: "Попрацювати та заробити LMN (кд 1 год)" },
      { cmd: "/fish",     desc: "Порибалити за LMN (кд 2 год)" },
      { cmd: "/casino",   desc: "Поставити LMN у казино" },
      { cmd: "/slots",    desc: "Зіграти в слоти" },
      { cmd: "/rob",      desc: "Пограбувати учасника (ризик)" },
      { cmd: "/give",     desc: "Подарувати LMN іншому" },
      { cmd: "/richest",  desc: "Топ багатіїв чату" },
    ]
  },
  {
    label: "💑 Соціум та Аура",
    color: "text-pink-400",
    commands: [
      { cmd: "/marry",    desc: "Зробити пропозицію (реплай)" },
      { cmd: "/divorce",  desc: "Розлучитися" },
      { cmd: "/marriages",desc: "Список пар у чаті" },
      { cmd: "/rep",      desc: "Дати репутацію (раз на день)" },
      { cmd: "/aura",     desc: "Переглянути свою ауру %" },
      { cmd: "/topaura",  desc: "Топ аури в чаті" },
      { cmd: "/checkin",  desc: "Щоденна відмітка (стрік)" },
      { cmd: "/streak",   desc: "Переглянути стрік" },
      { cmd: "/topstreak",desc: "Топ стріків" },
      { cmd: "/ship",     desc: "Сумісність двох учасників" },
      { cmd: "/couple",   desc: "Знайти ідеальну пару в чаті" },
      { cmd: "/serenade", desc: "♪ Серенада комусь" },
    ]
  },
  {
    label: "🛡 Модерація",
    color: "text-red-400",
    commands: [
      { cmd: "/mute",    desc: "Замовкнути учасника [реплай/час]" },
      { cmd: "/unmute",  desc: "Зняти мут" },
      { cmd: "/ban",     desc: "Заблокувати в чаті" },
      { cmd: "/unban",   desc: "Розблокувати" },
      { cmd: "/kick",    desc: "Вигнати з чату" },
      { cmd: "/warn",    desc: "Видати попередження (3 = бан)" },
      { cmd: "/unwarn",  desc: "Зняти попередження" },
      { cmd: "/purge",   desc: "Видалити останні N повідомлень" },
      { cmd: "/ro",      desc: "Read-only режим для учасника" },
      { cmd: "/pin",     desc: "Закріпити повідомлення" },
      { cmd: "/roles",   desc: "Переглянути ролі команди" },
    ]
  },
  {
    label: "🎮 Ігри та Розваги",
    color: "text-green-400",
    commands: [
      { cmd: "/roulette", desc: "Почати/приєднатись до рулетки" },
      { cmd: "/hangman",  desc: "Гра у шибеницю" },
      { cmd: "/truth",    desc: "Запитання правда" },
      { cmd: "/dare",     desc: "Виклик на сміливість" },
      { cmd: "/riddle",   desc: "Загадка" },
      { cmd: "/coin",     desc: "Підкинути монету" },
    ]
  },
  {
    label: "👤 Профіль",
    color: "text-purple-400",
    commands: [
      { cmd: "/profile",    desc: "Переглянути свій профіль" },
      { cmd: "/setbio",     desc: "Встановити біо" },
      { cmd: "/settitle",   desc: "Встановити титул" },
      { cmd: "/numerology", desc: "Нумерологія імені" },
      { cmd: "/bmi",        desc: "Розрахунок ІМТ" },
      { cmd: "/age",        desc: "Розрахунок віку" },
      { cmd: "/myid",       desc: "Твій Telegram ID" },
    ]
  },
  {
    label: "🔧 Утиліти",
    color: "text-blue-400",
    commands: [
      { cmd: "/rules",    desc: "Правила чату" },
      { cmd: "/fact",     desc: "Цікавий факт" },
      { cmd: "/quote",    desc: "Надихаюча цитата" },
      { cmd: "/cat",      desc: "Фото котика 🐱" },
      { cmd: "/dog",      desc: "Фото собаки 🐶" },
      { cmd: "/ping",     desc: "Час відповіді бота" },
      { cmd: "/chatinfo", desc: "Статистика чату" },
      { cmd: "/announce", desc: "Оголошення (адмін)" },
      { cmd: "/анкета",   desc: "Заповнити анкету знайомств" },
    ]
  },
];

const CHAT_RULES = [
  { n: "01", title: "Повага", text: "Поважайте всіх учасників незалежно від поглядів. Образи, приниження та токсичність заборонені." },
  { n: "02", title: "Без спаму", text: "Заборонено флуд, повторювані повідомлення та надмірне використання стікерів/емодзі." },
  { n: "03", title: "Без реклами", text: "Будь-яка реклама, самопіар та посилання без дозволу адміністрації — видаляються автоматично." },
  { n: "04", title: "Без пропаганди", text: "Підтримка або виправдання агресії рф — миттєвий бан. Ніяких винятків." },
  { n: "05", title: "Без NSFW", text: "Контент 18+ суворо заборонений. Це стосується тексту, фото та відео." },
  { n: "06", title: "Система варнів", text: "3 попередження = автоматичний бан. Мут видається за дрібні порушення. Апеляція — до адміністрації." },
  { n: "07", title: "Команда", text: "Поважайте рішення адміністрації та модераторів. Суперечки вирішуються в приватному порядку." },
  { n: "08", title: "Верифікація", text: "Нові учасники проходять математичну капчу перед отриманням доступу до функцій бота." },
];

const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: "easeOut" } }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.2 }
  }
};

export default function Home() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: containerRef });
  
  const backgroundY = useTransform(scrollYProgress, [0, 1], ['0%', '20%']);
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  return (
    <div ref={containerRef} className="relative w-full min-h-screen overflow-hidden bg-background">
      <div className="noise-bg"></div>
      
      {/* Abstract Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-primary/10 blur-[120px] mix-blend-screen" />
        <div className="absolute top-[40%] right-[-20%] w-[60vw] h-[60vw] rounded-full bg-accent/5 blur-[150px] mix-blend-screen" />
        <div className="absolute bottom-[-20%] left-[20%] w-[40vw] h-[40vw] rounded-full bg-primary/10 blur-[100px] mix-blend-screen" />
      </div>

      <FloatingButton />

      {/* Hero Section */}
      <section className="relative min-h-[100dvh] flex flex-col items-center justify-center pt-20 px-6">
        <motion.div 
          style={{ y: backgroundY, opacity }}
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          {/* Constellation-like background grid */}
          <div className="w-full h-full bg-[radial-gradient(ellipse_at_center,rgba(139,92,246,0.15)_0%,rgba(0,0,0,0)_60%)]" />
          
          {/* Floating Stars */}
          {[...Array(20)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 bg-white rounded-full"
              style={{
                top: `${Math.random() * 100}%`,
                left: `${Math.random() * 100}%`,
              }}
              animate={{
                opacity: [0, 1, 0],
                scale: [0, 1.5, 0],
              }}
              transition={{
                duration: 3 + Math.random() * 4,
                repeat: Infinity,
                delay: Math.random() * 5,
              }}
            />
          ))}
        </motion.div>

        <div className="z-10 text-center max-w-5xl mx-auto flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            className="mb-6 flex flex-col items-center"
          >
            <span className="px-4 py-1.5 rounded-full border border-white/10 bg-white/5 backdrop-blur-md text-xs font-medium tracking-[0.2em] text-white/70 uppercase mb-8 inline-block glass-panel">
              Українське ком'юніті
            </span>
            <h1 className="text-6xl md:text-8xl lg:text-[10rem] font-heading font-extrabold tracking-tighter leading-none shimmer-text select-none">
              LUMENA
            </h1>
            <p className="mt-8 text-xl md:text-3xl font-light text-white/60 tracking-wide max-w-2xl mx-auto leading-relaxed">
              Світло вашого спілкування. <br/>
              <span className="text-white/80 italic font-serif">Більше ніж просто бот.</span>
            </p>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1, duration: 1 }}
            className="absolute bottom-12 flex flex-col items-center gap-4 text-white/40"
          >
            <span className="text-sm tracking-widest uppercase">Дослідити</span>
            <ChevronDown className="w-5 h-5 animate-bounce" />
          </motion.div>
        </div>
      </section>

      {/* Philosophy / AI Section */}
      <section className="relative z-10 py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div 
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={fadeUp}
            className="grid md:grid-cols-2 gap-16 items-center"
          >
            <div className="space-y-8">
              <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full border border-primary/30 bg-primary/10 text-primary">
                <Wand2 className="w-5 h-5" />
                <span className="font-medium tracking-wide">Lumena AI</span>
              </div>
              <h2 className="text-4xl md:text-6xl font-heading font-bold leading-tight">
                Живий інтелект <br/>у вашому чаті
              </h2>
              <p className="text-lg text-white/60 leading-relaxed font-light">
                Лумка — це не просто набір команд. Це особистість, яка знає контекст ком'юніті, розуміє жарти та веде повноцінні діалоги. Згадайте її в чаті або напишіть в особисті — і ви відчуєте різницю.
              </p>
              <ul className="space-y-4">
                {[
                  "Вбудований AI з унікальним характером",
                  "Пам'ятає контекст розмови",
                  "Спілкується українською як рідною"
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-white/80">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 blur-[100px] rounded-full" />
              <div className="relative glass-panel rounded-2xl p-6 md:p-8 space-y-6">
                <div className="flex items-center gap-4 pb-6 border-b border-white/5">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-900 flex items-center justify-center font-heading font-bold text-xl shadow-[0_0_15px_rgba(139,92,246,0.5)]">
                    L
                  </div>
                  <div>
                    <div className="font-medium">LUMENA</div>
                    <div className="text-xs text-white/50">Online • AI Assistant</div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="flex gap-4">
                    <div className="w-8 h-8 rounded-full bg-white/10 shrink-0" />
                    <div className="bg-white/5 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-white/80">
                      Лумка, розкажи щось цікаве про космос
                    </div>
                  </div>
                  <div className="flex gap-4 flex-row-reverse">
                    <div className="w-8 h-8 rounded-full bg-primary/20 shrink-0 flex items-center justify-center text-xs">L</div>
                    <div className="bg-primary/20 border border-primary/20 rounded-2xl rounded-tr-sm px-4 py-3 text-sm text-white shadow-[0_0_20px_rgba(139,92,246,0.1)]">
                      Знаєш, ми всі буквально складаємося із зоряного пилу ✨ Кожен атом у нашому тілі був викуваний у центрі зірки мільярди років тому. Тому, коли ти дивишся на нічне небо — ти дивишся додому.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="relative z-10 py-32 px-6 bg-black/40">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            className="text-center mb-20"
          >
            <h2 className="text-4xl md:text-5xl font-heading font-bold shimmer-text-primary mb-6">
              Екосистема Можливостей
            </h2>
            <p className="text-white/50 max-w-2xl mx-auto">
              Від економіки до модерації — LUMENA пропонує все необхідне для створення ідеального простору.
            </p>
          </motion.div>

          <motion.div 
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-50px" }}
            className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            <FeatureCard 
              icon={<Coins className="text-accent" />}
              title="Економіка"
              description="Заробляй LMN, працюй, рибаль, грай у казино або грабуй. Кожні 6 годин — грошовий дощ у чаті."
              commands={['/balance', '/work', '/casino', '/rob']}
            />
            <FeatureCard 
              icon={<Heart className="text-pink-500" />}
              title="Соціум та Аура"
              description="Шукай ідеальну пару, одружуйся, даруй репутацію та підвищуй свою ауру спілкуванням."
              commands={['/marry', '/aura', '/rep', '/couple']}
            />
            <FeatureCard 
              icon={<ShieldAlert className="text-red-400" />}
              title="Модерація"
              description="Гнучка система ролей, авто-мути, анти-пропаганда фільтр та повний контроль над чатом."
              commands={['/ban', '/mute', '/warn', '/purge']}
            />
            <FeatureCard 
              icon={<LinkIcon className="text-blue-400" />}
              title="Анти-лінк"
              description="Автоматичне видалення спам-посилань від новачків із системою вайтлістів для адмінів."
              commands={['антилинк вкл', 'белый_список']}
            />
            <FeatureCard 
              icon={<Gamepad2 className="text-green-400" />}
              title="Розваги"
              description="Від російської рулетки до шибениці, правди чи дії. Нудьгувати не доведеться."
              commands={['/roulette', '/hangman', '/truth']}
            />
            <FeatureCard 
              icon={<UserCircle className="text-purple-400" />}
              title="Профіль & Утиліти"
              description="Налаштуй біо, отримуй титули, дізнайся нумерологію імені або розрахуй ІМТ."
              commands={['/profile', '/settitle', '/numerology']}
            />
          </motion.div>
        </div>
      </section>

      {/* Deep Dive Section (Verification) */}
      <section className="relative z-10 py-40 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="glass-panel rounded-[2rem] p-8 md:p-16 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-primary/5 rounded-full blur-[120px] pointer-events-none translate-x-1/3 -translate-y-1/3" />
            
            <div className="relative z-10 grid lg:grid-cols-2 gap-16 items-center">
              <motion.div 
                initial={{ opacity: 0, x: -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8 }}
                className="space-y-8"
              >
                <CheckCircle2 className="w-12 h-12 text-primary" />
                <h2 className="text-4xl md:text-5xl font-heading font-bold">Закритий клуб.<br/>Жодних ботів.</h2>
                <p className="text-lg text-white/60 font-light">
                  Безпека ком'юніті починається з порогу. Кожен новий учасник має пройти математичну капчу, щоб довести, що він людина. Тільки після цього відкривається доступ до всіх можливостей.
                </p>
                <div className="pt-6 border-t border-white/10">
                  <h3 className="text-xl font-medium mb-4 flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-white/40" /> Система анкет
                  </h3>
                  <p className="text-white/50 text-sm">
                    Зручна подача заявок на вступ чи ролі через бот. Адміністрація розглядає анкети, а VIP-учасники отримують преміум-шаблони.
                  </p>
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, x: 50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8, delay: 0.2 }}
                className="relative"
              >
                <div className="glass-panel rounded-xl p-6 border border-white/10 bg-black/40">
                  <div className="flex items-center gap-3 mb-6">
                    <ShieldAlert className="w-5 h-5 text-accent" />
                    <span className="font-medium text-sm text-white/80">Перевірка безпеки</span>
                  </div>
                  <div className="text-center space-y-6">
                    <div className="text-2xl font-mono tracking-widest bg-white/5 py-4 rounded-lg">
                      45 × 3 = ?
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {[125, 135, 145, 155].map((num, i) => (
                        <button key={i} className={`py-3 rounded-lg border transition-all ${num === 135 ? 'border-primary/50 bg-primary/10 hover:bg-primary/20 text-primary' : 'border-white/10 hover:bg-white/5 text-white/60'}`}>
                          {num}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer / Final CTA */}
      <footer className="relative z-10 py-32 px-6 border-t border-white/5 bg-gradient-to-b from-transparent to-black/80">
        <div className="max-w-4xl mx-auto text-center space-y-12">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-5xl md:text-7xl font-heading font-bold shimmer-text mb-8">
              Готові увімкнути світло?
            </h2>
            <p className="text-xl text-white/50 font-light mb-12 max-w-2xl mx-auto">
              Додайте LUMENA до своєї групи і перетворіть звичайний чат на повноцінну екосистему.
            </p>
            <a 
              href="https://t.me/LumenarAi_Bot" 
              target="_blank" 
              rel="noopener noreferrer"
              className="inline-flex items-center gap-3 px-8 py-5 rounded-full bg-white text-black font-semibold text-lg transition-transform hover:scale-105 active:scale-95 shadow-[0_0_40px_rgba(255,255,255,0.2)]"
            >
              <MessageSquareText className="w-6 h-6" />
              Додати в Telegram
            </a>
          </motion.div>
          
          <div className="pt-20 text-sm text-white/30 flex flex-col md:flex-row items-center justify-between">
            <p>© {new Date().getFullYear()} LUMENA. All rights reserved.</p>
            <div className="flex gap-6 mt-4 md:mt-0">
              <span className="hover:text-white/60 cursor-pointer transition-colors">Правила</span>
              <span className="hover:text-white/60 cursor-pointer transition-colors">Команди</span>
              <span className="hover:text-white/60 cursor-pointer transition-colors">Підтримка</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description, commands }: { icon: React.ReactNode, title: string, description: string, commands: string[] }) {
  return (
    <motion.div 
      variants={fadeUp}
      className="glass-panel glass-panel-hover rounded-2xl p-8 group transition-all duration-500 flex flex-col h-full"
    >
      <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500">
        {icon}
      </div>
      <h3 className="text-xl font-heading font-semibold mb-3 text-white/90">{title}</h3>
      <p className="text-white/50 text-sm leading-relaxed mb-6 flex-grow">{description}</p>
      
      <div className="flex flex-wrap gap-2 mt-auto">
        {commands.map((cmd, i) => (
          <span key={i} className="px-2 py-1 rounded bg-white/5 text-white/40 text-xs font-mono border border-white/5">
            {cmd}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
