/**
 * Telegram Mini App integration hook.
 *
 * Calls Telegram.WebApp.ready() so the loading indicator disappears,
 * expands to full height, and returns the WebApp object for advanced use.
 */
import { useEffect } from 'react';

// Minimal type declaration for window.Telegram
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready(): void;
        expand(): void;
        colorScheme: 'light' | 'dark';
        themeParams: Record<string, string>;
        initDataUnsafe: {
          user?: {
            id: number;
            first_name: string;
            last_name?: string;
            username?: string;
          };
        };
        MainButton: {
          setText(text: string): void;
          show(): void;
          hide(): void;
          onClick(fn: () => void): void;
        };
        close(): void;
      };
    };
  }
}

export function useTelegramWebApp() {
  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    if (!tg) return;
    tg.ready();   // прибирає завантажувальний екран Telegram
    tg.expand();  // розгортає на весь екран
  }, [tg]);

  return tg ?? null;
}

/** True якщо сторінка відкрита всередині Telegram Mini App */
export function isInsideTelegram(): boolean {
  return !!window.Telegram?.WebApp;
}
