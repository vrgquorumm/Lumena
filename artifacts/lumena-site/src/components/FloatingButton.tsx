import { motion } from 'framer-motion';
import { Send } from 'lucide-react';

export function FloatingButton() {
  return (
    <motion.a
      href="https://t.me/LumenarAi_Bot"
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay: 1 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className="fixed bottom-6 right-6 md:bottom-10 md:right-10 z-50 flex items-center gap-3 px-6 py-4 rounded-full bg-primary/20 backdrop-blur-xl border border-primary/50 shadow-[0_0_30px_rgba(139,92,246,0.3)] text-white font-medium overflow-hidden group"
    >
      <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/40 to-primary/0 translate-x-[-100%] group-hover:animate-[shimmer_2s_infinite]" />
      <div className="relative flex items-center gap-2">
        <Send className="w-5 h-5" />
        <span className="hidden sm:inline-block">Відкрити в Telegram</span>
        <span className="sm:hidden">Telegram</span>
      </div>
      
      {/* Pulse effect */}
      <span className="absolute flex h-full w-full inset-0 rounded-full">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75"></span>
      </span>
    </motion.a>
  );
}
